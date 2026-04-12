"""Pydantic v2 request/response schemas (FastAPI 0.115+ requires Pydantic v2)."""
from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    path: str


class ProcessResponse(BaseModel):
    job_id: str


class StatusResponse(BaseModel):
    job_id: str
    status: str  # "queued" | "running" | "complete" | "failed"
    progress: int
    total: int
    eta_seconds: float | None = None


class BatchSummaryResponse(BaseModel):
    total_jobs: int
    total_calls_processed: int
    average_confidence: float | None
    average_snr_improvement_db: float | None
