import json
from unittest.mock import patch, MagicMock

import pytest


def test_write_to_s3_writes_json():
    from src.tools.s3_writer import write_to_s3

    data = {
        "task_id": "test-001",
        "new_items": [{"title_zh": "测试"}],
        "updated_items": [],
        "metadata": {"sources_fetched": 1},
    }

    with patch("src.tools.s3_writer.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        result = write_to_s3(
            bucket="news-agent-data",
            key="collections/2026-05-21/1100-test.json",
            data=json.dumps(data),
        )

    assert result["status"] == "success"
    assert result["key"] == "collections/2026-05-21/1100-test.json"

    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args[1]
    assert call_kwargs["Bucket"] == "news-agent-data"
    assert call_kwargs["Key"] == "collections/2026-05-21/1100-test.json"
    written_data = json.loads(call_kwargs["Body"])
    assert written_data["task_id"] == "test-001"


def test_write_to_s3_handles_error():
    from src.tools.s3_writer import write_to_s3

    with patch("src.tools.s3_writer.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.put_object.side_effect = Exception("Access Denied")

        result = write_to_s3(
            bucket="news-agent-data",
            key="collections/test.json",
            data='{"test": true}',
        )

    assert result["status"] == "error"
    assert "Access Denied" in result["error"]
