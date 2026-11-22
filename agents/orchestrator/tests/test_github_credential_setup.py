import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def setup_module():
    path = Path(__file__).parents[1] / "infra/configure_github.py"
    spec = importlib.util.spec_from_file_location("configure_github", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_credential_setup_refuses_wrong_account_before_requesting_token(setup_module):
    session = MagicMock()
    session.client.return_value.get_caller_identity.return_value = {"Account": "1" * 12}
    with patch.object(setup_module, "getpass") as prompt:
        with pytest.raises(ValueError, match="account"):
            setup_module.configure(session, {"account": "0" * 12})
    prompt.assert_not_called()
    session.client.return_value.create_api_key_credential_provider.assert_not_called()


def test_credential_setup_passes_secret_directly_to_identity(setup_module):
    session = MagicMock()
    session.client.return_value.get_caller_identity.return_value = {"Account": "0" * 12}
    session.client.return_value.create_api_key_credential_provider.return_value = {"name": "github-token"}
    with patch.object(setup_module, "getpass", return_value="test-token"):
        result = setup_module.configure(session, {"account": "0" * 12})
    session.client.return_value.create_api_key_credential_provider.assert_called_once_with(
        name="github-token", apiKey="test-token",
    )
    assert result == "github-token"
