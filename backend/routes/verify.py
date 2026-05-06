from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.request import VerifyRequest
from models.response import VerifyResponse
from services.verification import get_verification_result, verify_and_store

router = APIRouter(prefix="/verify", tags=["verify"])


@router.post("", response_model=VerifyResponse)
async def post_verify(body: VerifyRequest) -> VerifyResponse:
    # Payment is enforced by the x402 middleware in main.py. By the time
    # this handler runs, the X-PAYMENT header has been verified against the
    # facilitator and request.state.payment_payload is populated.
    return await verify_and_store(body)


@router.get("/{hash_value}")
async def get_verify(hash_value: str) -> dict:
    try:
        return await get_verification_result(hash_value)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
