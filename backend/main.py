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

from routes.verify import router as verify_router

app = FastAPI(title="trac3r API")

app.include_router(verify_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
