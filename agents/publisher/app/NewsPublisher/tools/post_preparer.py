"""Deterministically create or merge a news post using the actual repository state."""
import json
import os
from datetime import datetime, timezone

from strands import tool
from tools.formatter import format_post
from tools.git_ops import write_new_post
from tools.merger import merge_posts
from tools.s3_reader import read_from_s3


@tool
def prepare_post(repo_path: str, file_path: str, s3_bucket: str, s3_key: str, strategy: str = "{}") -> dict:
    """Prepare a daily news post on disk, preserving existing content on every run.

    Args:
        repo_path: Local cloned repository directory.
        file_path: Daily post path within the repository.
        s3_bucket: Bucket containing the collected news.
        s3_key: Key of the collection JSON.
        strategy: JSON merge options; applies when a post already exists.

    Returns:
        Status, action (publish_new or merge_update), and item counts. No Git push.
    """
    try:
        if os.path.exists(os.path.join(repo_path, file_path)):
            result = json.loads(merge_posts(repo_path, file_path, s3_bucket, s3_key, strategy))
            return {**result, "action": "merge_update"}

        source = read_from_s3(s3_bucket, s3_key)
        if source["status"] == "error":
            return source
        data = source["data"]
        if data.get("updated_items"):
            return {"status": "error", "error": "Cannot apply topic updates: target post is missing"}
        timestamp = datetime.fromisoformat(data["collected_at"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        timestamp = timestamp.astimezone(timezone.utc)
        rendered = json.loads(format_post(
            json.dumps(data["new_items"], ensure_ascii=False), "norway_daily", "{}",
            timestamp.strftime("%Y-%m-%d"), timestamp.strftime("%H:%M:%S"),
        ))
        if rendered["status"] == "error":
            return rendered
        result = write_new_post(repo_path, file_path, rendered["content"])
        return {**result, "action": "publish_new", "new_items_added": len(data["new_items"]),
                "existing_items_updated": 0, "total_items": len(data["new_items"])}
    except (KeyError, TypeError, ValueError, OSError) as exc:
        return {"status": "error", "error": str(exc)}
