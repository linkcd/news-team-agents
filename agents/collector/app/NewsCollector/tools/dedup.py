import json
import re

import boto3
import httpx
from bedrock_agentcore.identity import requires_api_key
from strands import tool


def _parse_markdown_topics(markdown: str) -> tuple[list[str], list[dict]]:
    """Parse a blog post markdown to extract URLs and topic summaries."""
    urls = re.findall(r'\[.*?\]\((https?://[^\)]+)\)', markdown)

    topics = []
    sections = re.split(r'###\s+\d+\.\s+', markdown)
    for section in sections[1:]:  # skip content before first ###
        lines = section.strip().split('\n')
        title = lines[0].strip()

        summary_lines = []
        past_source = False
        for line in lines[1:]:
            if line.strip().startswith("来源:") or line.strip().startswith("来源："):
                past_source = True
                continue
            if past_source and line.strip():
                summary_lines.append(line.strip())

        summary = "\n".join(summary_lines)
        source_urls = re.findall(r'\[.*?\]\((https?://[^\)]+)\)', section)

        topics.append(
            {"title": title, "summary": summary, "source_urls": source_urls}
        )

    return urls, topics


def _parse_s3_collection(data: dict) -> tuple[list[str], list[dict]]:
    """Parse a previous S3 collection output to extract URLs and topics."""
    urls = []
    topics = []

    for item in data.get("new_items", []):
        for source in item.get("sources", []):
            urls.append(source["url"])
        topics.append(
            {
                "title": item.get("title_zh", ""),
                "summary": item.get("summary_zh", ""),
                "source_urls": [s["url"] for s in item.get("sources", [])],
            }
        )

    for item in data.get("updated_items", []):
        if "new_source" in item:
            urls.append(item["new_source"]["url"])

    return urls, topics


@requires_api_key(provider_name="github-token", into="api_key")
def _fetch_github_file(repo: str, path: str, api_key: str = "") -> dict:
    """Fetch a file from GitHub using the injected token for private repos."""
    raw_url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
    headers = {"Authorization": f"token {api_key}"} if api_key else {}
    response = httpx.get(raw_url, timeout=15, follow_redirects=True, headers=headers)
    response.raise_for_status()
    return {"content": response.text}


@tool
def get_dedup_context(dedup_config: str) -> dict:
    """Read existing URLs and topic summaries from a dedup source.

    This tool reads previously collected content to enable deduplication.
    It supports multiple source types: none, url_list, github_file, s3_file.

    Args:
        dedup_config: JSON string with dedup source configuration. Must include "type" field.

    Returns:
        Dict with status, known_urls list, existing_topics list (each with title, summary, source_urls)
    """
    config = json.loads(dedup_config)
    source_type = config.get("type", "none")

    if source_type == "none":
        return {"status": "success", "known_urls": [], "existing_topics": []}

    if source_type == "url_list":
        return {
            "status": "success",
            "known_urls": config.get("urls", []),
            "existing_topics": [],
        }

    if source_type == "github_file":
        repo = config["repo"]
        path = config["path"]
        try:
            result = _fetch_github_file(repo=repo, path=path)
            content = result["content"]
        except Exception:
            return {"status": "success", "known_urls": [], "existing_topics": []}

        if not content:
            return {"status": "success", "known_urls": [], "existing_topics": []}

        urls, topics = _parse_markdown_topics(content)
        return {"status": "success", "known_urls": urls, "existing_topics": topics}

    if source_type == "s3_file":
        bucket = config["bucket"]
        key = config["key"]
        try:
            s3 = boto3.client("s3")
            obj = s3.get_object(Bucket=bucket, Key=key)
            data = json.loads(obj["Body"].read())
        except Exception as e:
            return {"status": "error", "error": str(e), "known_urls": [], "existing_topics": []}

        urls, topics = _parse_s3_collection(data)
        return {"status": "success", "known_urls": urls, "existing_topics": topics}

    return {
        "status": "error",
        "error": f"Unknown dedup source type: {source_type}",
        "known_urls": [],
        "existing_topics": [],
    }
