# TRAC3R Backend

FastAPI service that verifies dataset integrity, scores trust, and persists
results to Supabase. Payment is gated by a mock x402 header.

## Implemented (Day 2)

- `POST /verify` — runs detection engine, stores result, returns scored response
- `GET /verify/{hash}` — fetches a stored verification by hash
- `GET /health` — liveness check
- x402-style payment mock (header `x-payment: paid`, otherwise HTTP 402)
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
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role JWT>
```

The service-role key (NOT the publishable / anon key) is required because the
backend writes to a table protected by RLS. `main.py` loads `.env` automatically
via `python-dotenv`.

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

Headers: `x-payment: paid` (required).

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

Response (402, no `x-payment`):
```json
{
  "error": "Payment required",
  "x402": {
    "version": 1,
    "accepts": [
      {"scheme": "exact", "network": "base", "maxAmountRequired": "0.01", "asset": "USDC"}
    ],
    "memo": "trac3r-verification"
  }
}
```

### `GET /verify/{hash}`

| stored status | response                                                       |
|---------------|----------------------------------------------------------------|
| (none)        | `{"result": "not_found", "hash": "0x…"}`                       |
| `verified`    | `{"result": "match", "originalTimestamp": "…Z", "hash": "0x…"}` |
| `flagged`     | `{"result": "flagged", "originalTimestamp": "…Z", "hash": "0x…"}` |

## Quick curl

```bash
curl -sS -X POST "http://localhost:8000/verify" \
  -H "Content-Type: application/json" \
  -H "x-payment: paid" \
  -d '{"dataset":[{"timestamp":"2026-04-29T19:00:00Z","source":"node1","value":1200}],"algorithm":"trac3r-v1"}'
```
