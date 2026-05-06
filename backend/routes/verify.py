from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from models.request import VerifyRequest
from models.response import VerifyResponse
from services.verification import get_verification_result, verify_and_store

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

    return await verify_and_store(body)


@router.get("/{hash_value}")
async def get_verify(hash_value: str) -> dict:
    try:
        return await get_verification_result(hash_value)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc