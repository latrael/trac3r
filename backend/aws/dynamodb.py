"""DynamoDB persistence for verification records.

Single table: ``trac3r-verifications`` (configurable via ``DYNAMODB_TABLE``).
Partition key: ``hash`` (String).

Numeric values are stored as DynamoDB ``Number`` (Decimal) and converted back
to ``float`` on read. Nested lists / maps (``flags``, ``dataset``) round-trip
as native DynamoDB List / Map types.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from config.settings import (
    get_aws_region,
    get_dynamodb_endpoint_url,
    get_dynamodb_table_name,
)


def _resource():
    kwargs = {"region_name": get_aws_region()}
    endpoint = get_dynamodb_endpoint_url()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.resource("dynamodb", **kwargs)


def get_table():
    return _resource().Table(get_dynamodb_table_name())


def ensure_table() -> None:
    """Idempotently create the verifications table if it does not exist.

    Uses on-demand (PAY_PER_REQUEST) billing so no capacity planning is needed.
    """

    name = get_dynamodb_table_name()
    res = _resource()
    client = res.meta.client
    try:
        client.describe_table(TableName=name)
        return
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise

    res.create_table(
        TableName=name,
        KeySchema=[{"AttributeName": "hash", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "hash", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    client.get_waiter("table_exists").wait(TableName=name)


def _to_dynamo(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    return value


def _from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        as_int = int(value)
        return as_int if Decimal(as_int) == value else float(value)
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    return value


def put_verification_record(record: dict) -> None:
    get_table().put_item(Item=_to_dynamo(record))


def get_verification_record(hash_value: str) -> Optional[dict]:
    response = get_table().get_item(Key={"hash": hash_value})
    item = response.get("Item")
    if not item:
        return None
    return _from_dynamo(item)
