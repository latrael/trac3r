from __future__ import annotations

from fastapi import FastAPI

from routes.verify import router as verify_router

app = FastAPI(title="trac3r API")

app.include_router(verify_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}