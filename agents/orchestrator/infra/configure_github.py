# Copyright 2026 news-agent contributors
# SPDX-License-Identifier: Apache-2.0
"""Create github-token in the selected account using a hidden terminal prompt."""
import argparse
from getpass import getpass
import json
from pathlib import Path

import boto3


def configure(session, config):
    account = session.client("sts").get_caller_identity()["Account"]
    if account != config["account"]:
        raise ValueError(f"CLI account {account} does not match deployment account {config['account']}")
    token = getpass(f"GitHub token for {config.get('blogRepo', 'the target repository')} (hidden): ").strip()
    if not token:
        raise ValueError("A GitHub token is required")
    result = session.client("bedrock-agentcore-control").create_api_key_credential_provider(
        name="github-token", apiKey=token,
    )
    return result["name"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()
    config = json.loads(Path(__file__).with_name("deployment.json").read_text())
    session = boto3.Session(profile_name=args.profile, region_name=config["region"])
    try:
        name = configure(session, config)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", type(exc).__name__)
        raise SystemExit(f"Credential setup failed ({code}). Existing providers are not overwritten.") from None
    print(f"Created {name} in account {config['account']} / {config['region']}.")


if __name__ == "__main__":
    main()
