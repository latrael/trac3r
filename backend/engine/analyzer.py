from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import statistics
from typing import Any


REQUIRED_FIELDS = ("timestamp", "value")


def analyze(dataset: list[dict]) -> dict:
    checks = (
        check_missing_values,
        check_duplicate_timestamps,
        check_timestamp_gaps,
        check_value_spikes,
        check_replayed_rows,
    )

    flags: list[str] = []
    total_deduction = 0.0

    for check in checks:
        check_flags, deduction = check(dataset)
        flags.extend(check_flags)
        total_deduction += deduction

    trust_score = round(max(0.0, min(1.0, 1.0 - total_deduction)), 2)

    return {
        "trustScore": trust_score,
        "flags": flags,
        "status": _status_for_score(trust_score),
    }


def check_missing_values(dataset: list[dict]) -> tuple[list[str], float]:
    affected_fields: dict[str, int] = defaultdict(int)
    fields = set(REQUIRED_FIELDS)

    for row in dataset:
        fields.update(row.keys())

    for row in dataset:
        for field in fields:
            value = row.get(field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                affected_fields[field] += 1

    flags = [
        f"Missing values detected: {field} is null in {count} rows"
        for field, count in sorted(affected_fields.items())
    ]
    return flags, round(len(flags) * 0.10, 2)


def check_duplicate_timestamps(dataset: list[dict]) -> tuple[list[str], float]:
    timestamps = [
        row.get("timestamp")
        for row in dataset
        if row.get("timestamp") not in (None, "")
    ]
    counts = Counter(timestamps)
    duplicates = [
        (timestamp, count)
        for timestamp, count in counts.items()
        if count >= 2
    ]

    flags = [
        f"Duplicate timestamp detected: {timestamp} appears {count} times"
        for timestamp, count in sorted(duplicates)
    ]
    return flags, round(len(flags) * 0.20, 2)


def check_timestamp_gaps(dataset: list[dict]) -> tuple[list[str], float]:
    parsed: list[tuple[int, datetime]] = []

    for index, row in enumerate(dataset, start=1):
        timestamp = row.get("timestamp")
        if not timestamp:
            continue
        try:
            parsed.append((index, _parse_timestamp(str(timestamp))))
        except ValueError:
            continue

    parsed.sort(key=lambda item: item[1])
    if len(parsed) < 3:
        return [], 0.0

    intervals = [
        (parsed[i][0], parsed[i + 1][0], (parsed[i + 1][1] - parsed[i][1]).total_seconds())
        for i in range(len(parsed) - 1)
    ]
    positive_intervals = [interval for _, _, interval in intervals if interval > 0]
    if not positive_intervals:
        return [], 0.0

    expected_interval = _most_common_interval(positive_intervals)

    for left_row, right_row, interval in intervals:
        if interval >= expected_interval * 2:
            return [
                f"Timestamp gap detected: missing interval between row {left_row} and row {right_row}"
            ], 0.20

    return [], 0.0


def check_value_spikes(dataset: list[dict]) -> tuple[list[str], float]:
    prior_values: list[float] = []

    for index, row in enumerate(dataset, start=1):
        value = _numeric_value(row.get("value"))
        if value is None:
            continue

        window = prior_values[-5:]
        if len(window) >= 3:
            median = statistics.median(window)
            if median > 0 and value > median * 3:
                pct_above = round((value / median - 1) * 100)
                return [
                    f"Major value spike detected: row {index} value is {pct_above}% above rolling median"
                ], 0.30

        prior_values.append(value)

    return [], 0.0


def check_replayed_rows(dataset: list[dict]) -> tuple[list[str], float]:
    seen: dict[tuple[tuple[str, Any], ...], int] = {}

    for index, row in enumerate(dataset, start=1):
        fingerprint = tuple(sorted(row.items()))
        original_index = seen.get(fingerprint)
        if original_index is not None:
            return [
                f"Replayed row detected: row {index} is an exact duplicate of row {original_index}"
            ], 0.30
        seen[fingerprint] = index

    return [], 0.0


def _status_for_score(score: float) -> str:
    if score >= 0.85:
        return "verified"
    if score >= 0.70:
        return "warning"
    return "flagged"


def _parse_timestamp(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _numeric_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _most_common_interval(intervals: list[float]) -> float:
    counts = Counter(intervals)
    return counts.most_common(1)[0][0]
