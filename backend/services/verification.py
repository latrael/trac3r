from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from config.settings import get_supabase_service_role_key, get_supabase_url
from engine.analyzer import analyze
from models.request import VerifyRequest
from models.response import VerifyResponse
from supabase import Client, create_client
from utils.hash import generate_hash


def _build_supabase_client() -> Client:
    return create_client(get_supabase_url(), get_supabase_service_role_key())


def _dataset_to_storage_payload(payload: VerifyRequest) -> list[dict]:
    return [row.model_dump(mode="json") for row in payload.dataset]


def _status_from_trust_score(trust_score: float) -> str:
    return "verified" if trust_score >= 0.85 else "flagged"


def _save_verification_record(client: Client, record: dict) -> None:
    client.table("verifications").insert(record).execute()


def _fetch_verification_record(client: Client, hash_value: str) -> Optional[dict]:
    result = (
        client.table("verifications")
        .select("hash,status,timestamp")
        .eq("hash", hash_value)
        .limit(1)
        .execute()
    )
    rows = getattr(result, "data", None) or []
    if not rows:
        return None
    return rows[0]


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
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "algorithm": payload.algorithm,
        "dataset": dataset_payload,
    }
    _save_verification_record(_build_supabase_client(), record)

    response_status = "verified" if status == "verified" else "flagged"
    return VerifyResponse(
        status=response_status,
        trustScore=trust_score,
        flags=flags,
        hash=verification_hash,
        algorithm=payload.algorithm,
        timestamp=timestamp,
    )


async def get_verification_result(hash_value: str) -> dict[str, Any]:
    record = _fetch_verification_record(_build_supabase_client(), hash_value)
    if not record:
        return {"result": "not_found", "hash": hash_value}

    status = str(record.get("status", "")).lower()
    result = "flagged" if status == "flagged" else "match"
    return {
        "result": result,
        "originalTimestamp": record.get("timestamp"),
        "hash": record.get("hash", hash_value),
    }


async def verify_stub(payload: VerifyRequest) -> VerifyResponse:
    # Backwards-compatible alias to avoid breaking existing imports.
    return await verify_and_store(payload)