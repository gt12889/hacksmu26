"""GET /api/result/{job_id} — return job results, audio, or spectrogram."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from api.jobs import JOB_REGISTRY

router = APIRouter()


@router.get("/api/result/{job_id}")
async def get_result(job_id: str) -> JSONResponse:
    """Return results when complete; 202 while still running/queued."""
    job = JOB_REGISTRY.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    status = job["status"]
    if status != "complete":
        return JSONResponse(
            status_code=202,
            content={"detail": f"Job status: {status}"},
        )

    return JSONResponse(
        status_code=200,
        content={"job_id": job_id, "results": job["results"]},
    )


@router.get("/api/result/{job_id}/audio/{call_index}")
async def get_audio(job_id: str, call_index: int) -> FileResponse:
    """Return the cleaned WAV file for a specific call index."""
    job = JOB_REGISTRY.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    if job["status"] != "complete":
        raise HTTPException(
            status_code=202,
            detail=f"Job not complete — status: {job['status']}",
        )

    results = job.get("results", [])
    if call_index < 0 or call_index >= len(results):
        raise HTTPException(
            status_code=404,
            detail=f"call_index {call_index} out of range (total: {len(results)})",
        )

    wav_path = results[call_index].get("clean_wav_path", "")
    if not wav_path or not Path(wav_path).exists():
        raise HTTPException(status_code=404, detail="Audio file not available")

    return FileResponse(wav_path, media_type="audio/wav")


@router.get("/api/result/{job_id}/spectrogram/{call_index}")
async def get_spectrogram(job_id: str, call_index: int) -> FileResponse:
    """Return the spectrogram PNG for a specific call index.

    Returns 404 if no spectrogram was generated (batch_runner does not produce PNG files
    in Phase 4 — this endpoint is a no-op placeholder for the React demo).
    """
    job = JOB_REGISTRY.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    if job["status"] != "complete":
        raise HTTPException(
            status_code=202,
            detail=f"Job not complete — status: {job['status']}",
        )

    results = job.get("results", [])
    if call_index < 0 or call_index >= len(results):
        raise HTTPException(
            status_code=404,
            detail=f"call_index {call_index} out of range (total: {len(results)})",
        )

    result = results[call_index]
    png_path = result.get("png_path")
    if not png_path or not Path(png_path).exists():
        raise HTTPException(status_code=404, detail="spectrogram not available")

    return FileResponse(png_path, media_type="image/png")
