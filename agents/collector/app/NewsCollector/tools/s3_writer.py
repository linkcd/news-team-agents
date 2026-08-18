# Copyright 2026 news-agent contributors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import re

import boto3
from strands import tool


def _validate_and_fix_json(data: str) -> str:
    """Validate JSON string, attempting to fix common LLM output errors.

    Handles unescaped double quotes inside string values (e.g. Chinese
    quotation marks rendered as ASCII ").
    """
    try:
        parsed = json.loads(data)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        pass

    fixed = _fix_unescaped_quotes(data)
    parsed = json.loads(fixed)
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def _fix_unescaped_quotes(data: str) -> str:
    """Fix unescaped quotes inside JSON string values."""
    lines = data.split("\n")
    fixed_lines = []
    for line in lines:
        match = re.match(
            r'^(\s*"(?:summary_zh|title_zh|changelog|title_original)":\s*")(.*)(",?)$',
            line,
        )
        if match:
            prefix, value, suffix = match.group(1), match.group(2), match.group(3)
            value = re.sub(r'(?<!\\)"', '\\"', value)
            line = prefix + value + suffix
        fixed_lines.append(line)
    return "\n".join(fixed_lines)


@tool
def write_to_s3(bucket: str, key: str, data: str) -> dict:
    """Write JSON data to an S3 bucket.

    Validates JSON before writing. Attempts to fix common LLM output errors
    (unescaped quotes in string values). Fails if JSON cannot be repaired.

    Args:
        bucket: S3 bucket name
        key: S3 object key (path)
        data: JSON string to write

    Returns:
        Dict with status, key, and error if any
    """
    try:
        validated = _validate_and_fix_json(data)
    except (json.JSONDecodeError, ValueError) as e:
        return {"status": "error", "error": f"Invalid JSON: {e}", "key": key}

    try:
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=validated,
            ContentType="application/json",
        )
        return {"status": "success", "key": key}
    except Exception as e:
        return {"status": "error", "error": str(e), "key": key}
