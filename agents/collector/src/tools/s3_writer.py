import json

import boto3
from strands import tool


@tool
def write_to_s3(bucket: str, key: str, data: str) -> dict:
    """Write JSON data to an S3 bucket.

    Args:
        bucket: S3 bucket name
        key: S3 object key (path)
        data: JSON string to write

    Returns:
        Dict with status, key, and error if any
    """
    try:
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType="application/json",
        )
        return {"status": "success", "key": key}
    except Exception as e:
        return {"status": "error", "error": str(e), "key": key}
