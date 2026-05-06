"""Frontend-friendly agent endpoint.

POST /agent/verify is NOT x402-gated. The server itself acts as the buyer:
it signs a Base Sepolia USDC payment with BUYER_KEY and proxies through to
the gated /verify endpoint. The browser frontend can call this without any
wallet integration.

The real x402 protocol demo is still exposed at POST /verify — use the
Postman collection or demo/agent_demo.py to see the 402 → sign → retry flow.
"""
from __future__ import annotations

import os
from typing import Any

import requests
from eth_account import Account
from fastapi import APIRouter, HTTPException, Request
from x402 import x402ClientSync
from x402.http.clients.requests import wrapRequestsWithPayment
from x402.mechanisms.evm.exact import ExactEvmClientScheme
from x402.mechanisms.evm.signers import EthAccountSigner

from config.settings import get_x402_network
from models.request import VerifyRequest

router = APIRouter(prefix="/agent", tags=["agent"])

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is not None:
        return _session

    key = os.environ.get("BUYER_KEY")
    if not key:
        raise HTTPException(
            status_code=500,
            detail="BUYER_KEY not configured on the server.",
        )

    account = Account.from_key(key)
    signer = EthAccountSigner(account)
    client = x402ClientSync()
    client.register(get_x402_network(), ExactEvmClientScheme(signer=signer))
    _session = wrapRequestsWithPayment(requests.Session(), client)
    return _session


@router.post("/verify")
def agent_verify(body: VerifyRequest, request: Request) -> dict[str, Any]:
    session = _get_session()
    base_url = str(request.base_url).rstrip("/")
    target = f"{base_url}/verify"

    try:
        response = session.post(target, json=body.model_dump(mode="json"), timeout=60)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Upstream error: {exc}") from exc

    settle_header = response.headers.get("x-payment-response") or response.headers.get(
        "X-PAYMENT-RESPONSE"
    )

    payload: dict[str, Any]
    try:
        payload = response.json()
    except ValueError:
        payload = {"error": response.text[:500]}

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=payload)

    payload["payment"] = {
        "paid": True,
        "network": get_x402_network(),
        "asset": "USDC",
        "amount": "0.01",
        "facilitator": "x402.org",
        "settlement": settle_header,
    }
    return payload
