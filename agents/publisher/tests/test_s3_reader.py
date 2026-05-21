import json
from unittest.mock import patch, MagicMock

import pytest


def test_read_from_s3_returns_parsed_json():
    from tools.s3_reader import read_from_s3

    s3_data = {
        "task_id": "test-001",
        "new_items": [{"title_zh": "测试新闻", "category": "domestic"}],
        "updated_items": [],
        "metadata": {"sources_fetched": 3},
    }

    with patch("tools.s3_reader.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(s3_data).encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_body}

        result = read_from_s3(
            bucket="news-agent-data",
            key="collections/2026-05-21/0500-norway-news.json",
        )

    assert result["status"] == "success"
    assert result["data"]["task_id"] == "test-001"
    assert len(result["data"]["new_items"]) == 1
    assert result["data"]["new_items"][0]["title_zh"] == "测试新闻"

    mock_s3.get_object.assert_called_once_with(
        Bucket="news-agent-data",
        Key="collections/2026-05-21/0500-norway-news.json",
    )


def test_read_from_s3_handles_missing_key():
    from tools.s3_reader import read_from_s3

    with patch("tools.s3_reader.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.get_object.side_effect = Exception("NoSuchKey: The specified key does not exist.")

        result = read_from_s3(bucket="news-agent-data", key="nonexistent.json")

    assert result["status"] == "error"
    assert "NoSuchKey" in result["error"]
