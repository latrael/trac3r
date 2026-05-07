# TRAC3R Demo Recording Script

Target length: **4–5 minutes**. Hits every judging-rubric point: real protocol, on-chain settlement, working UI, repo walkthrough.

Pull this file up on a second monitor while recording.

---

## Pre-recording checklist

Do all of this **before you hit record**:

- [ ] Backend running: `backend/venv/bin/uvicorn main:app --app-dir backend --reload --port 8000`
- [ ] Frontend running: `python3 -m http.server 5500 --directory frontend`
- [ ] Three terminal tabs open and labeled:
  - **Tab 1** — running uvicorn (don't touch during recording)
  - **Tab 2** — clean prompt, working dir is the repo root, ready for curl
  - **Tab 3** — clean prompt, ready for `agent_demo.py`
- [ ] Browser tabs open, in this order:
  - `http://localhost:5500` (frontend)
  - `https://sepolia.basescan.org/address/0xe3cB5A3aC8dfdC9E67e8876bf99579BEe3db7Be3` (seller wallet)
  - `https://github.com/latrael/trac3r` (repo)
- [ ] Buyer wallet has ≥ $0.10 testnet USDC and a sliver of Base Sepolia ETH
- [ ] Mic level checked, screen recorder set to capture mic + system audio
- [ ] Window width: terminals at least 120 columns so the `payment-required` header doesn't wrap
- [ ] **One warm-up paid call already made** so the Lambda init is cached and Basescan has a recent transaction at the top of the list (re-run `python demo/agent_demo.py` once before recording)

---

## Beat 1 — Problem framing (30 s)

**On screen:** the GitHub repo's main page (or just a slide with "TRAC3R").

**Voiceover (verbatim):**

> "Autonomous agents are designed to act. They execute trades, trigger workflows, move funds. But they act on whatever data they receive — and they have no reliable way to know if that data has been manipulated.
>
> TRAC3R is a paid data-integrity verification API. Before an agent acts on a dataset, it calls TRAC3R, pays one cent in USDC through Coinbase's x402 protocol on Base, and gets back a trust score, a list of anomaly flags, a cryptographic hash, and an on-chain receipt."

---

## Beat 2 — Backend running, gate is real (60 s)

**On screen:** Tab 2 (terminal).

**Step 2a — Health check.** Type:

```bash
curl -s http://localhost:8000/health
```

Voiceover: *"Backend is up locally on port 8000. FastAPI on Python 3.13."*

**Step 2b — Hit the gate without paying.** Type:

```bash
curl -i -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"trac3r-v1","dataset":[{"timestamp":"2026-04-29T19:00:00Z","source":"node1","value":1200}]}'
```

Pause on the response. Voiceover:

> "402 Payment Required. The response is empty by design — the protocol payload lives in this `payment-required` header, base64 encoded. This is real Coinbase x402 v2, not a mock — it's emitted by the official Coinbase x402 Python SDK we have wired into our FastAPI middleware."

**Step 2c — Decode the header live.** Copy the long base64 value. Type:

```bash
echo "<paste header value here>" | base64 -d | jq
```

Pause on the JSON. Voiceover, pointing at each field:

> "Version 2. Network: `eip155:84532` — that's Base Sepolia. Scheme: exact. Asset: this address is Base Sepolia USDC. Amount: 10000 atomic units, which is one cent because USDC has six decimals. PayTo: our seller wallet, ending `7Be3`. Anyone can read this header, sign a payment, and retry — that's the protocol."

> "If you don't pay, you don't get the verification. No work runs, nothing is written to the database."

---

## Beat 3 — Frontend demo (60 s)

**On screen:** browser at `http://localhost:5500`.

**Step 3a — Clean dataset.** Click **Verify clean dataset**.

Voiceover while it loads:

> "The frontend is a single static HTML file. When I click verify, it sends the dataset to our backend. The backend signs an x402 payment, the public Coinbase facilitator settles it on Base Sepolia, and only then does the detection engine run."

When result renders, point at:
- The **score 1.00** and the green **Verified** badge
- The **Hash** — *"SHA-256 over the full verification context"*
- The **Payment** line — *"That call just paid one cent USDC on Base Sepolia"*

**Step 3b — Tampered dataset.** Click **Verify tampered dataset**.

Voiceover while it loads:

> "Same dataset shape, but I've injected four anomalies — a duplicate timestamp, a value spike, a missing interval, and a replayed row."

When result renders, point at:
- The **score** dropped to ~0.0 and the red **Flagged** badge
- The **flags list** — *"Each one is human-readable, suitable for displaying to a user or feeding into Bedrock for a plain-English explanation"*
- The **Hash** is different from the clean one — *"Tamper with any field and the hash changes; the proof is bound to the inputs"*

---

## Beat 4 — On-chain proof + agent flow (75 s)

**This is the strongest x402 moment. Don't rush it.**

**Step 4a — Run the agent script.** Switch to Tab 3. Type:

```bash
backend/venv/bin/python demo/agent_demo.py
```

Voiceover while it runs:

> "This Python script is what an autonomous agent actually looks like. It uses the official x402 client library — when our server returns 402, the script reads the payment-required header, signs an EIP-3009 USDC authorization with its own private key, and retries. No mock, no manual steps — real signing, real on-chain settlement."

When output appears, point at:
- *"Clean dataset: trust score 1.0, agent proceeds"*
- *"Tampered dataset: score 0.0, agent refuses, prints the flags it would have acted on"*

> "That's the trust checkpoint. An agent that uses TRAC3R won't act on bad data — and crucially, it pays for the privilege of knowing that, which means TRAC3R is sustainable as infrastructure."

**Step 4b — Basescan proof.** Switch to the Basescan tab on the seller address. Refresh.

Voiceover, pointing at the most recent USDC Token Transfer:

> "And here's the receipt. Our seller wallet on Base Sepolia. Each verification triggers a real on-chain USDC transfer, settled by Coinbase's public facilitator. This is the transaction the agent script just generated, less than ten seconds ago."

Click into the transaction. Point at the From/To/Amount fields:

> "0.01 USDC, from the buyer wallet, to our seller. Verified on-chain, end-to-end."

---

## Beat 5 — Repo walkthrough (60 s)

**On screen:** GitHub repo at `https://github.com/latrael/trac3r`. Scroll to the README's component sections.

**The four components — about 10 seconds each:**

**Component 1 — `backend/services/x402_gate.py`.**

> "The payment middleware. About 40 lines. Registers Base Sepolia, points at Coinbase's public facilitator, gates POST /verify with a $0.01 USDC price."

**Component 2 — `backend/engine/analyzer.py`.**

> "The detection engine. Five deterministic checks — missing values, duplicate timestamps, gaps, value spikes, replayed rows. No ML, no randomness. Same input always produces the same score, the same flags, the same hash."

**Component 3 — `backend/aws/dynamodb.py` + `backend/utils/hash.py`.**

> "Persistence. Every verification is hashed with SHA-256 over its full context — dataset, score, flags, algorithm, timestamp, status — and stored in DynamoDB partitioned by hash. The hash binds all of those fields together; tamper with any of them and the proof breaks."

**Component 4 — `backend/routes/agent.py` + `frontend/index.html`.**

> "The demo surface. The static frontend calls `/agent/verify`, which signs payments server-side so anyone can click through without a wallet plugin. The real protocol surface is `/verify` and is exercised by the Python agent script you just saw."

**Tests.** Open `tests/` directory or run `pytest`:

```bash
backend/venv/bin/python -m pytest tests/test_integration.py tests/test_analyzer.py tests/test_x402_gate.py -v
```

> "Twenty offline tests pass on every change — covering the detection engine, the persistence layer, and the x402 gate's 402 response shape. There's also a live end-to-end test that makes real Base Sepolia payments to verify the full signed-retry flow."

---

## Beat 6 — Close (15 s)

**On screen:** README homepage.

**Voiceover (verbatim):**

> "TRAC3R turns data integrity into a paid, machine-readable trust checkpoint for the agent economy. The protocol is real x402 on Base, the detection is deterministic, the proof is hashed and stored, and every call settles on-chain. Thanks for watching."

---

## Three sentences to land somewhere in the video

These map directly to what judges are checking. Say each one verbatim — they're already woven into the script above, but if you ad-lib, make sure they land:

1. *"The 402 response and `payment-required` header are emitted by the official Coinbase x402 Python SDK — TRAC3R is a real x402 resource server, not a simulation."*
2. *"Every paid call settles a USDC transfer on Base Sepolia, verifiable on Basescan at the seller address."*
3. *"The trust score, flags, and SHA-256 hash are returned in the same response that triggered the on-chain payment — payment and verification are atomic from the caller's perspective."*

---

## What to include in the README

Per the rubric (point 7):

- [ ] **Demo video** — link to the Loom/YouTube recording at the top of README
- [ ] **Screenshots of the UI** — capture two: clean result (green) and tampered result (red). Drop into `docs/screenshots/` and reference in the README
- [ ] **Description of blockchain interaction** — already covered in the System Interaction Flow section. Add one line at the top: *"Each call triggers a real USDC transfer on Base Sepolia via Coinbase's x402 protocol."*
- [ ] **Audio walkthrough video** — same Loom link, separate bullet so judges find it

Suggested README header block to add at the very top, above the title blurb:

```markdown
🎥 **[Watch the 5-minute demo →](LOOM_LINK_HERE)**

🖼️ **UI screenshots:** [clean](docs/screenshots/clean.png) · [tampered](docs/screenshots/tampered.png)

🔗 **On-chain proof:** [seller wallet on Basescan](https://sepolia.basescan.org/address/0xe3cB5A3aC8dfdC9E67e8876bf99579BEe3db7Be3)
```

---

## Recording tips

- **Don't show the `.env` file**, even briefly — `BUYER_KEY` is in there.
- **Don't paste the full base64 header into the voiceover** — it's gibberish. Just point at it on screen and decode.
- If a button click is slow because of cold start, pause your narration and wait. Don't apologize for it; just resume cleanly when the result renders.
- If you fumble a line, pause for two seconds in silence, then say the line again. Easier to cut in editing than splicing mid-sentence.
- Record one extra take of just Basescan zoomed in on a transaction — it's the most quotable single visual in the demo.
