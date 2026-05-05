# TRAC3R Backend - Day 1 Progress

This repository currently contains the Day 1 API Lead backend setup for TRAC3R.  
The focus is a working `POST /verify` stub with clean contracts for team integration.

## Implemented

- FastAPI backend scaffold in `backend/`
- `POST /verify` stub endpoint
  - Validates input with Pydantic (`dataset`, `algorithm`)
  - Returns structured hardcoded verification response
  - Does **not** call detection logic yet
- x402-style payment mock
  - Requires header `x-payment: paid`
  - Returns `HTTP 402` payment-required JSON when missing/invalid
- Deterministic SHA-256 utility in `backend/utils/hash.py`
  - Hashes `dataset`, `trustScore`, sorted `flags`, `algorithm`, `timestamp`, `status`
  - Returns hash prefixed with `0x`
- Day 1 AWS helper placeholders
  - `backend/aws/lambda_handler.py`
  - `backend/aws/dynamodb.py`

## Backend layout

```text
backend/
├── main.py
├── requirements.txt
├── routes/
│   └── verify.py
├── models/
│   ├── request.py
│   └── response.py
├── engine/
│   └── __init__.py
├── utils/
│   └── hash.py
├── aws/
│   ├── lambda_handler.py
│   └── dynamodb.py
├── services/
│   └── verification.py
└── config/
    └── settings.py
```

## Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Base URL: `http://localhost:8000`

## Test `POST /verify`

```bash
curl -sS -X POST "http://localhost:8000/verify" \
  -H "Content-Type: application/json" \
  -H "x-payment: paid" \
  -d '{
    "dataset": [
      {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
      {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1250}
    ],
    "algorithm": "trac3r-v1"
  }'
```

Expected response shape (`timestamp` will vary):

```json
{
  "status": "verified",
  "trustScore": 0.94,
  "flags": [],
  "hash": "0xabc123...",
  "algorithm": "trac3r-v1",
  "timestamp": "2026-05-05T16:43:15.993792Z"
}
```

If `x-payment` is missing or not `paid`, response is `HTTP 402`:

```json
{
  "error": "Payment required",
  "x402": {
    "version": 1,
    "accepts": [
      {
        "scheme": "exact",
        "network": "base",
        "maxAmountRequired": "0.01",
        "asset": "USDC"
      }
    ],
    "memo": "trac3r-verification"
  }
}
```

## Environment variables (AWS prep)

For production Lambda deployment, prefer IAM roles over static keys.
