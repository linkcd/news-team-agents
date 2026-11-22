from unittest.mock import patch

import pytest


def test_collector_invocation_propagates_identity_user():
    from tools.invoke_collector import invoke_collector
    from config import COLLECTOR_RUNTIME_ARN

    with patch("tools.a2a_client.invoke_a2a", return_value={"status": "success"}) as invoke:
        invoke_collector({"task_id": "test"})
    invoke.assert_called_once_with(COLLECTOR_RUNTIME_ARN, {"task_id": "test"}, runtime_user_id="orchestrator")


def test_agent_refuses_to_start_without_required_configuration(monkeypatch):
    import config

    monkeypatch.setattr(config, "COLLECTOR_RUNTIME_ARN", "")
    with pytest.raises(ValueError, match="COLLECTOR_RUNTIME_ARN"):
        config.validate_configuration()


def test_runtime_arns_must_belong_to_the_same_account(monkeypatch):
    import config

    monkeypatch.setattr(config, "COLLECTOR_RUNTIME_ARN", f"arn:aws:bedrock-agentcore:eu-west-1:{'0' * 12}:runtime/collector-id")
    monkeypatch.setattr(config, "PUBLISHER_RUNTIME_ARN", f"arn:aws:bedrock-agentcore:eu-west-1:{'1' * 12}:runtime/publisher-id")
    monkeypatch.setattr(config, "BLOG_REPO", "example/blog")
    monkeypatch.setattr(config, "S3_BUCKET", "test-bucket")
    with pytest.raises(ValueError, match="same account"):
        config.validate_configuration()


def test_agent_factory_validates_configuration_before_constructing_model(monkeypatch):
    import agent
    import config

    monkeypatch.setattr(config, "COLLECTOR_RUNTIME_ARN", "")
    with patch.object(agent, "BedrockModel") as model:
        with pytest.raises(ValueError, match="COLLECTOR_RUNTIME_ARN"):
            agent.create_agent()
    model.assert_not_called()
