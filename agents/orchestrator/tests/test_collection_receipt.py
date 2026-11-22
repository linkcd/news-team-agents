from datetime import datetime, timedelta, timezone
import json
from unittest.mock import MagicMock, patch

import pytest


TASK = {"task_id": "receipt-test", "output": {"s3_bucket": "test-bucket", "s3_key_prefix": "collections/today/"}}
FORMAT_ERROR = {"status": "error", "error": "No structured result in agent response"}


def stored_collection():
    return {"task_id": "receipt-test", "new_items": [{"title_zh": "Topic", "summary_zh": "Facts",
             "sources": [{"url": "https://example.com/news"}]}], "updated_items": [],
            "metadata": {"grouped_into_new_topics": 99}}


def test_successful_collection_is_recovered_from_s3_when_agent_returns_markdown():
    from tools.invoke_collector import invoke_collector

    s3 = MagicMock()
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: json.dumps(stored_collection()).encode()),
                                  "LastModified": datetime.now(timezone.utc) + timedelta(seconds=1)}
    with patch("tools.a2a_client.invoke_a2a", return_value=FORMAT_ERROR), patch("boto3.client", return_value=s3):
        result = invoke_collector(TASK)
    assert result["status"] == "success"
    assert result["data_key"] == "collections/today/receipt-test.json"
    assert result["summary"]["grouped_into_new_topics"] == 1
    assert result["summary"]["matched_to_existing_topics"] == 0
    assert "new_items" not in result
    s3.get_object.assert_called_once_with(Bucket="test-bucket", Key="collections/today/receipt-test.json")


@pytest.mark.parametrize("problem", ["stale", "wrong_task", "bad_shape"])
def test_unverified_s3_output_is_not_accepted(problem):
    from tools.invoke_collector import invoke_collector

    data = stored_collection()
    modified = datetime.now(timezone.utc) + timedelta(seconds=1)
    if problem == "stale":
        modified -= timedelta(days=1)
    elif problem == "wrong_task":
        data["task_id"] = "another-task"
    else:
        data["new_items"] = "not a list"
    s3 = MagicMock()
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: json.dumps(data).encode()), "LastModified": modified}
    with patch("tools.a2a_client.invoke_a2a", return_value=FORMAT_ERROR), patch("boto3.client", return_value=s3):
        result = invoke_collector(TASK)
    assert result["status"] == "error"
    s3.get_object.assert_called_once()


def test_real_agent_failure_is_not_overridden_by_a_receipt():
    from tools.invoke_collector import invoke_collector

    error = {"status": "error", "error": "Access denied"}
    with patch("tools.a2a_client.invoke_a2a", return_value=error), patch("boto3.client") as client:
        assert invoke_collector(TASK) == error
    client.assert_not_called()
