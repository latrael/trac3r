"""Live E2E tests against real AWS DynamoDB + real x402 on Base Sepolia.

Run with:
    python tests/test_live_e2e.py

Reads credentials from .env at the project root (AWS_* and BUYER_KEY).
Each "verified" or "flagged" call below burns ~$0.01 of testnet USDC from
the buyer wallet. Faucet links:
  - Base Sepolia ETH:  https://portal.cdp.coinbase.com/products/faucet
  - Base Sepolia USDC: https://faucet.circle.com (network: Base Sepolia)

Coverage:
  - DynamoDB table is created if absent
  - POST /verify with no payment → 402 + payment-required header
  - POST /verify signed via x402 client → verified (clean) / flagged (tampered)
  - GET /verify/{hash} → match / flagged / not_found
  - DynamoDB record is persisted (direct table scan)
"""
from __future__ import annotations

import base64
import json
import os
import sys
import unittest
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

os.environ.pop("DYNAMODB_ENDPOINT_URL", None)
os.environ.setdefault("X402_ENABLED", "true")
os.environ.setdefault("X402_NETWORK", "eip155:84532")

from eth_account import Account  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from x402 import x402ClientSync  # noqa: E402
from x402.mechanisms.evm.exact import ExactEvmClientScheme  # noqa: E402
from x402.mechanisms.evm.signers import EthAccountSigner  # noqa: E402

from aws.dynamodb import ensure_table, get_table  # noqa: E402
from main import app  # noqa: E402


CLEAN_PAYLOAD = {
    "dataset": [
        {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
        {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1210},
        {"timestamp": "2026-04-29T19:02:00Z", "source": "node1", "value": 1195},
        {"timestamp": "2026-04-29T19:03:00Z", "source": "node2", "value": 1205},
        {"timestamp": "2026-04-29T19:04:00Z", "source": "node1", "value": 1198},
    ],
    "algorithm": "trac3r-v1",
}

TAMPERED_PAYLOAD = {
    "dataset": [
        {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
        {"timestamp": "2026-04-29T19:00:00Z", "source": "node2", "value": 1210},
        {"timestamp": "2026-04-29T19:01:00Z", "source": "node1", "value": 1195},
        {"timestamp": "2026-04-29T19:02:00Z", "source": "node2", "value": 7200},
        {"timestamp": "2026-04-29T19:03:00Z", "source": "node1", "value": 1205},
    ],
    "algorithm": "trac3r-v1",
}


def _build_x402_client() -> x402ClientSync:
    key = os.environ.get("BUYER_KEY")
    if not key:
        raise unittest.SkipTest("BUYER_KEY not set in .env — skipping live e2e.")
    account = Account.from_key(key)
    signer = EthAccountSigner(account)
    client = x402ClientSync()
    client.register(os.environ["X402_NETWORK"], ExactEvmClientScheme(signer=signer))
    return client


def _signed_post(test_client: TestClient, x402: x402ClientSync, path: str, json_body):
    """POST then, on 402, sign payment from the response and retry once."""
    first = test_client.post(path, json=json_body)
    if first.status_code != 402:
        return first
    headers = {k.lower(): v for k, v in first.headers.items()}
    payment_headers, _ = (
        # x402HTTPClientSync wraps x402ClientSync to do header decoding
        __import__("x402.http", fromlist=["x402HTTPClientSync"]).x402HTTPClientSync(x402)
    ).handle_402_response(headers, first.content)
    return test_client.post(path, json=json_body, headers=payment_headers)


class LiveE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n[setup] Verifying DynamoDB table on real AWS…")
        ensure_table()
        print("[setup] Table ready.")
        cls.client = TestClient(app)
        cls.x402 = _build_x402_client()

    # ------------------------------------------------------------------
    # Payment gate
    # ------------------------------------------------------------------

    def test_01_payment_required_no_header(self):
        """POST /verify without payment → 402 + payment-required header (v2)."""
        resp = self.client.post("/verify", json=CLEAN_PAYLOAD)
        self.assertEqual(resp.status_code, 402, resp.text)

        header = resp.headers.get("payment-required")
        self.assertIsNotNone(header, "payment-required header missing on 402")
        decoded = json.loads(base64.b64decode(header))
        self.assertEqual(decoded["x402Version"], 2)
        opt = decoded["accepts"][0]
        self.assertEqual(opt["scheme"], "exact")
        self.assertEqual(opt["network"], "eip155:84532")
        self.assertEqual(opt["amount"], "10000")
        print(f"  PASS payment gate → 402 v2, payTo={opt['payTo']}")

    # ------------------------------------------------------------------
    # Clean dataset (real x402 sign + retry)
    # ------------------------------------------------------------------

    def test_02_clean_dataset_verified(self):
        resp = _signed_post(self.client, self.x402, "/verify", CLEAN_PAYLOAD)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "verified")
        self.assertGreaterEqual(body["trustScore"], 0.85, body)
        self.assertEqual(body["flags"], [])
        self.assertTrue(body["hash"].startswith("0x"), body)
        self.assertEqual(body["algorithm"], "trac3r-v1")
        self.__class__._clean_hash = body["hash"]
        print(
            f"  PASS clean → verified, score={body['trustScore']}, "
            f"hash={body['hash'][:18]}…"
        )

    # ------------------------------------------------------------------
    # Tampered dataset (real x402 sign + retry)
    # ------------------------------------------------------------------

    def test_03_tampered_dataset_flagged(self):
        resp = _signed_post(self.client, self.x402, "/verify", TAMPERED_PAYLOAD)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "flagged")
        self.assertLessEqual(body["trustScore"], 0.70, body)
        self.assertGreaterEqual(len(body["flags"]), 1, body)
        self.__class__._tampered_hash = body["hash"]
        print(
            f"  PASS tampered → flagged, score={body['trustScore']}, "
            f"flags={len(body['flags'])}"
        )

    # ------------------------------------------------------------------
    # GET /verify/{hash}
    # ------------------------------------------------------------------

    def test_04_get_verify_clean_match(self):
        h = getattr(self.__class__, "_clean_hash", None)
        if not h:
            self.skipTest("clean hash not available (test_02 may have failed)")
        resp = self.client.get(f"/verify/{h}")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["result"], "match")
        self.assertEqual(body["hash"], h)
        self.assertTrue(body["originalTimestamp"].endswith("Z"), body)
        print(f"  PASS GET /verify/{{clean}} → match, ts={body['originalTimestamp']}")

    def test_05_get_verify_tampered_flagged(self):
        h = getattr(self.__class__, "_tampered_hash", None)
        if not h:
            self.skipTest("tampered hash not available (test_03 may have failed)")
        resp = self.client.get(f"/verify/{h}")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["result"], "flagged")
        print("  PASS GET /verify/{tampered} → flagged")

    def test_06_get_verify_not_found(self):
        resp = self.client.get("/verify/0xnonexistent_live_e2e_test")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["result"], "not_found")
        print("  PASS GET /verify/nonexistent → not_found")

    # ------------------------------------------------------------------
    # DynamoDB persistence verification
    # ------------------------------------------------------------------

    def test_07_dynamodb_record_persisted(self):
        h = getattr(self.__class__, "_clean_hash", None)
        if not h:
            self.skipTest("clean hash not available")
        table = get_table()
        item = table.get_item(Key={"hash": h}).get("Item")
        self.assertIsNotNone(item, f"No item found in DynamoDB for hash={h}")
        self.assertEqual(item["hash"], h)
        for field in ("trustScore", "status", "flags", "timestamp"):
            self.assertIn(field, item)
        print(
            f"  PASS DynamoDB record confirmed: status={item['status']}, "
            f"score={float(item['trustScore'])}"
        )

    # ------------------------------------------------------------------
    # /agent/verify (server-side payment helper)
    # ------------------------------------------------------------------

    def test_08_agent_verify_pays_internally(self):
        """POST /agent/verify uses BUYER_KEY server-side; no headers needed."""
        resp = self.client.post("/agent/verify", json=CLEAN_PAYLOAD)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "verified")
        self.assertIn("payment", body)
        self.assertEqual(body["payment"]["paid"], True)
        self.assertEqual(body["payment"]["network"], "eip155:84532")
        print("  PASS /agent/verify → verified with payment metadata")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def test_09_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})
        print("  PASS /health → ok")


if __name__ == "__main__":
    print("=" * 60)
    print("TRAC3R Live E2E — Real AWS DynamoDB + Base Sepolia x402")
    print("=" * 60)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromTestCase(LiveE2ETests))
    sys.exit(0 if result.wasSuccessful() else 1)
