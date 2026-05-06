from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(_HERE), ".env"))
    load_dotenv(os.path.join(_HERE, ".env"))
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import x402_enabled
from routes.agent import router as agent_router
from routes.verify import router as verify_router

app = FastAPI(title="trac3r API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-PAYMENT-RESPONSE"],
)

if x402_enabled():
    from services.x402_gate import build_payment_middleware

    _x402_mw = build_payment_middleware()

    @app.middleware("http")
    async def x402_middleware(request, call_next):
        return await _x402_mw(request, call_next)

app.include_router(verify_router)
app.include_router(agent_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
