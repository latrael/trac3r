"""Autonomous agent simulation for the TRAC3R demo.

The agent calls POST /verify before acting on a dataset. The /verify endpoint
is x402-gated, so the agent's HTTP session is wrapped with x402 payment
handling — on a 402 response it signs an EIP-3009 payment authorization with
the buyer's private key and retries automatically.

Required env (in .env at repo root):
    BUYER_KEY=0x...            # private key for the demo buyer wallet (Base Sepolia, funded with USDC + ETH)
    API_URL=http://localhost:8000   # optional, defaults to localhost

Run:
    pip install -r demo/requirements.txt
    python demo/agent_demo.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from eth_account import Account
from x402 import x402ClientSync
from x402.http.clients.requests import wrapRequestsWithPayment
from x402.mechanisms.evm.exact import ExactEvmClientScheme
from x402.mechanisms.evm.signers import EthAccountSigner

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_data import clean_dataset, tampered_dataset  # noqa: E402

API_URL = os.environ.get("API_URL", "http://localhost:8000")
NETWORK = os.environ.get("X402_NETWORK", "eip155:84532")  # Base Sepolia
TRUST_THRESHOLD = 0.70


def _build_session() -> requests.Session:
    key = os.environ.get("BUYER_KEY")
    if not key:
        raise SystemExit("BUYER_KEY not set in .env — cannot sign x402 payments.")

    account = Account.from_key(key)
    signer = EthAccountSigner(account)
    client = x402ClientSync()
    client.register(NETWORK, ExactEvmClientScheme(signer=signer))
    return wrapRequestsWithPayment(requests.Session(), client)


def agent_decision(label: str, session: requests.Session, dataset: list[dict]) -> bool:
    payload = {"algorithm": "trac3r-v1", "dataset": dataset}

    try:
        response = session.post(f"{API_URL}/verify", json=payload, timeout=60)
    except requests.RequestException as exc:
        print(f"[{label}] Network error contacting {API_URL}: {exc}")
        return False

    if response.status_code != 200:
        print(f"[{label}] {response.status_code} {response.reason}: {response.text[:300]}")
        return False

    result = response.json()
    score = result.get("trustScore")
    flags = result.get("flags", [])
    status = result.get("status", "unknown")
    explanation = result.get("explanation", "N/A")

    print(f"--- {label} ---")
    settle_header = response.headers.get("x-payment-response") or response.headers.get(
        "X-PAYMENT-RESPONSE"
    )
    if settle_header:
        print(f"Payment settled: {settle_header[:80]}…")

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
    session = _build_session()
    print(f"Calling TRAC3R at {API_URL} (network={NETWORK})\n")
    agent_decision("Clean Data", session, clean_dataset)
    print()
    agent_decision("Tampered Data", session, tampered_dataset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
