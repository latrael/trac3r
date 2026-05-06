"""Offline tests for the x402 payment gate on POST /verify.

These tests stand up the FastAPI app with the x402 middleware enabled but
patch the facilitator client so no network calls are made. They verify:
  - An unpaid request returns 402 with a base64 `payment-required` header
    that decodes to a v2 payload pointing at Base Sepolia USDC and our payTo.
  - GET routes (e.g. /verify/{hash}, /health) are not gated.

Real round-trip behaviour (signing, settlement) is covered by
tests/test_live_e2e.py, which hits the public Base Sepolia facilitator.
"""
from __future__ import annotations

import base64
import importlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["DYNAMODB_TABLE"] = "trac3r-verifications-test"
os.environ["X402_ENABLED"] = "true"
os.environ["X402_PAY_TO"] = "0xe3cB5A3aC8dfdC9E67e8876bf99579BEe3db7Be3"
os.environ["X402_PRICE"] = "$0.01"
os.environ["X402_NETWORK"] = "eip155:84532"

# Stub facilitator support so the middleware can resolve the USDC asset
# address without network access. Returned shape mirrors a real /supported
# response from the public facilitator.
from x402.http.facilitator_client import HTTPFacilitatorClient  # noqa: E402
from x402.schemas.responses import SupportedResponse  # noqa: E402

_FAKE_SUPPORTED = SupportedResponse.model_validate(
    {
        "kinds": [
            {
                "x402Version": 2,
                "scheme": "exact",
                "network": "eip155:84532",
                "extra": {
                    "feePayer": "facilitator",
                    "feeBps": 0,
                    "asset": {
                        "address": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
                        "decimals": 6,
                        "eip712": {"name": "USDC", "version": "2"},
                    },
                },
            }
        ]
    }
)

PAYLOAD = {
    "algorithm": "trac3r-v1",
    "dataset": [
        {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200}
    ],
}


class X402GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def fake_supported(self):
            return _FAKE_SUPPORTED

        cls._supported_patch = patch.object(
            HTTPFacilitatorClient, "get_supported", fake_supported
        )
        cls._supported_patch.start()

        # Reload main so the middleware is built with our env + the patch.
        for mod in [m for m in list(sys.modules) if m == "main" or m.startswith("main.")]:
            del sys.modules[mod]
        cls.main = importlib.import_module("main")

        from fastapi.testclient import TestClient

        cls.client = TestClient(cls.main.app)

    @classmethod
    def tearDownClass(cls):
        cls._supported_patch.stop()

    def test_unpaid_post_verify_returns_402(self):
        resp = self.client.post("/verify", json=PAYLOAD)
        self.assertEqual(resp.status_code, 402, resp.text)

    def test_402_response_has_payment_required_header(self):
        resp = self.client.post("/verify", json=PAYLOAD)
        header = resp.headers.get("payment-required")
        self.assertIsNotNone(header, "payment-required header missing on 402")

        decoded = json.loads(base64.b64decode(header))
        self.assertEqual(decoded["x402Version"], 2)
        self.assertEqual(decoded["error"], "Payment required")
        accepts = decoded["accepts"]
        self.assertEqual(len(accepts), 1)

        opt = accepts[0]
        self.assertEqual(opt["scheme"], "exact")
        self.assertEqual(opt["network"], "eip155:84532")
        self.assertEqual(
            opt["payTo"].lower(),
            "0xe3cB5A3aC8dfdC9E67e8876bf99579BEe3db7Be3".lower(),
        )
        # $0.01 USDC = 10000 atomic units (6 decimals)
        self.assertEqual(opt["amount"], "10000")
        self.assertEqual(
            opt["asset"].lower(),
            "0x036CbD53842c5426634e7929541eC2318f3dCF7e".lower(),
        )

    def test_health_is_not_gated(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_get_verify_hash_is_not_gated(self):
        resp = self.client.get("/verify/0xdoesnotexist")
        # Not gated → reaches the route. Body may surface a 500 if AWS is
        # unreachable, but that's a separate concern; the gate test passes
        # as long as we don't get 402.
        self.assertNotEqual(resp.status_code, 402)


if __name__ == "__main__":
    unittest.main()
