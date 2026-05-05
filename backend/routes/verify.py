from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from models.request import VerifyRequest
from models.response import VerifyResponse
from services.verification import verify_stub

router = APIRouter(prefix="/verify", tags=["verify"])


def _payment_required_payload() -> dict:
    # Day 1 mock: Backend Engineer 3 owns full x402 wiring.
    return {
        "error": "Payment required",
        "x402": {
            "version": 1,
            "accepts": [
                {
                    "scheme": "exact",
                    "network": "base",
                    "maxAmountRequired": "0.01",
                    "asset": "USDC",
                }
            ],
            "memo": "trac3r-verification",
        },
    }


@router.post("", response_model=VerifyResponse)
async def post_verify(
    body: VerifyRequest,
    x_payment: Optional[str] = Header(default=None, alias="x-payment"),
) -> VerifyResponse:
    if not x_payment or x_payment.strip().lower() != "paid":
        return JSONResponse(status_code=402, content=_payment_required_payload())

    return await verify_stub(body)


@router.get("/{hash_value}")
async def get_verify(hash_value: str) -> dict:
    raise HTTPException(
        status_code=501,
        detail="GET /verify/{hash} is not implemented yet (Day 2).",
    )