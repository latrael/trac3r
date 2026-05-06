# TRAC3R — Backend Engineer (Consolidated, Post-Day-2)

Single source of truth for the backend after the AWS → Supabase pivot. This
supersedes `ROLE_backend_engineer_1_api_lead.md`,
`ROLE_backend_engineer_2_detection.md`, and
`ROLE_backend_engineer_3_integration.md` for everything that is not strictly
historical.

---

## What changed since the original role files

- **Storage** moved from DynamoDB + S3 to a single Supabase Postgres table
  (`verifications`). All `boto3` / DynamoDB / Lambda code has been removed.
- **Hosting** for the demo runs FastAPI directly (`uvicorn`). API Gateway and
  Lambda packaging are out of scope for the hackathon demo.
- **Status policy** is enforced at the API layer, not in the analyzer. The
  analyzer's `warning` band is collapsed to `verified` or `flagged` before the
  HTTP response is produced.
- **Env loading** is automatic. `backend/main.py` reads `.env` via
  `python-dotenv`. There is no longer a need to `source` env vars manually.

---

## System shape

```
client
  │  POST /verify  (x-payment: paid)
  ▼
FastAPI (backend/main.py)
  └─ routes/verify.py            ← payment gate (402 otherwise)
       └─ services/verification.py
            ├─ engine.analyze(dataset)        → trustScore, flags
            ├─ utils.hash.generate_hash(...)  → 0x… SHA-256
            └─ supabase.table("verifications").insert(record)

client
  │  GET /verify/{hash}
  ▼
FastAPI → services.get_verification_result
            └─ supabase.table("verifications").select(...).eq("hash", h)
```

---

## API contract (frontend-stable)

### `POST /verify`

Required header: `x-payment: paid`. Anything else → HTTP 402 with the x402
payload below.

Request body:
```json
{
  "dataset": [
    {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200}
  ],
  "algorithm": "trac3r-v1"
}
```

200 response:
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

Status policy at the HTTP layer:

- `trustScore >= 0.85` → `status = "verified"`
- otherwise → `status = "flagged"`

The analyzer may internally compute a third state called `warning`. That state
is **never** surfaced in the HTTP response; it collapses to `flagged`.

402 response (missing/invalid `x-payment`):
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

`originalTimestamp` is normalized to RFC3339 `…Z` form regardless of how
Supabase returns it.

### `GET /health`

`{"status": "ok"}` — used by the demo UI to confirm the backend is up.

---

## Detection engine

File: `backend/engine/analyzer.py`. Public surface:

```python
analyze(dataset: list[dict]) -> {"trustScore": float, "flags": list[str], "status": str}
```

Each row reaching the analyzer is a JSON-like dict with at least `timestamp`,
`source`, and `value`. Inputs that arrive via `POST /verify` are validated by
`models/request.py` (`VerifyRequest` / `DatasetPoint`) before reaching the
analyzer, so the analyzer can assume well-typed rows.

Checks and their deductions:

| check                     | deduction per finding |
|---------------------------|-----------------------|
| missing values (per field)| 0.10                  |
| duplicate timestamps      | 0.20                  |
| timestamp gaps            | 0.20                  |
| value spikes              | 0.30                  |
| replayed rows             | 0.30                  |

`trustScore` is `clamp(1.0 - sum(deductions), 0.0, 1.0)` rounded to 2 dp.

Internal status thresholds (informational only — not the API contract):

- `>= 0.85` → `verified`
- `>= 0.70` → `warning`
- otherwise → `flagged`

---

## Hashing

File: `backend/utils/hash.py`.

```python
generate_hash(dataset, trustScore, flags, algorithm, timestamp, status) -> "0x..."
```

Hash inputs are concatenated in this order, with deterministic serialization:

```
dataset_serialized + trustScore + flags_sorted + algorithm + timestamp + status
```

- `dataset` is JSON-encoded with sorted keys and compact separators.
- `timestamp` (datetime or string) is normalized to UTC, microseconds dropped,
  rendered as `YYYY-MM-DDTHH:MM:SSZ`.
- `flags` are sorted before hashing.

The hash MUST change if any single input changes. The integration tests
enforce this.

---

## Storage (Supabase)

Table: `verifications`.

| column      | type        | notes                                |
|-------------|-------------|--------------------------------------|
| hash        | text (PK)   | `0x…` SHA-256                        |
| trustScore  | float8      | 0.0 – 1.0                            |
| status      | text        | `verified` or `flagged`              |
| flags       | jsonb       | array of strings                     |
| timestamp   | timestamptz | UTC, populated by the backend        |
| algorithm   | text        | e.g. `trac3r-v1`                     |
| dataset     | jsonb       | original dataset rows                |

Required env vars:

```env
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role JWT>
```

Use the service-role JWT, not the publishable / anon key — the table is RLS
protected and inserts from the backend will fail with the anon key.

The Supabase client is built lazily inside
`services.verification._build_supabase_client`, which is the seam tests patch
to run offline.

---

## Repository layout

```
trac3r/
├── backend/
│   ├── main.py                  ← FastAPI app, env bootstrap
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── routes/verify.py
│   ├── services/verification.py ← analyze + hash + supabase write/read
│   ├── engine/analyzer.py
│   ├── models/{request,response}.py
│   ├── utils/hash.py
│   ├── config/settings.py
│   └── bedrock/explainer.py     ← optional natural-language explanation
├── tests/
│   ├── test_analyzer.py         ← engine unit tests
│   └── test_integration.py      ← API + service tests, Supabase mocked
├── demo/                        ← demo / agent harness
├── demo-data/                   ← clean + tampered CSV fixtures
└── docs/ROLE_backend_engineer.md (this file)
```

---

## Local dev

```bash
# one-time
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# run
cd ..
uvicorn backend.main:app --reload --port 8000
# or:  cd backend && uvicorn main:app --reload --port 8000

# tests
python -m pytest tests/ -v
```

---

## Definition of done

- [x] `POST /verify` validates input, runs `engine.analyze`, persists to
      Supabase, returns the documented JSON.
- [x] Trust score and flags come from `engine.analyze` (not hardcoded).
- [x] SHA-256 hash is deterministic, prefixed with `0x`, and changes when any
      input field changes.
- [x] `GET /verify/{hash}` returns `match` / `flagged` / `not_found` with the
      documented shape and a `…Z`-normalized `originalTimestamp`.
- [x] x402 gate returns 402 when `x-payment` is absent or not `paid`.
- [x] Clean dataset → `trustScore ≥ 0.85` → `verified`. Tampered dataset →
      `trustScore ≤ 0.70` → `flagged`.
- [x] Analyzer-internal `warning` is never surfaced over HTTP.
- [x] All tests pass: `pytest tests/`.
