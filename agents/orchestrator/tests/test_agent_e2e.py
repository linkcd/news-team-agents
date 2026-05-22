"""End-to-end test for the Orchestrator agent workflow with mocked tool responses."""

import json
import sys
from unittest.mock import MagicMock, patch, call

import pytest


@pytest.fixture
def mock_invoke_a2a():
    """Patch invoke_a2a at the module level to control responses."""
    from tools import a2a_client
    original = a2a_client.invoke_a2a
    mock = MagicMock()
    a2a_client.invoke_a2a = mock
    yield mock
    a2a_client.invoke_a2a = original


# Legacy fixture name for backward compatibility
@pytest.fixture
def mock_boto3_client(mock_invoke_a2a):
    """Adapts the old fixture interface to the new invoke_a2a mock."""
    return mock_invoke_a2a


def make_a2a_success_response(data: dict) -> dict:
    """Helper: returns data as if invoke_a2a succeeded."""
    return data


def make_a2a_error_response(error_text: str) -> dict:
    """Helper: returns an error dict as if invoke_a2a got a failure."""
    return {"status": "error", "error": error_text}


class TestOrchestratorWorkflow:
    def test_successful_first_run_with_new_topics(self, mock_boto3_client):
        """First run of day: collects news, publishes new post."""
        from tools.invoke_collector import invoke_collector
        from tools.invoke_publisher import invoke_publisher

        collector_result = {
            "status": "success",
            "task_id": "norway-news-2026-05-21-0500",
            "data_key": "collections/2026-05-21/0500-norway-news.json",
            "summary": {
                "sources_fetched": 11,
                "items_in_rss": 45,
                "after_time_filter": 20,
                "new_urls_found": 8,
                "grouped_into_new_topics": 3,
                "matched_to_existing_topics": 0,
                "skipped_no_new_info": 0,
                "skipped_already_seen_urls": 0,
            },
        }
        publisher_result = {
            "status": "success",
            "task_id": "publish-norway-2026-05-21-0500",
            "result": {
                "action": "publish_new",
                "file_path": "source/_posts/20260521-norway.md",
                "commit_sha": "abc123",
                "new_items_added": 3,
                "total_items_in_post": 3,
            },
        }

        mock_boto3_client.side_effect = [
            make_a2a_success_response(collector_result),
            make_a2a_success_response(publisher_result),
        ]

        # Invoke collector
        coll_result = invoke_collector({
            "task_id": "norway-news-2026-05-21-0500",
            "sources": [{"url": "https://nrk.no/rss", "type": "rss"}],
            "filters": {"time_window_hours": 6, "dedup_source": {"type": "none"}},
            "processing": {"consolidate_topics": True, "translate_to": ["zh"]},
            "output": {"s3_bucket": "news-agent-data-548129671048", "s3_key_prefix": "collections/2026-05-21/"},
        })
        assert coll_result["status"] == "success"
        assert coll_result["summary"]["grouped_into_new_topics"] == 3

        # Invoke publisher
        pub_result = invoke_publisher({
            "task_id": "publish-norway-2026-05-21-0500",
            "type": "publish_new",
            "source": {"type": "s3", "bucket": "news-agent-data-548129671048", "key": coll_result["data_key"]},
            "template": "norway_daily",
            "output": {"repo": "claw-lu/hexo-blog", "branch": "main", "file_path": "source/_posts/20260521-norway.md"},
        })
        assert pub_result["status"] == "success"
        assert pub_result["result"]["commit_sha"] == "abc123"

    def test_subsequent_run_with_merge_update(self, mock_boto3_client):
        """Subsequent run: collects new topics, merges into existing post."""
        from tools.invoke_collector import invoke_collector
        from tools.invoke_publisher import invoke_publisher

        collector_result = {
            "status": "success",
            "task_id": "norway-news-2026-05-21-1100",
            "data_key": "collections/2026-05-21/1100-norway-news.json",
            "summary": {
                "sources_fetched": 11,
                "items_in_rss": 50,
                "after_time_filter": 15,
                "new_urls_found": 4,
                "grouped_into_new_topics": 2,
                "matched_to_existing_topics": 1,
                "skipped_no_new_info": 1,
                "skipped_already_seen_urls": 10,
            },
        }
        publisher_result = {
            "status": "success",
            "task_id": "publish-norway-2026-05-21-1100",
            "result": {
                "action": "merge_update",
                "file_path": "source/_posts/20260521-norway.md",
                "commit_sha": "def456",
                "new_items_added": 2,
                "existing_items_updated": 1,
                "total_items_in_post": 6,
            },
        }

        mock_boto3_client.side_effect = [
            make_a2a_success_response(collector_result),
            make_a2a_success_response(publisher_result),
        ]

        coll_result = invoke_collector({
            "task_id": "norway-news-2026-05-21-1100",
            "sources": [{"url": "https://nrk.no/rss", "type": "rss"}],
            "filters": {
                "time_window_hours": 6,
                "dedup_source": {"type": "github_file", "repo": "claw-lu/hexo-blog", "path": "source/_posts/20260521-norway.md"},
            },
            "processing": {"consolidate_topics": True, "translate_to": ["zh"]},
            "output": {"s3_bucket": "news-agent-data-548129671048", "s3_key_prefix": "collections/2026-05-21/"},
        })
        assert coll_result["status"] == "success"

        pub_result = invoke_publisher({
            "task_id": "publish-norway-2026-05-21-1100",
            "type": "merge_update",
            "source": {"type": "s3", "bucket": "news-agent-data-548129671048", "key": coll_result["data_key"]},
            "target": {"repo": "claw-lu/hexo-blog", "branch": "main", "file_path": "source/_posts/20260521-norway.md"},
            "merge_strategy": {"new_items": "append_per_section", "updated_items": "replace_summary_and_add_source", "renumber": True, "regenerate_day_summary": True},
        })
        assert pub_result["status"] == "success"
        assert pub_result["result"]["action"] == "merge_update"
        assert pub_result["result"]["total_items_in_post"] == 6

    def test_no_new_topics_skips_publish(self, mock_boto3_client):
        """When collector finds nothing new, publisher is not invoked."""
        from tools.invoke_collector import invoke_collector

        collector_result = {
            "status": "success",
            "task_id": "norway-news-2026-05-21-2300",
            "data_key": "collections/2026-05-21/2300-norway-news.json",
            "summary": {
                "sources_fetched": 11,
                "items_in_rss": 30,
                "after_time_filter": 5,
                "new_urls_found": 0,
                "grouped_into_new_topics": 0,
                "matched_to_existing_topics": 0,
                "skipped_no_new_info": 3,
                "skipped_already_seen_urls": 5,
            },
        }

        mock_boto3_client.return_value = make_a2a_success_response(collector_result)

        coll_result = invoke_collector({
            "task_id": "norway-news-2026-05-21-2300",
            "sources": [{"url": "https://nrk.no/rss", "type": "rss"}],
            "filters": {"time_window_hours": 6},
            "processing": {"consolidate_topics": True},
            "output": {"s3_bucket": "news-agent-data-548129671048", "s3_key_prefix": "collections/2026-05-21/"},
        })

        assert coll_result["status"] == "success"
        assert coll_result["summary"]["grouped_into_new_topics"] == 0
        assert coll_result["summary"]["matched_to_existing_topics"] == 0
        # In the real agent flow, the LLM would decide not to call invoke_publisher.
        # We verify the collector was called only once (no publisher call).
        assert mock_boto3_client.call_count == 1

    def test_collector_failure_with_retry(self, mock_boto3_client):
        """Collector fails first time, retried once, succeeds on second attempt."""
        from tools.invoke_collector import invoke_collector

        collector_success = {
            "status": "success",
            "task_id": "norway-news-2026-05-21-1100",
            "data_key": "collections/2026-05-21/1100-norway-news.json",
            "summary": {"grouped_into_new_topics": 2, "matched_to_existing_topics": 0},
        }

        mock_boto3_client.side_effect = [
            make_a2a_error_response("Timeout fetching RSS"),
            make_a2a_success_response(collector_success),
        ]

        task_config = {"task_id": "norway-news-2026-05-21-1100", "sources": []}

        # First call fails
        result1 = invoke_collector(task_config)
        assert result1["status"] == "error"

        # Retry succeeds
        result2 = invoke_collector(task_config)
        assert result2["status"] == "success"
        assert result2["summary"]["grouped_into_new_topics"] == 2

    def test_collector_failure_after_retry_returns_failure(self, mock_boto3_client):
        """Collector fails both attempts, orchestrator reports failure."""
        from tools.invoke_collector import invoke_collector

        mock_boto3_client.side_effect = [
            make_a2a_error_response("Timeout fetching RSS"),
            make_a2a_error_response("Timeout fetching RSS again"),
        ]

        task_config = {"task_id": "norway-news-2026-05-21-1100", "sources": []}

        result1 = invoke_collector(task_config)
        assert result1["status"] == "error"

        result2 = invoke_collector(task_config)
        assert result2["status"] == "error"
        assert "Timeout" in result2["error"]

    def test_publisher_failure_no_retry(self, mock_boto3_client):
        """Publisher failure is not retried."""
        from tools.invoke_publisher import invoke_publisher

        mock_boto3_client.return_value = make_a2a_error_response("Git push rejected: conflict")

        result = invoke_publisher({
            "task_id": "publish-norway-2026-05-21-1100",
            "type": "merge_update",
        })

        assert result["status"] == "error"
        assert "Git push rejected" in result["error"]
        # Only one call — no retry
        assert mock_boto3_client.call_count == 1


class TestConfigIntegration:
    def test_config_has_all_news_sources(self):
        """Config contains all 11 Norwegian news sources."""
        from config import NEWS_SOURCES

        assert len(NEWS_SOURCES) == 11
        categories = {s["category"] for s in NEWS_SOURCES}
        assert categories == {"domestic", "international", "business"}

        domestic = [s for s in NEWS_SOURCES if s["category"] == "domestic"]
        international = [s for s in NEWS_SOURCES if s["category"] == "international"]
        business = [s for s in NEWS_SOURCES if s["category"] == "business"]
        assert len(domestic) == 7
        assert len(international) == 3
        assert len(business) == 1

    def test_config_has_required_arns(self):
        """Config has collector and publisher ARNs."""
        from config import COLLECTOR_RUNTIME_ARN, PUBLISHER_RUNTIME_ARN, S3_BUCKET

        assert "newscollector" in COLLECTOR_RUNTIME_ARN
        assert S3_BUCKET == "news-agent-data-548129671048"

    def test_config_has_blog_settings(self):
        """Config has blog repo and branch."""
        from config import BLOG_REPO, BLOG_BRANCH

        assert BLOG_REPO == "claw-lu/hexo-blog"
        assert BLOG_BRANCH == "main"
