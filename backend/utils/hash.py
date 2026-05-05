from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable, List


def _normalize_datetime_to_z(dt: datetime) -> str:
    """
    Normalize datetime to a deterministic RFC3339-ish string ending with 'Z'.
    """

    if dt.tzinfo is None:
        # Assume UTC when no timezone info is provided.
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    # Example format expected by the role file: 2026-04-29T19:03:00Z
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_timestamp(ts: Any) -> str:
    """
    Accept a datetime or ISO-8601 string and return a deterministic '...Z' form.
    """

    if isinstance(ts, datetime):
        return _normalize_datetime_to_z(ts)

    if not isinstance(ts, str):
        raise TypeError(f"timestamp must be a datetime or ISO string, got: {type(ts).__name__}")

    raw = ts.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    dt = datetime.fromisoformat(raw)
    return _normalize_datetime_to_z(dt)


def _serialize_dataset(dataset: Iterable[dict]) -> str:
    """
    Serialize dataset deterministically.

    Expects each item to be a dict with at least:
      - timestamp (datetime or ISO string)
      - source (string)
      - value (JSON-serializable number)
    """

    normalized: List[dict] = []
    for item in dataset:
        ts = _normalize_timestamp(item["timestamp"])
        normalized.append(
            {
                "timestamp": ts,
                "source": item["source"],
                "value": item["value"],
            }
        )

    # Use JSON encoding to ensure stable ordering of fields.
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def generate_hash(
    dataset: Iterable[dict],
    trustScore: float,
    flags: Iterable[str],
    algorithm: str,
    timestamp: Any,
    status: str,
) -> str:
    """
    Deterministically generate a SHA-256 hash for a verification context.

    Hashes the following components (in order):
      dataset_serialized + trustScore + flags_sorted + algorithm + timestamp + status

    Returns:
      A hex string prefixed with '0x'.
    """

    dataset_serialized = _serialize_dataset(dataset)
    flags_sorted_serialized = json.dumps(sorted(list(flags)), separators=(",", ":"))
    trust_score_serialized = str(trustScore)
    algorithm_serialized = algorithm
    timestamp_serialized = _normalize_timestamp(timestamp)
    status_serialized = status

    raw = "".join(
        [
            dataset_serialized,
            trust_score_serialized,
            flags_sorted_serialized,
            algorithm_serialized,
            timestamp_serialized,
            status_serialized,
        ]
    )
    return "0x" + hashlib.sha256(raw.encode("utf-8")).hexdigest()