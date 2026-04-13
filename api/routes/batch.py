"""GET /api/batch/summary and batch results/audio endpoints."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from api.jobs import JOB_REGISTRY
from api.models import BatchSummaryResponse

router = APIRouter()

# Allowed root directories for batch audio serving (resolved at import time)
_REPO_ROOT = Path(__file__).resolve().parents[2]  # api/routes/batch.py -> api/ -> repo root
BATCH_OUTPUT_DIR = _REPO_ROOT / "data" / "outputs"
_ALLOWED_ROOTS = [
    (_REPO_ROOT / "data" / "outputs").resolve(),
    (_REPO_ROOT / "cleaned").resolve(),
]


@router.get("/api/batch/results")
async def batch_results() -> JSONResponse:
    """Read all summary.csv files under data/outputs/ and merge into one result list.

    Used by the React demo to browse the 212 pre-processed calls without re-running
    the pipeline. Returns empty list if data/outputs/ does not exist.
    """
    results: list[dict] = []
    if BATCH_OUTPUT_DIR.exists():
        # Accept both summary.csv and batch_summary.csv
        candidates = list(BATCH_OUTPUT_DIR.glob("*/summary.csv")) + list(
            BATCH_OUTPUT_DIR.glob("*/batch_summary.csv")
        )
        # De-dup (summary.csv may be a symlink to batch_summary.csv)
        seen: set[Path] = set()
        for summary_csv in sorted(candidates):
            real = summary_csv.resolve()
            if real in seen:
                continue
            seen.add(real)
            try:
                df = pd.read_csv(summary_csv)
            except Exception:
                continue
            run_dir = summary_csv.parent
            cleaned_dir = run_dir / "cleaned"
            for idx, row in enumerate(df.to_dict(orient="records")):
                # Derive clean_wav_path if not in CSV
                wav = row.get("clean_wav_path", "")
                if not wav:
                    stem = Path(str(row.get("filename", ""))).stem
                    derived = cleaned_dir / f"{stem}_{idx:04d}_clean.wav"
                    if derived.exists():
                        row["clean_wav_path"] = str(derived.resolve())
                    else:
                        row["clean_wav_path"] = ""
                elif not Path(str(wav)).is_absolute():
                    row["clean_wav_path"] = str((run_dir / wav).resolve())
                # Ensure all fields the frontend expects exist
                row.setdefault("start", 0.0)
                row.setdefault("end", 0.0)
                row.setdefault("call_index", idx)
                results.append(row)
    return JSONResponse(
        status_code=200,
        content={"job_id": "batch-disk", "results": results},
    )


@router.get("/api/batch/audio")
async def batch_audio(
    path: str = Query(..., description="Absolute path to a clean WAV file"),
) -> FileResponse:
    """Serve a pre-processed clean WAV by absolute path.

    Used by the React frontend to play audio for batch-disk rows (source.kind='batch').
    Security: only files under data/outputs/ or cleaned/ are served; 403 otherwise.
    """
    resolved = Path(path).resolve()
    allowed = any(
        str(resolved).startswith(str(root) + os.sep) or resolved == root
        for root in _ALLOWED_ROOTS
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Path outside allowed directories")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(resolved), media_type="audio/wav")


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
