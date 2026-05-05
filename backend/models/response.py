from __future__ import annotations

from datetime import datetime
from typing import Literal, List

from pydantic import BaseModel, ConfigDict, Field


VerifyStatus = Literal["verified", "flagged"]


class VerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VerifyStatus
    trustScore: float = Field(..., ge=0.0, le=1.0)
    flags: List[str]
    hash: str
    algorithm: str
    timestamp: datetime