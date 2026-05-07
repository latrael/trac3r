# TRAC3R: Paid Data Integrity Verification API for Autonomous Agents

TRAC3R is a four-component modular system that lets AI agents pay a tiny fee per request to verify that a dataset has not been tampered with before they act on it.

Each component is optimized for determinism, auditability, and demo clarity, while staying inside the constraints of a Lambda + DynamoDB stack and Coinbase's x402 payment protocol on Base.

---

## 🛠 Component 1: `backend/services/x402_gate.py`

### Purpose:
Mounts a real x402 payment middleware in front of `POST /verify`. Every call must be accompanied by a signed EIP-3009 USDC authorization on Base Sepolia, verified and settled by the public Coinbase facilitator at `https://x402.org/facilitator`.

### Key Functions:
- `build_payment_middleware()`:
  Constructs an `x402ResourceServer`, registers the `ExactEvmServerScheme` for `eip155:84532` (Base Sepolia), wires the public facilitator client, and returns a FastAPI middleware that gates `POST /verify`.

- `payment_middleware(routes, server)` (from the `x402` SDK):
  Inspects each request, returns `402 Payment Required` with a base64 `payment-required` header on the first call, then verifies and settles the signed `X-PAYMENT` header on the retry.

### Security:
- Private keys never touch the server for the public `/verify` path — clients sign with their own wallet, the facilitator does on-chain verification and settlement.
- Network and payTo address are pinned via env (`X402_NETWORK`, `X402_PAY_TO`); price is enforced by the middleware before any compute runs.

### Scalability:
- Switching to mainnet is a one-line env change (`X402_NETWORK=eip155:8453`).
- Multiple price tiers or routes can be added by extending the `routes` dict in `build_payment_middleware`.

---

## 🛠 Component 2: `backend/engine/analyzer.py`

### Purpose:
Runs five deterministic anomaly checks against a submitted dataset and returns a trust score in `[0.0, 1.0]` plus a list of human-readable flags.

### Key Functions:
- `analyze(dataset: list[dict]) -> {trustScore, flags, status}`:
  Aggregates per-check deductions starting from 1.0 and produces the final report.

- Per-check helpers: `check_missing_values`, `check_duplicate_timestamps`, `check_timestamp_gaps`, `check_value_spikes` (3× rolling median), `check_replayed_rows`.

### Security:
- No ML, no probabilistic models — every flag is reproducible from inputs.
- Status thresholds are enforced at the API layer: `verified` (≥ 0.85) or `flagged` (< 0.85). The analyzer's internal `warning` band is collapsed to keep the demo readable.

### Scalability:
- Each check is independent. Adding a new check is a single function plus a row in the scoring table — no rewiring required.

---

## 🛠 Component 3: `backend/aws/dynamodb.py` + `backend/utils/hash.py`

### Purpose:
Persists every verification as an auditable proof record so the same dataset can be re-checked later via `GET /verify/{hash}` and confirmed against an on-chain payment trail.

### Key Functions:
- `generate_hash(dataset, trustScore, flags, algorithm, timestamp, status) -> "0x<sha256>"`:
  Deterministic SHA-256 over the full verification context, sorted-key JSON serialized. Any single field change produces a new hash.

- `put_verification_record(record)` / `get_verification_record(hash)`:
  Writes the record to the `trac3r-verifications` DynamoDB table (partition key: `hash`) and reads it back for the lookup endpoint.

### Security:
- The hash binds dataset → trust score → flags → algorithm → timestamp → status. Mutating any of those without re-running verification produces a mismatched hash.
- IAM credentials are loaded only from `.env` at server start; no secret material is ever logged or returned.

### Scalability:
- DynamoDB partitioned by hash gives O(1) lookups under arbitrary load.
- A future S3 attachment for the raw dataset payload is a one-line addition.

---

## 🛠 Component 4: `backend/routes/agent.py` + `frontend/index.html`

### Purpose:
Provides a friendly demo surface that does not require a browser wallet plugin. The server holds a buyer key and signs payments on behalf of the static frontend, so judges can click two buttons and watch the protocol work.

### Key Functions:
- `POST /agent/verify`:
  Identical request/response to `POST /verify`, but the FastAPI handler signs the EIP-3009 authorization with `BUYER_KEY` and proxies the call through. Adds a `payment` block to the response.

- `frontend/index.html`:
  Single static page, no build step. Generates a clean and a tampered dataset on the fly, calls `/agent/verify`, and renders the score, status badge, flags, hash, and payment metadata.

### Security:
- `BUYER_KEY` is loaded from `.env` and never returned to the client.
- The real x402 protocol surface (`POST /verify`) remains payment-gated — the helper endpoint is purely a UX convenience.

### Demo Affordance:
- Postman and `demo/agent_demo.py` exercise the real signed-retry flow.
- The frontend exercises the verification + persistence flow without wallet friction.

---

## 🔒 Key Security Features

- **Deterministic Hashing**:
  Every verification is a SHA-256 of its full context, including the dataset, trust score, flags, and timestamp. Tampering with any field after the fact produces a different hash.

- **On-Chain Settlement**:
  Each call is paid in USDC on Base Sepolia and settled by Coinbase's public facilitator. The transaction is independently verifiable on Basescan.

- **No Plain-Text Secrets**:
  No private keys, API keys, or credentials are ever returned in API responses. `.env` is git-ignored.

- **Pre-Compute Gate**:
  Payment is verified before the detection engine runs and before anything is written to DynamoDB. A failed payment costs zero compute.

- **Reproducible Detection**:
  No randomness, no ML models. The same dataset always produces the same trust score and flags.

---

## 🔗 System Interaction Flow

1. An agent (or the demo frontend) submits a dataset to `POST /verify`.
2. The x402 middleware returns `402 Payment Required` with a base64 `payment-required` header naming the price (`$0.01 USDC`), network (`eip155:84532`), and payTo address.
3. The agent signs an EIP-3009 USDC authorization with its private key and retries with the `X-PAYMENT` header.
4. The middleware forwards the signed payload to the public facilitator, which verifies signature + balance and settles the transfer on Base Sepolia.
5. On success, the request reaches `verify_and_store(...)`:
   - `engine.analyze(dataset)` produces `trustScore` and `flags`.
   - `generate_hash(...)` computes the proof hash.
   - DynamoDB persists the full record.
6. The API returns the structured report. Later, anyone can call `GET /verify/{hash}` to confirm the proof exists.

---

## ✅ Final Summary

This architecture ensures that:
- Autonomous agents have a paid, machine-readable trust checkpoint they can call before acting on any dataset.
- Every verification is cryptographically bound to its inputs and persisted as an auditable record.
- Payment, verification, and persistence are all enforced server-side — the client only sees a single JSON response.
- The system runs entirely on testnet for demos and flips to mainnet via a single env variable.

---

## 🚀 Run Locally

```bash
# 1. Recreate the venv on Python 3.13 (the official x402 SDK requires ≥ 3.10)
rm -rf backend/venv
/opt/homebrew/bin/python3.13 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt -r demo/requirements.txt

# 2. Populate .env at the repo root
#    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
#    BUYER_KEY=0x<funded Base Sepolia private key>

# 3. Fund the buyer wallet
#    Base Sepolia ETH:  https://portal.cdp.coinbase.com/products/faucet
#    Base Sepolia USDC: https://faucet.circle.com  (network: Base Sepolia)

# 4. Start the API
backend/venv/bin/uvicorn main:app --app-dir backend --reload --port 8000

# 5. Start the static frontend (separate terminal)
python3 -m http.server 5500 --directory frontend
```

Open http://localhost:5500 and click either button to run a real x402 payment + verification round-trip.

### Quick checks

```bash
# Confirm the gate is active (returns 402 + payment-required header)
curl -i -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"trac3r-v1","dataset":[{"timestamp":"2026-04-29T19:00:00Z","source":"node1","value":1200}]}'

# Real signed payment via the agent script
backend/venv/bin/python demo/agent_demo.py

# Full offline test suite (20 tests)
backend/venv/bin/python -m pytest tests/test_integration.py tests/test_analyzer.py tests/test_x402_gate.py -v

# Live e2e: real Base Sepolia + real DynamoDB (~$0.02 of testnet USDC per run)
backend/venv/bin/python tests/test_live_e2e.py
```

---

## 🔗 Links

- Base Sepolia explorer: https://sepolia.basescan.org
- Base Sepolia USDC contract: `0x036CbD53842c5426634e7929541eC2318f3dCF7e`
- x402 facilitator: https://x402.org/facilitator
- x402 protocol: https://github.com/coinbase/x402
- Faucets: [ETH](https://portal.cdp.coinbase.com/products/faucet) · [USDC](https://faucet.circle.com)
