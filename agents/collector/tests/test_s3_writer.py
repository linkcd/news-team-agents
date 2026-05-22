import json
from unittest.mock import patch, MagicMock

import pytest


def test_write_to_s3_writes_json():
    from tools.s3_writer import write_to_s3

    data = {
        "task_id": "test-001",
        "new_items": [{"title_zh": "测试"}],
        "updated_items": [],
        "metadata": {"sources_fetched": 1},
    }

    with patch("tools.s3_writer.boto3") as mock_boto3:
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
    from tools.s3_writer import write_to_s3

    with patch("tools.s3_writer.boto3") as mock_boto3:
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


def test_write_to_s3_fixes_unescaped_quotes():
    from tools.s3_writer import write_to_s3

    bad_json = '''{
      "task_id": "test-002",
      "new_items": [
        {
          "title_zh": "事故经过"既像快进又像慢动作"",
          "category": "domestic",
          "summary_zh": "一名骑车者描述事故经过"既像快进又像慢动作"。挪威公路管理局呼吁注意安全。",
          "sources": []
        }
      ],
      "updated_items": [],
      "metadata": {}
    }'''

    with patch("tools.s3_writer.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        result = write_to_s3(
            bucket="news-agent-data",
            key="collections/test-fix.json",
            data=bad_json,
        )

    assert result["status"] == "success"
    written = json.loads(mock_s3.put_object.call_args[1]["Body"])
    assert '既像快进又像慢动作' in written["new_items"][0]["title_zh"]
    assert '"' in written["new_items"][0]["title_zh"]


def test_write_to_s3_rejects_unfixable_json():
    from tools.s3_writer import write_to_s3

    result = write_to_s3(
        bucket="news-agent-data",
        key="collections/bad.json",
        data="this is not json at all {{{",
    )

    assert result["status"] == "error"
    assert "Invalid JSON" in result["error"]
