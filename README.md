# TRAC3R Backend

FastAPI service that verifies dataset integrity, scores trust, and persists
results to DynamoDB. `POST /verify` is gated by **real x402 payments on Base
Sepolia testnet** via the public Coinbase facilitator at
`https://x402.org/facilitator` — no API keys required.

## ⚠️ Teammate upgrade note (Python 3.13)

The official Coinbase `x402` Python SDK requires Python ≥ 3.10. Existing 3.9
venvs need to be recreated:

```bash
rm -rf backend/venv
/opt/homebrew/bin/python3.13 -m venv backend/venv   # or any python3.10+
backend/venv/bin/pip install -r backend/requirements.txt
backend/venv/bin/pip install -r demo/requirements.txt   # if running agent_demo.py
```

If you don't have python3.13, install via `brew install python@3.13` (mac) or
`apt install python3.13-venv` (linux).

## Implemented

- `POST /verify` — x402-gated. Returns 402 with payment requirements on first
  call; on retry with a valid `X-PAYMENT` header (signed EIP-3009 USDC
  authorization) runs detection, stores, and returns the scored response.
- `POST /agent/verify` — same payload, but the **server** acts as buyer using
  `BUYER_KEY` from `.env`. Used by the static frontend; lets you skip wallet
  integration in the browser.
- `GET /verify/{hash}` — fetches a stored verification by hash.
- `GET /health` — liveness check.
- Deterministic SHA-256 hashing in `backend/utils/hash.py` (`0x…` prefix)
- Supabase persistence via service-role key (table: `verifications`)
- Detection engine in `backend/engine/analyzer.py` (missing values, duplicate
  timestamps, gaps, value spikes, replay)

## Backend layout

```text
backend/
├── main.py
├── requirements.txt
├── requirements-dev.txt
├── routes/verify.py
├── models/{request,response}.py
├── engine/analyzer.py
├── services/verification.py
├── utils/hash.py
├── bedrock/explainer.py
└── config/settings.py
```

## Environment

Create `.env` at the repo root:

```env
# AWS (DynamoDB + S3)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# x402 buyer wallet — funded on Base Sepolia with USDC + ETH.
# Used by demo/agent_demo.py and POST /agent/verify.
BUYER_KEY=0x<private_key>

# x402 settings (defaults shown; override only if needed)
# X402_PAY_TO=0xe3cB5A3aC8dfdC9E67e8876bf99579BEe3db7Be3
# X402_PRICE=$0.01
# X402_NETWORK=eip155:84532          # Base Sepolia. Mainnet: eip155:8453
# X402_FACILITATOR_URL=https://x402.org/facilitator
# X402_ENABLED=true                  # set to false to disable the gate locally
```

`main.py` auto-loads `.env` via `python-dotenv`. **Never commit `.env`** — it
contains the buyer's private key.

### Funding the buyer wallet (Base Sepolia)

- Base Sepolia ETH: https://portal.cdp.coinbase.com/products/faucet
- Base Sepolia USDC: https://faucet.circle.com (pick "Base Sepolia")

### Supabase schema

Table `verifications`:

| column      | type        | notes                                |
|-------------|-------------|--------------------------------------|
| hash        | text (PK)   | `0x…` SHA-256                        |
| trustScore  | float8      | 0.0 – 1.0                            |
| status      | text        | `verified` or `flagged`              |
| flags       | jsonb       | array of strings                     |
| timestamp   | timestamptz | UTC                                  |
| algorithm   | text        | e.g. `trac3r-v1`                     |
| dataset     | jsonb       | original dataset rows                |

## Run locally

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Or from the repo root:

```bash
uvicorn backend.main:app --reload --port 8000
```

Base URL: `http://localhost:8000`

## Run tests

```bash
cd backend
source venv/bin/activate
pip install -r requirements-dev.txt
cd ..
python -m pytest tests/ -v
```

The integration tests mock Supabase, so they run offline.

## API

### `POST /verify`

Headers: `X-PAYMENT: <base64 EIP-3009 payload>` (required). The official `x402`
client libraries (Python, JS, Go, Rust) handle the 402 → sign → retry flow
automatically. See `demo/agent_demo.py` for the canonical Python example.

Request:
```json
{
  "dataset": [
    {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
    {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1250}
  ],
  "algorithm": "trac3r-v1"
}
```

Response (200):
```json
{
  "status": "verified",
  "trustScore": 0.94,
  "flags": [],
  "hash": "0xabc123...",
  "algorithm": "trac3r-v1",
  "timestamp": "2026-04-29T19:03:00Z"
}
```

`status` is normalized at the API layer to `verified` (trustScore ≥ 0.85) or
`flagged` (otherwise). The analyzer's internal `warning` band is not surfaced.

Response (402, no `X-PAYMENT` header): an empty body with a
`payment-required` response header (base64-encoded JSON) describing the
accepted payment options. The x402 client libraries decode this automatically.

### `POST /agent/verify`

Identical request/response to `POST /verify`, but the server pays on behalf of
the caller using `BUYER_KEY`. Use this from the browser frontend to avoid
wallet integration. Adds a `payment` block to the response.

### `GET /verify/{hash}`

| stored status | response                                                       |
|---------------|----------------------------------------------------------------|
| (none)        | `{"result": "not_found", "hash": "0x…"}`                       |
| `verified`    | `{"result": "match", "originalTimestamp": "…Z", "hash": "0x…"}` |
| `flagged`     | `{"result": "flagged", "originalTimestamp": "…Z", "hash": "0x…"}` |

## Quick checks

402 (no payment) — confirms the gate is active:
```bash
curl -i -X POST "http://localhost:8000/verify" \
  -H "Content-Type: application/json" \
  -d '{"dataset":[{"timestamp":"2026-04-29T19:00:00Z","source":"node1","value":1200}],"algorithm":"trac3r-v1"}'
```

End-to-end paid call via the agent helper (uses BUYER_KEY server-side):
```bash
curl -sS -X POST "http://localhost:8000/agent/verify" \
  -H "Content-Type: application/json" \
  -d '{"dataset":[{"timestamp":"2026-04-29T19:00:00Z","source":"node1","value":1200}],"algorithm":"trac3r-v1"}'
```

Real x402 round-trip from a Python client:
```bash
python demo/agent_demo.py
```

## Frontend

Static page at `frontend/index.html`. Calls `POST /agent/verify`, no wallet
required. Open it via `python -m http.server 5500 --directory frontend` and
visit `http://localhost:5500` (the page reads the API URL from `window.location.origin`
by default; override with `localStorage.setItem("trac3r-api","http://localhost:8000")`).
