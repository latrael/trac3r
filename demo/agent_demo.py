"""Autonomous agent simulation for the TRAC3R demo.

The agent calls POST /verify before acting on a dataset. If the trust score
clears 0.70 it proceeds; otherwise it refuses and prints the flags + Bedrock
explanation.

Setup:
    pip install -r demo/requirements.txt

Run:
    python demo/agent_demo.py
    API_URL=https://your-gateway/verify-base python demo/agent_demo.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_data import clean_dataset, tampered_dataset  # noqa: E402

API_URL = os.environ.get("API_URL", "http://localhost:8000")
PAYMENT_HEADER = os.environ.get("X_PAYMENT", "mock-x402-payload")
TRUST_THRESHOLD = 0.70


def agent_decision(label: str, dataset: list[dict]) -> bool:
    payload = {"algorithm": "trac3r-v1", "dataset": dataset}
    headers = {"Content-Type": "application/json", "X-PAYMENT": PAYMENT_HEADER}

    try:
        response = requests.post(
            f"{API_URL}/verify", json=payload, headers=headers, timeout=30
        )
    except requests.RequestException as exc:
        print(f"[{label}] Network error contacting {API_URL}: {exc}")
        return False

    if response.status_code != 200:
        print(f"[{label}] {response.status_code} {response.reason}: {response.text}")
        return False

    result = response.json()
    score = result.get("trustScore")
    flags = result.get("flags", [])
    status = result.get("status", "unknown")
    explanation = result.get("explanation", "N/A")
    payment = result.get("payment", {})

    print(f"--- {label} ---")
    print(f"Payment: paid={payment.get('paid')} network={payment.get('network')} "
          f"amount={payment.get('amount')} {payment.get('asset')}")

    if score is None:
        print(f"[{label}] Response missing trustScore: {result}")
        return False

    if score >= TRUST_THRESHOLD:
        print(f"Agent proceeding. Trust score: {score}. Status: {status}.")
        if explanation != "N/A":
            print(f"  Explanation: {explanation}")
        return True

    print(f"Agent refused to act. Trust score: {score}. Status: {status}.")
    if flags:
        print(f"  Reason: {', '.join(flags)}")
    print(f"  Explanation: {explanation}")
    return False


def main() -> int:
    print(f"Calling TRAC3R at {API_URL}\n")
    agent_decision("Clean Data", clean_dataset)
    print()
    agent_decision("Tampered Data", tampered_dataset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
