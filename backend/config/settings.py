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


def get_x402_pay_to() -> str:
    return os.getenv("X402_PAY_TO", "0xe3cB5A3aC8dfdC9E67e8876bf99579BEe3db7Be3").strip()


def get_x402_price() -> str:
    return os.getenv("X402_PRICE", "$0.01").strip()


def get_x402_network() -> str:
    return os.getenv("X402_NETWORK", "eip155:84532").strip()


def get_x402_facilitator_url() -> str:
    return os.getenv("X402_FACILITATOR_URL", "https://x402.org/facilitator").strip()


def x402_enabled() -> bool:
    return os.getenv("X402_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
