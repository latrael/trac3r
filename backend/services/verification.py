from __future__ import annotations

from datetime import datetime, timezone

from models.request import VerifyRequest
from models.response import VerifyResponse


async def verify_stub(payload: VerifyRequest) -> VerifyResponse:
    # Day 1 stub: stable, hardcoded response for Backend Engineer 3 integration.
    return VerifyResponse(
        status="verified",
        trustScore=0.94,
        flags=[],
        hash="0xabc123...",
        algorithm=payload.algorithm,
        timestamp=datetime.now(timezone.utc),
    )