from __future__ import annotations

import os
from typing import Any, Dict, Optional


TABLE_NAME = os.getenv("DYNAMODB_TABLE", "trac3r-verifications")


def write_verification_record(record: Dict[str, Any]) -> None:
    """
    Day 1 placeholder for DynamoDB write.

    The actual boto3 wiring is owned later—this exists so Backend Engineer 3
    can integrate the function signature without us overbuilding today.
    """

    raise NotImplementedError(
        f"DynamoDB write placeholder (table={TABLE_NAME})."
    )


def read_verification_record(hash_value: str) -> Optional[Dict[str, Any]]:
    """
    Day 1 placeholder for DynamoDB read.
    """

    raise NotImplementedError(
        f"DynamoDB read placeholder (table={TABLE_NAME})."
    )
