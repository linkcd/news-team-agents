import importlib.util
import json
from datetime import timedelta
from pathlib import Path

import pytest


@pytest.fixture
def observation():
    path = Path(__file__).parents[1] / "infra/observe_schedule.py"
    spec = importlib.util.spec_from_file_location("schedule_observation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_observation_window_contains_only_future_scheduled_slots(observation):
    start = observation.utc("2030-01-01T16:00:00Z")
    slots = observation.scheduled_slots(start, start + timedelta(hours=24))
    assert [s.isoformat() for s in slots] == [
        "2030-01-01T17:00:00+00:00", "2030-01-01T23:00:00+00:00",
        "2030-01-02T05:00:00+00:00", "2030-01-02T11:00:00+00:00",
    ]


def test_manual_or_other_slot_results_do_not_count_as_scheduled_success(observation):
    result = {"status": "success", "run_time": "2030-01-01T15:49:00Z"}
    assert observation.completed_result([json.dumps(result)], observation.utc("2030-01-01T17:00:00Z")) is None


def test_scheduled_receipt_allows_seconds_within_the_scheduled_minute(observation):
    slot = observation.utc("2030-01-01T17:00:00Z")
    assert observation.belongs_to_slot("2030-01-01T17:00:12Z", slot)
    assert not observation.belongs_to_slot("2030-01-01T17:01:00Z", slot)


def test_completion_parser_ignores_interleaved_health_logs(observation):
    slot = observation.utc("2030-01-01T17:00:00Z")
    messages = ['```json\n{\n', 'INFO: GET /ping HTTP/1.1 200 OK\n',
                '"status":"success",\n"run_time":"2030-01-01T17:00:00Z"\n}\n```']
    assert observation.completed_result(messages, slot)["status"] == "success"


def test_intermediate_parameters_are_not_mistaken_for_completion(observation):
    slot = observation.utc("2030-01-01T17:00:00Z")
    parameters = {"run_time": slot.isoformat(), "task_id": "example"}
    assert observation.completed_result([json.dumps(parameters)], slot) is None


def test_truncated_collection_key_can_be_reconstructed_for_external_verification(observation):
    slot = observation.utc("2030-01-01T17:00:00Z")
    damaged = '\n'.join([
        '```json', '{', '"status":"success",', '"run_time":"2030-01-01T17:00:00Z",',
        '"collection":{"new_topics":1,"updated_topics":0,', 'broken-tail-of-key"', '},',
        '"publish":' + json.dumps({"action": "merge_update", "file_path": "source/_posts/20300101-norway.md",
                                  "commit_sha": "a" * 40, "total_items_in_post": 3}), '}', '```',
    ])
    result = observation.completed_result([damaged], slot)
    assert result["log_reconstructed"] is True
    assert result["collection"]["data_key"] == "collections/2030-01-01/norway-news-2030-01-01-1700.json"
    assert result["publish"]["commit_sha"] == "a" * 40


def test_commit_evidence_must_match_the_scheduled_window_and_file(observation):
    slot = observation.utc("2030-01-01T17:00:00Z")
    path = "source/_posts/20300101-norway.md"
    commit = {"commit": {"committer": {"date": "2030-01-01T17:05:00Z"}}, "files": [{"filename": path}]}
    observation.validate_commit(commit, path, slot)
    with pytest.raises(ValueError):
        observation.validate_commit(commit, "unrelated.md", slot)
    commit["commit"]["committer"]["date"] = "2030-01-01T15:00:00Z"
    with pytest.raises(ValueError):
        observation.validate_commit(commit, path, slot)


def test_no_content_run_can_finish_without_publication(observation):
    result = {"status": "success", "collection": {"new_topics": 0, "updated_topics": 0}, "publish": None}
    observation.validate_result(result, {"new_items": [], "updated_items": []})


@pytest.mark.parametrize("bad", [
    {"status": "error"},
    {"status": "success", "dry_run": True},
    {"status": "success", "collection": {"new_topics": 0, "updated_topics": 0}, "publish": None},
])
def test_failure_dry_run_and_wrong_counts_are_not_success(observation, bad):
    with pytest.raises(ValueError):
        observation.validate_result(bad, {"new_items": [{}], "updated_items": []})


def test_public_page_counter_counts_only_numbered_topics(observation):
    assert observation.page_topic_count('<h3><a></a>1. News</h3><h3>Related posts</h3><h3>2. More</h3>') == 2
