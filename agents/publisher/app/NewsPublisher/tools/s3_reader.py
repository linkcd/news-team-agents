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
