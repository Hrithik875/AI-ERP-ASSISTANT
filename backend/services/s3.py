"""
AI ERP Assistant — S3 Service
===============================
S3 operations: upload, download, presigned URLs, bucket management.
"""

import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from config import S3_BUCKET_NAME, AWS_REGION

logger = logging.getLogger("erp-assistant")

# Reuse client across invocations (Lambda warm starts)
_s3_client = boto3.client("s3", region_name=AWS_REGION)


def get_s3_client():
    return _s3_client


def ensure_bucket_exists():
    """Create the S3 bucket if it doesn't exist."""
    try:
        _s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
    except ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code == 404:
            logger.info(f"Creating bucket {S3_BUCKET_NAME} in {AWS_REGION}")
            try:
                if AWS_REGION == "us-east-1":
                    _s3_client.create_bucket(Bucket=S3_BUCKET_NAME)
                else:
                    _s3_client.create_bucket(
                        Bucket=S3_BUCKET_NAME,
                        CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
                    )
                logger.info(f"Bucket {S3_BUCKET_NAME} created")
            except Exception as create_err:
                logger.error(f"Failed to create bucket: {create_err}")
        else:
            logger.error(f"Error checking bucket: {e}")


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to S3. Returns the S3 key."""
    try:
        _s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info(f"S3 upload: {key} ({len(data)} bytes)")
        return key
    except ClientError as e:
        logger.error(f"S3 upload failed for {key}: {e}")
        raise


def download_bytes(key: str) -> bytes:
    """Download file bytes from S3."""
    try:
        response = _s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=key)
        data = response["Body"].read()
        logger.info(f"S3 download: {key} ({len(data)} bytes)")
        return data
    except ClientError as e:
        logger.error(f"S3 download failed for {key}: {e}")
        raise


def get_presigned_url(key: str, expiration: int = 3600) -> str:
    """Generate a presigned URL for S3 object access."""
    try:
        url = _s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET_NAME, "Key": key},
            ExpiresIn=expiration,
        )
        return url
    except ClientError as e:
        logger.error(f"Presigned URL generation failed for {key}: {e}")
        raise


def delete_object(key: str):
    """Delete an object from S3."""
    try:
        _s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=key)
        logger.info(f"S3 delete: {key}")
    except ClientError as e:
        logger.error(f"S3 delete failed for {key}: {e}")
        raise
