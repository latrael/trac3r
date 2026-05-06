from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aws.dynamodb import get_verification_record, put_verification_record
from engine.analyzer import analyze
from models.request import VerifyRequest
from models.response import VerifyResponse
from utils.hash import generate_hash


def _dataset_to_storage_payload(payload: VerifyRequest) -> list[dict]:
    return [row.model_dump(mode="json") for row in payload.dataset]


def _status_from_trust_score(trust_score: float) -> str:
    return "verified" if trust_score >= 0.85 else "flagged"


def _format_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_stored_timestamp(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc).replace(microsecond=0)
    return parsed.isoformat().replace("+00:00", "Z")


async def verify_and_store(payload: VerifyRequest) -> VerifyResponse:
    dataset_payload = _dataset_to_storage_payload(payload)
    analysis = analyze(dataset_payload)

    trust_score = float(analysis["trustScore"])
    flags = list(analysis["flags"])
    status = _status_from_trust_score(trust_score)
    timestamp = datetime.now(timezone.utc)
    verification_hash = generate_hash(
        dataset=dataset_payload,
        trustScore=trust_score,
        flags=flags,
        algorithm=payload.algorithm,
        timestamp=timestamp,
        status=status,
    )

    record = {
        "hash": verification_hash,
        "trustScore": trust_score,
        "status": status,
        "flags": flags,
        "timestamp": _format_z(timestamp),
        "algorithm": payload.algorithm,
        "dataset": dataset_payload,
    }
    put_verification_record(record)

    return VerifyResponse(
        status=status,
        trustScore=trust_score,
        flags=flags,
        hash=verification_hash,
        algorithm=payload.algorithm,
        timestamp=timestamp,
    )


async def get_verification_result(hash_value: str) -> dict[str, Any]:
    record = get_verification_record(hash_value)
    if not record:
        return {"result": "not_found", "hash": hash_value}

    status = str(record.get("status", "")).lower()
    result = "flagged" if status == "flagged" else "match"
    return {
        "result": result,
        "originalTimestamp": _normalize_stored_timestamp(record.get("timestamp")),
        "hash": record.get("hash", hash_value),
    }
