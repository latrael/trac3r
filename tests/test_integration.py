"""Integration tests for the FastAPI /verify routes wired to DynamoDB.

DynamoDB is faked with moto, so the suite runs offline.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["DYNAMODB_TABLE"] = "trac3r-verifications-test"

from fastapi.testclient import TestClient  # noqa: E402
from moto import mock_aws  # noqa: E402

from aws.dynamodb import ensure_table  # noqa: E402
from main import app  # noqa: E402
from utils.hash import generate_hash  # noqa: E402


CLEAN_PAYLOAD = {
    "dataset": [
        {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
        {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1210},
        {"timestamp": "2026-04-29T19:02:00Z", "source": "node1", "value": 1190},
    ],
    "algorithm": "trac3r-v1",
}

TAMPERED_PAYLOAD = {
    "dataset": [
        {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
        {"timestamp": "2026-04-29T19:00:00Z", "source": "node2", "value": 1210},
        {"timestamp": "2026-04-29T19:01:00Z", "source": "node1", "value": 1190},
        {"timestamp": "2026-04-29T19:02:00Z", "source": "node2", "value": 7200},
    ],
    "algorithm": "trac3r-v1",
}


@mock_aws
class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        ensure_table()
        self.client = TestClient(app)

    def test_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_payment_required_returns_402_x402_shape(self):
        resp = self.client.post("/verify", json=CLEAN_PAYLOAD)
        self.assertEqual(resp.status_code, 402)
        body = resp.json()
        self.assertEqual(body["error"], "Payment required")
        self.assertIn("x402", body)
        self.assertEqual(body["x402"]["version"], 1)
        self.assertEqual(body["x402"]["accepts"][0]["asset"], "USDC")

    def test_verify_clean_returns_verified(self):
        resp = self.client.post(
            "/verify", json=CLEAN_PAYLOAD, headers={"x-payment": "paid"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "verified")
        self.assertGreaterEqual(body["trustScore"], 0.85)
        self.assertEqual(body["flags"], [])
        self.assertTrue(body["hash"].startswith("0x"))
        self.assertEqual(body["algorithm"], "trac3r-v1")
        self.assertIn("timestamp", body)

    def test_verify_tampered_returns_flagged(self):
        resp = self.client.post(
            "/verify", json=TAMPERED_PAYLOAD, headers={"x-payment": "paid"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "flagged")
        self.assertLessEqual(body["trustScore"], 0.70)
        self.assertGreaterEqual(len(body["flags"]), 1)

    def test_status_is_normalized_to_verified_or_flagged_only(self):
        warning_payload = {
            "dataset": [
                {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
                {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1210},
            ],
            "algorithm": "trac3r-v1",
        }
        resp = self.client.post(
            "/verify", json=warning_payload, headers={"x-payment": "paid"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn(resp.json()["status"], ("verified", "flagged"))

    def test_get_verify_not_found(self):
        resp = self.client.get("/verify/0xdoesnotexist")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(), {"result": "not_found", "hash": "0xdoesnotexist"}
        )

    def test_get_verify_match_after_post(self):
        post = self.client.post(
            "/verify", json=CLEAN_PAYLOAD, headers={"x-payment": "paid"}
        )
        h = post.json()["hash"]
        resp = self.client.get(f"/verify/{h}")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["result"], "match")
        self.assertEqual(body["hash"], h)
        self.assertTrue(body["originalTimestamp"].endswith("Z"))

    def test_get_verify_flagged_after_post(self):
        post = self.client.post(
            "/verify", json=TAMPERED_PAYLOAD, headers={"x-payment": "paid"}
        )
        h = post.json()["hash"]
        resp = self.client.get(f"/verify/{h}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["result"], "flagged")

    def test_hash_deterministic(self):
        dataset = CLEAN_PAYLOAD["dataset"]
        ts = "2026-04-29T19:03:00Z"
        a = generate_hash(
            dataset=dataset,
            trustScore=0.94,
            flags=[],
            algorithm="trac3r-v1",
            timestamp=ts,
            status="verified",
        )
        b = generate_hash(
            dataset=dataset,
            trustScore=0.94,
            flags=[],
            algorithm="trac3r-v1",
            timestamp=ts,
            status="verified",
        )
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("0x") and len(a) == 66)

        c = generate_hash(
            dataset=dataset,
            trustScore=0.93,
            flags=[],
            algorithm="trac3r-v1",
            timestamp=ts,
            status="verified",
        )
        self.assertNotEqual(a, c)


if __name__ == "__main__":
    unittest.main()
