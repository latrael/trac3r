from __future__ import annotations

import os


def get_aws_region() -> str:
    return os.getenv("AWS_REGION", "us-east-1").strip() or "us-east-1"


def get_dynamodb_table_name() -> str:
    return os.getenv("DYNAMODB_TABLE", "trac3r-verifications").strip() or "trac3r-verifications"


def get_dynamodb_endpoint_url() -> str | None:
    """Optional override for local/test endpoints (moto / DynamoDB Local)."""
    value = os.getenv("DYNAMODB_ENDPOINT_URL", "").strip()
    return value or None
