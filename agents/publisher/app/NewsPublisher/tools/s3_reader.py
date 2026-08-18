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

import boto3
from strands import tool


@tool
def read_from_s3(bucket: str, key: str) -> dict:
    """Read and parse JSON content from an S3 bucket.

    Args:
        bucket: S3 bucket name
        key: S3 object key (path)

    Returns:
        Dict with status, parsed data, and error if any
    """
    try:
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read())
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "error": str(e)}
