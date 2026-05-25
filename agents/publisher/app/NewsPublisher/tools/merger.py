import json
import re
import datetime

import boto3
from strands import tool

from tools.sections import SECTION_MAP, SECTION_ORDER, REVERSE_SECTION_MAP


def _parse_post(content: str) -> dict:
    """Parse a blog post into structured sections with items."""
    lines = content.split("\n")

    # Extract frontmatter
    frontmatter = ""
    if lines[0].strip() == "---":
        end_idx = content.index("---", 4)
        frontmatter = content[: end_idx + 3]
        rest = content[end_idx + 3 :].strip()
    else:
        rest = content

    # Extract day summary (between ## 今日综述 and <!-- more -->)
    summary_section = ""
    summary_match = re.search(
        r"## 今日综述\n(.*?)<!-- more -->", rest, re.DOTALL
    )
    if summary_match:
        summary_section = summary_match.group(1).strip()

    # Parse sections
    sections = {}
    section_pattern = r"## (国内新闻|国际新闻|财经新闻)\n"
    section_splits = re.split(section_pattern, rest)

    current_section = None
    for i, part in enumerate(section_splits):
        if part in REVERSE_SECTION_MAP:
            current_section = REVERSE_SECTION_MAP[part]
            sections[current_section] = []
        elif current_section is not None:
            # Parse items within section
            item_splits = re.split(r"### \d+\.\s+", part)
            for item_text in item_splits[1:]:
                item_lines = item_text.strip().split("\n")
                title = item_lines[0].strip()

                sources_text = ""
                earliest_time = ""
                summary_lines = []
                changelog = ""
                past_header = False
                source_urls = []

                for line in item_lines[1:]:
                    if line.startswith("**来源**:"):
                        sources_match = re.search(
                            r"\*\*来源\*\*:\s*(.+?)\s*\|\s*\*\*最早报道\*\*:\s*(.+)",
                            line,
                        )
                        if sources_match:
                            sources_text = sources_match.group(1)
                            earliest_time = sources_match.group(2)
                        past_header = True
                    elif line.startswith("原文链接:"):
                        urls = re.findall(r"\[(.+?)\]\((https?://[^\)]+)\)", line)
                        source_urls.extend(
                            [{"source_label": label, "url": url} for label, url in urls]
                        )
                    elif line.strip().startswith("(更新于"):
                        changelog = line.strip()
                    elif line.strip() == "---":
                        continue
                    elif past_header and line.strip():
                        summary_lines.append(line.strip())

                sections[current_section].append({
                    "title_zh": title,
                    "sources_text": sources_text,
                    "earliest_time": earliest_time,
                    "summary_zh": "\n".join(summary_lines),
                    "source_urls": source_urls,
                    "changelog": changelog,
                })

    return {
        "frontmatter": frontmatter,
        "summary": summary_section,
        "sections": sections,
    }


def _render_item(number: int, item: dict) -> str:
    """Render a single item as markdown."""
    lines = [f"### {number}. {item['title_zh']}"]
    lines.append(f"**来源**: {item['sources_text']} | **最早报道**: {item['earliest_time']}")
    lines.append("")
    lines.append(item["summary_zh"])
    if item.get("changelog"):
        lines.append(item["changelog"])
    lines.append("")

    links = " | ".join(
        f"[{s['source_label']}]({s['url']})" for s in item["source_urls"]
    )
    lines.append(f"原文链接: {links}")
    lines.append("")
    lines.append("---")
    return "\n".join(lines)


def _rebuild_post(parsed: dict, updated_time: str) -> str:
    """Rebuild the full post markdown from parsed structure."""
    parts = [parsed["frontmatter"], ""]
    parts.append("<style>article.article-content, .post-body, .article-entry { font-size: 1.15em; line-height: 1.8; }</style>")
    parts.append("")
    parts.append(f"*最后更新: {updated_time} UTC*")
    parts.append("")
    parts.append("## 今日综述")
    parts.append(parsed["summary"])
    parts.append("")
    parts.append("<!-- more -->")
    parts.append("")

    number = 1
    for cat in SECTION_ORDER:
        parts.append(f"## {SECTION_MAP[cat]}")
        parts.append("")
        items = parsed["sections"].get(cat, [])
        for item in items:
            parts.append(_render_item(number, item))
            parts.append("")
            number += 1

    # Footer with all sources
    all_sources = set()
    for cat in SECTION_ORDER:
        for item in parsed["sections"].get(cat, []):
            for s in item["source_urls"]:
                all_sources.add(s["source_label"])
    parts.append(f"*新闻来源: {', '.join(sorted(all_sources))}*")

    return "\n".join(parts)


@tool
def merge_posts(repo_path: str, file_path: str, s3_bucket: str, s3_key: str, strategy: str) -> str:
    """Merge new and updated items into an existing blog post on disk.

    Reads existing content from repo_path/file_path, merges with new items from S3,
    and writes the result back to the same file. Returns only metadata (not content).

    Args:
        repo_path: Local path to the cloned repository (from git_clone result)
        file_path: Path within the repo to the existing blog post
        s3_bucket: S3 bucket containing the collected items JSON
        s3_key: S3 key of the collected items JSON
        strategy: JSON string with merge strategy options (new_items, updated_items, renumber, regenerate_day_summary)

    Returns:
        JSON string with status and counts (new_items_added, existing_items_updated, total_items)
    """
    import os
    full_path = os.path.join(repo_path, file_path)

    if not os.path.exists(full_path):
        return json.dumps({"status": "error", "error": f"File not found: {file_path}"})

    with open(full_path, "r", encoding="utf-8") as f:
        existing_content = f.read()

    if not existing_content.strip():
        return json.dumps({"status": "error", "error": "Cannot merge into empty existing content. Use format_post for new posts."})

    try:
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        collection_data = json.loads(obj["Body"].read())

        parsed = _parse_post(existing_content)
        new = collection_data.get("new_items", [])
        updated = collection_data.get("updated_items", [])
        strat = json.loads(strategy)

        items_added = 0
        items_updated = 0

        # Apply updates to existing items
        for update in updated:
            match_title = update["match_title_zh"]
            matched = False
            for cat in SECTION_ORDER:
                for item in parsed["sections"].get(cat, []):
                    if item["title_zh"] == match_title:
                        item["summary_zh"] = update["updated_summary_zh"]
                        new_src = update["new_source"]
                        item["source_urls"].append({
                            "source_label": new_src["source_label"],
                            "url": new_src["url"],
                        })
                        item["sources_text"] = ", ".join(
                            s["source_label"] for s in item["source_urls"]
                        )
                        item["changelog"] = f"({update['changelog']})"
                        items_updated += 1
                        matched = True
                        break
                if matched:
                    break

        # Insert new items into correct sections
        prepend = strat.get("new_items") == "prepend_per_section"
        for item in new:
            cat = item.get("category", "domestic")
            if cat not in parsed["sections"]:
                parsed["sections"][cat] = []

            sources = item.get("sources", [])
            sources_text = ", ".join(s["source_label"] for s in sources)
            earliest = min((s["published_at"] for s in sources if s.get("published_at")), default="")
            source_urls = [
                {"source_label": s["source_label"], "url": s["url"]} for s in sources
            ]

            new_entry = {
                "title_zh": item["title_zh"],
                "sources_text": sources_text,
                "earliest_time": earliest,
                "summary_zh": item["summary_zh"],
                "source_urls": source_urls,
                "changelog": "",
            }

            if prepend:
                parsed["sections"][cat].insert(0, new_entry)
            else:
                parsed["sections"][cat].append(new_entry)
            items_added += 1

        # Count total items
        total = sum(len(items) for items in parsed["sections"].values())

        updated_time = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M")
        content = _rebuild_post(parsed, updated_time)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return json.dumps({
            "status": "success",
            "new_items_added": items_added,
            "existing_items_updated": items_updated,
            "total_items": total,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})
