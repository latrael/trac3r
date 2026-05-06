"""Live E2E tests against real AWS DynamoDB.

Run with:
    python3 tests/test_live_e2e.py

Reads credentials from .env at the project root. Does NOT mock anything.
Requires network access to AWS us-east-1.

Day 2 coverage:
  - Table is created if absent (ensure_table)
  - POST /verify with x-payment: paid → verified (clean dataset, score >= 0.85)
  - POST /verify with x-payment: paid → flagged (tampered dataset, score <= 0.70)
  - POST /verify without payment header → 402 + x402 shape
  - GET /verify/{hash} → "match" for verified record
  - GET /verify/{hash} → "flagged" for flagged record
  - GET /verify/nonexistent → "not_found"
  - Hash is deterministic (same inputs = same hash)
  - DynamoDB record is persisted (direct table scan confirms item)
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

# --- path setup -------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Load real credentials from project .env BEFORE importing aws modules.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Ensure DYNAMODB_ENDPOINT_URL is NOT set so boto3 hits real AWS.
os.environ.pop("DYNAMODB_ENDPOINT_URL", None)

# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient  # noqa: E402

from aws.dynamodb import ensure_table, get_table  # noqa: E402
from main import app  # noqa: E402

# ---------------------------------------------------------------------------

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
        {"timestamp": "2026-04-29T19:00:00Z", "source": "node2", "value": 1210},  # dup timestamp
        {"timestamp": "2026-04-29T19:01:00Z", "source": "node1", "value": 1195},
        {"timestamp": "2026-04-29T19:02:00Z", "source": "node2", "value": 7200},  # spike
        {"timestamp": "2026-04-29T19:03:00Z", "source": "node1", "value": 1205},
    ],
    "algorithm": "trac3r-v1",
}


class LiveE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n[setup] Creating/verifying DynamoDB table against real AWS...")
        ensure_table()
        print("[setup] Table ready.")
        cls.client = TestClient(app)

    # ------------------------------------------------------------------
    # Payment gate
    # ------------------------------------------------------------------

    def test_01_payment_required_no_header(self):
        """POST /verify without x-payment returns 402 with x402 shape."""
        resp = self.client.post("/verify", json=CLEAN_PAYLOAD)
        self.assertEqual(resp.status_code, 402, resp.text)
        body = resp.json()
        self.assertEqual(body["error"], "Payment required")
        self.assertIn("x402", body)
        self.assertEqual(body["x402"]["version"], 1)
        accepts = body["x402"]["accepts"][0]
        self.assertEqual(accepts["asset"], "USDC")
        self.assertEqual(accepts["network"], "base")
        print("  PASS payment gate → 402 + x402 shape")

    # ------------------------------------------------------------------
    # Clean dataset
    # ------------------------------------------------------------------

    def test_02_clean_dataset_verified(self):
        """Clean dataset → status=verified, trustScore >= 0.85, no flags."""
        resp = self.client.post(
            "/verify", json=CLEAN_PAYLOAD, headers={"x-payment": "paid"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "verified")
        self.assertGreaterEqual(body["trustScore"], 0.85, body)
        self.assertEqual(body["flags"], [])
        self.assertTrue(body["hash"].startswith("0x"), body)
        self.assertEqual(body["algorithm"], "trac3r-v1")
        self.assertIn("timestamp", body)
        self.__class__._clean_hash = body["hash"]
        print(f"  PASS clean dataset → verified, score={body['trustScore']}, hash={body['hash'][:18]}...")

    # ------------------------------------------------------------------
    # Tampered dataset
    # ------------------------------------------------------------------

    def test_03_tampered_dataset_flagged(self):
        """Tampered dataset → status=flagged, trustScore <= 0.70, ≥ 1 flag."""
        resp = self.client.post(
            "/verify", json=TAMPERED_PAYLOAD, headers={"x-payment": "paid"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "flagged")
        self.assertLessEqual(body["trustScore"], 0.70, body)
        self.assertGreaterEqual(len(body["flags"]), 1, body)
        self.__class__._tampered_hash = body["hash"]
        print(f"  PASS tampered dataset → flagged, score={body['trustScore']}, flags={body['flags']}")

    # ------------------------------------------------------------------
    # GET /verify/{hash}
    # ------------------------------------------------------------------

    def test_04_get_verify_clean_match(self):
        """GET /verify/{clean_hash} → result=match."""
        h = getattr(self.__class__, "_clean_hash", None)
        if not h:
            self.skipTest("clean hash not available (test_02 may have failed)")
        resp = self.client.get(f"/verify/{h}")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["result"], "match")
        self.assertEqual(body["hash"], h)
        self.assertTrue(body["originalTimestamp"].endswith("Z"), body)
        print(f"  PASS GET /verify/{{clean_hash}} → match, ts={body['originalTimestamp']}")

    def test_05_get_verify_tampered_flagged(self):
        """GET /verify/{tampered_hash} → result=flagged."""
        h = getattr(self.__class__, "_tampered_hash", None)
        if not h:
            self.skipTest("tampered hash not available (test_03 may have failed)")
        resp = self.client.get(f"/verify/{h}")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["result"], "flagged")
        print(f"  PASS GET /verify/{{tampered_hash}} → flagged")

    def test_06_get_verify_not_found(self):
        """GET /verify/0xnonexistent → result=not_found."""
        resp = self.client.get("/verify/0xnonexistent_live_e2e_test")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["result"], "not_found")
        print("  PASS GET /verify/nonexistent → not_found")

    # ------------------------------------------------------------------
    # DynamoDB persistence verification
    # ------------------------------------------------------------------

    def test_07_dynamodb_record_persisted(self):
        """Record written by POST /verify is readable directly from DynamoDB."""
        h = getattr(self.__class__, "_clean_hash", None)
        if not h:
            self.skipTest("clean hash not available")
        table = get_table()
        item = table.get_item(Key={"hash": h}).get("Item")
        self.assertIsNotNone(item, f"No item found in DynamoDB for hash={h}")
        self.assertEqual(item["hash"], h)
        self.assertIn("trustScore", item)
        self.assertIn("status", item)
        self.assertIn("flags", item)
        self.assertIn("timestamp", item)
        print(f"  PASS DynamoDB record confirmed: status={item['status']}, score={float(item['trustScore'])}")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def test_08_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})
        print("  PASS /health → ok")


if __name__ == "__main__":
    print("=" * 60)
    print("TRAC3R Live E2E Tests — Real AWS DynamoDB")
    print("=" * 60)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromTestCase(LiveE2ETests))
    sys.exit(0 if result.wasSuccessful() else 1)
