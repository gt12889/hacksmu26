"""GET /api/batch/summary — aggregate metrics across all jobs in JOB_REGISTRY."""
from __future__ import annotations

from fastapi import APIRouter

from api.jobs import JOB_REGISTRY
from api.models import BatchSummaryResponse

router = APIRouter()


@router.get("/api/batch/summary", response_model=BatchSummaryResponse)
async def batch_summary() -> BatchSummaryResponse:
    """Aggregate metrics across all jobs registered in JOB_REGISTRY."""
    total_jobs = len(JOB_REGISTRY)
    total_calls = sum(job["progress"] for job in JOB_REGISTRY.values())

    # Collect all result dicts from completed jobs
    all_results: list[dict] = []
    for job in JOB_REGISTRY.values():
        if job["status"] == "complete":
            all_results.extend(job.get("results", []))

    avg_confidence: float | None = None
    avg_snr_improvement: float | None = None

    if all_results:
        confidences = [r["confidence"] for r in all_results if "confidence" in r]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)

        snr_improvements = [
            r["snr_after_db"] - r["snr_before_db"]
            for r in all_results
            if "snr_after_db" in r and "snr_before_db" in r
        ]
        if snr_improvements:
            avg_snr_improvement = sum(snr_improvements) / len(snr_improvements)

    return BatchSummaryResponse(
        total_jobs=total_jobs,
        total_calls_processed=total_calls,
        average_confidence=avg_confidence,
        average_snr_improvement_db=avg_snr_improvement,
    )
