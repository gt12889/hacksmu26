"""GET /api/status/{job_id} — return job status from JOB_REGISTRY."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.jobs import JOB_REGISTRY
from api.models import StatusResponse

router = APIRouter()


@router.get("/api/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str) -> StatusResponse:
    """Return current status for a job. 404 if job_id is unknown."""
    job = JOB_REGISTRY.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        total=job["total"],
    )
