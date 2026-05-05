from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from typing import Any, Dict, Optional

# Ensure `backend/` is on the import path when invoked by AWS Lambda.
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from models.request import VerifyRequest
from services.verification import verify_stub


def _json_response(status_code: int, payload: Any) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


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


def _get_header_value(event: Any, header_name: str) -> Optional[str]:
    """
    Extract header value from API Gateway proxy event shape.
    Header keys can be any case; we match case-insensitively.
    """

    if not isinstance(event, dict):
        return None

    headers = event.get("headers") or {}
    if not isinstance(headers, dict):
        return None

    target = header_name.lower()
    for k, v in headers.items():
        if isinstance(k, str) and k.lower() == target:
            return v if isinstance(v, str) else None

    return None


def _extract_payload(event: Any) -> Dict[str, Any]:
    """
    Supports the most common API Gateway proxy shape:
      - event["body"] (string or dict)
      - event["isBase64Encoded"] (optional)

    Also supports passing the request JSON directly as `event`.
    """

    if isinstance(event, dict) and "body" in event:
        body = event.get("body")
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")

        if isinstance(body, str):
            return json.loads(body)
        if isinstance(body, dict):
            return body

        raise ValueError("Unsupported event['body'] type.")

    if isinstance(event, dict):
        return event

    raise ValueError("Unsupported event shape for verification request.")


def lambda_handler(event: Any, context: Optional[Any] = None) -> dict:
    """
    Day 1 Lambda handler: validates input and returns the same stub response
    as `POST /verify` (no detection logic yet).
    """

    try:
        x_payment = _get_header_value(event, "x-payment")
        if not x_payment or x_payment.strip().lower() != "paid":
            return _json_response(402, _payment_required_payload())

        payload_dict = _extract_payload(event)
        request = VerifyRequest.model_validate(payload_dict)
        response = asyncio.run(verify_stub(request))
        return _json_response(200, response.model_dump(mode="json"))
    except Exception as exc:
        # Keep it simple for Day 1. Pydantic validation errors surface as 400.
        return _json_response(400, {"error": str(exc)})
