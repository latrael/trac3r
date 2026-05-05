from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class DatasetPoint(BaseModel):
    timestamp: datetime = Field(..., description="ISO-8601 timestamp (UTC recommended)")
    source: str = Field(..., description="Dataset source identifier (e.g., node name)")
    value: float = Field(..., description="Numeric value for the given timestamp/source")


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: List[DatasetPoint] = Field(..., min_length=1)
    algorithm: str = Field(..., description="Algorithm version identifier (e.g., trac3r-v1)")