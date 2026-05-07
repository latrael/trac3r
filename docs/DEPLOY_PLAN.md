# TRAC3R Public Deploy Plan

A pragmatic plan to put TRAC3R on the public internet for free (or near-free), with the core x402 demo flow working end-to-end. Hand this file to a fresh chat and it should have everything needed to execute.

---

## Goals

1. **Public URL** for the API: `https://api.trac3r.<domain>` (or an AWS-default URL).
2. **Public URL** for the frontend: `https://trac3r.<domain>` (or `vercel.app` / `netlify.app`).
3. **Real x402 payment** works against the public API.
4. **Costs**: stay inside AWS free tier + Vercel/Netlify free tier. Testnet USDC only.

---

## Architecture (target)

```
Browser ─┬─► Vercel/Netlify static site (frontend/index.html)
         │
         └─► API Gateway HTTPS endpoint
                  │
                  ▼
              Lambda (FastAPI via Mangum)
                  │
              ┌───┴────┐
              ▼        ▼
          DynamoDB    x402 facilitator (https://x402.org/facilitator)
        (proof store)
```

Components:
- **API**: existing FastAPI app, deployed as a single AWS Lambda fronted by API Gateway (HTTP API).
- **Frontend**: existing `frontend/index.html`, deployed to Vercel as a static site.
- **DynamoDB**: existing `trac3r-verifications` table.
- **x402**: public Coinbase facilitator on Base Sepolia. No additional infra needed.

---

## Pre-deploy decisions

### 1. What to do with `/agent/verify`

The helper endpoint pays from `BUYER_KEY` server-side. Exposing it publicly = strangers drain the buyer wallet.

**Pick one:**

- **A. Keep `/agent/verify`, rate-limited.** Add API Gateway throttling (e.g. 1 req/sec, 10 req/day per IP). Frontend continues calling it. Easiest path for "judge clicks button, sees result." Buyer wallet costs ≈ $0.01 per click in testnet USDC.
- **B. Drop `/agent/verify` from public deploy.** Frontend uses MetaMask + EIP-712 signing to call `/verify` directly. Each user pays from their own wallet. Most authentic. Requires the user to have a wallet configured for Base Sepolia.
- **C. Hybrid.** Both endpoints public. Frontend defaults to `/agent/verify` for the friendly path; a "Pay with my own wallet" toggle switches to `/verify` + browser signing.

**Recommendation:** **A** for the hackathon demo, **C** if there's an extra hour. **B** is purist but costs you judges who don't have MetaMask ready.

### 2. Domain

- **Easiest**: use the default API Gateway URL (`https://<id>.execute-api.us-east-1.amazonaws.com`) and Vercel's `*.vercel.app` URL. Zero DNS work.
- **Polished**: register `trac3r.<tld>`, point CNAME at Vercel and API Gateway. Adds 30 min.

---

## Step 1 — API on AWS Lambda

### 1a. Add Mangum to requirements

`backend/requirements.txt`:

```
mangum>=0.17.0,<1.0.0
```

### 1b. Add Lambda handler

`backend/lambda_handler.py`:

```python
from mangum import Mangum
from main import app

handler = Mangum(app, lifespan="off")
```

### 1c. Bundle the deployment package

The x402 SDK pulls in `eth_account`, `web3`, `eth_abi`, etc. The total zip is too big for inline upload — use a **Lambda container image** instead. It's actually simpler.

`backend/Dockerfile`:

```dockerfile
FROM public.ecr.aws/lambda/python:3.13

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ${LAMBDA_TASK_ROOT}/

CMD ["lambda_handler.handler"]
```

Build + push to ECR:

```bash
aws ecr create-repository --repository-name trac3r-api
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <acct>.dkr.ecr.us-east-1.amazonaws.com

docker build -t trac3r-api ./backend
docker tag trac3r-api:latest <acct>.dkr.ecr.us-east-1.amazonaws.com/trac3r-api:latest
docker push <acct>.dkr.ecr.us-east-1.amazonaws.com/trac3r-api:latest
```

### 1d. Create the Lambda function

```bash
aws lambda create-function \
  --function-name trac3r-api \
  --package-type Image \
  --code ImageUri=<acct>.dkr.ecr.us-east-1.amazonaws.com/trac3r-api:latest \
  --role arn:aws:iam::<acct>:role/trac3r-lambda-role \
  --memory-size 1024 \
  --timeout 30 \
  --environment "Variables={
    AWS_REGION=us-east-1,
    DYNAMODB_TABLE=trac3r-verifications,
    BUYER_KEY=<paste from .env>,
    X402_PAY_TO=0xe3cB5A3aC8dfdC9E67e8876bf99579BEe3db7Be3,
    X402_NETWORK=eip155:84532,
    X402_PRICE=$0.01,
    X402_FACILITATOR_URL=https://x402.org/facilitator,
    X402_ENABLED=true
  }"
```

The IAM role needs:
- `AWSLambdaBasicExecutionRole` (logs)
- DynamoDB read/write on the `trac3r-verifications` table
- (No outbound network policy needed; Lambdas have egress by default.)

**Cold start note**: ~3–5 seconds on first request because the x402 middleware fetches `/supported` from the facilitator on init. Subsequent invocations are fast. If this is too slow for the demo, set provisioned concurrency = 1 (~$5/mo) or add a CloudWatch warm-up rule.

### 1e. Front it with API Gateway

HTTP API (cheaper and simpler than REST API):

```bash
aws apigatewayv2 create-api \
  --name trac3r-api \
  --protocol-type HTTP \
  --target arn:aws:lambda:us-east-1:<acct>:function:trac3r-api \
  --cors-configuration "AllowOrigins=*,AllowMethods=GET,POST,OPTIONS,AllowHeaders=*"
```

This gives you the public URL: `https://<id>.execute-api.us-east-1.amazonaws.com`.

**Smoke test:**
```bash
API=https://<id>.execute-api.us-east-1.amazonaws.com
curl -i -X POST "$API/verify" \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"trac3r-v1","dataset":[{"timestamp":"2026-04-29T19:00:00Z","source":"node1","value":1200}]}'
```

Expect `402 Payment Required` with the `payment-required` header. If that works, the gate is live.

### 1f. (Decision A only) Throttling for `/agent/verify`

In API Gateway, add a route-specific throttling rule on `POST /agent/verify`:

```bash
aws apigatewayv2 update-stage \
  --api-id <id> \
  --stage-name '$default' \
  --route-settings '{
    "POST /agent/verify": {
      "ThrottlingBurstLimit": 2,
      "ThrottlingRateLimit": 1
    }
  }'
```

This caps the helper at 1 req/sec / 2 burst, preventing a stranger from draining the buyer wallet via a script. Add a CloudWatch alarm on the `BUYER_KEY` wallet's USDC balance if you want belt + suspenders — query Basescan API on a schedule and alert when balance drops below a threshold.

---

## Step 2 — Frontend on Vercel

`frontend/index.html` is already a single static file. No build step.

### 2a. Point the frontend at the public API

The frontend currently reads the API URL from `window.location.origin` with a `localStorage` override. For the deploy, hardcode the API base or use a build-time env. Simplest:

Edit `frontend/index.html`:

```js
const API = "https://<id>.execute-api.us-east-1.amazonaws.com";
```

Or add a tiny `frontend/config.js`:

```js
window.TRAC3R_API = "https://<id>.execute-api.us-east-1.amazonaws.com";
```

…and reference it from `index.html`.

### 2b. Deploy to Vercel

```bash
npm i -g vercel
cd frontend
vercel deploy --prod
```

First-time prompts: link to a project, accept the static config. You'll get a URL like `https://trac3r.vercel.app`.

(Netlify is equally good: `npx netlify deploy --dir=frontend --prod`.)

### 2c. Smoke test

Visit the Vercel URL, click both buttons. Should see real x402 flow run end-to-end and DynamoDB record the result.

---

## Step 3 — (Optional) Browser-wallet flow

If you went with **Decision B or C** above, the frontend also needs to sign x402 payments client-side. Two options:

### Option 1 — `x402-fetch` from a CDN

```html
<script type="module">
  import { wrapFetchWithPayment } from "https://esm.sh/x402-fetch@latest";
  import { createWalletClient, custom } from "https://esm.sh/viem@latest";
  import { baseSepolia } from "https://esm.sh/viem@latest/chains";

  // After "Connect wallet" button:
  const account = (await window.ethereum.request({ method: "eth_requestAccounts" }))[0];
  const wallet = createWalletClient({ account, chain: baseSepolia, transport: custom(window.ethereum) });
  const fetchWithPay = wrapFetchWithPayment(fetch, wallet);

  // Then call /verify exactly as you would call fetch:
  const r = await fetchWithPay(`${API}/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ algorithm: "trac3r-v1", dataset: cleanDataset }),
  });
</script>
```

The library handles the 402 → sign → retry loop. MetaMask pops up on the signature step.

### Option 2 — Hand-rolled EIP-712 signing

Skip unless you're allergic to npm. The `x402-fetch` route is genuinely the simplest path.

### What the user needs

- MetaMask (or Coinbase Wallet) browser extension
- Base Sepolia network added (chainId `84532`, RPC `https://sepolia.base.org`)
- Wallet funded with Base Sepolia USDC ([Circle faucet](https://faucet.circle.com))
- No ETH needed (EIP-3009 is gasless for the signer; facilitator pays gas)

Add a "Get testnet USDC" link on the frontend so judges aren't lost.

---

## Step 4 — Sanity checklist

- [ ] `curl https://<api>/health` → `{"status":"ok"}`
- [ ] `curl -i -X POST https://<api>/verify -d '{"...":"..."}'` → `402` with `payment-required` header
- [ ] `python demo/agent_demo.py` against the public URL → clean verifies, tampered flagged
- [ ] Frontend loads at the Vercel URL, both buttons return scored responses
- [ ] DynamoDB `trac3r-verifications` table has new items after a button click
- [ ] At least one transaction visible on https://sepolia.basescan.org/address/0xe3cB5A3aC8dfdC9E67e8876bf99579BEe3db7Be3
- [ ] (Decision A) `/agent/verify` throttling confirmed by hammering it with `ab` or `hey`

---

## Step 5 — When you're ready for mainnet

The whole stack flips to Base mainnet via env:

- `X402_NETWORK=eip155:8453`
- Buyer wallet needs real USDC (~$1 covers hundreds of demo calls)
- The public facilitator at `https://x402.org/facilitator` requires CDP API keys for mainnet settlement. Add them via env vars and the SDK picks them up.

Don't flip until the testnet deploy is fully working.

---

## Costs (rough)

| Component | Monthly cost (light demo use) |
|---|---|
| Lambda container image | < $0.01 (free tier covers) |
| API Gateway HTTP API | < $0.01 (free tier: 1M calls/mo) |
| DynamoDB on-demand | < $0.01 (free tier: 25 GB + 25 RCU/WCU) |
| ECR image storage | ~$0.10 (one ~1 GB image) |
| Vercel static hosting | $0 (hobby tier) |
| Buyer wallet (testnet) | $0 (faucet refills) |

Total: pennies per month, plus your time refilling the buyer faucet.

---

## Open questions for the next chat

- Which Decision (A / B / C) above? Default: A.
- Custom domain or default URLs? Default: defaults.
- Provisioned concurrency to kill the cold start, or accept the 3–5 s on first hit?
- Is `BUYER_KEY` rotated for the public deploy, or reusing the dev key? (Recommend rotating — old key is in your local `.env`, has been used for testing, and you'd want a clean wallet for the public surface.)
