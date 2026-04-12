"""POST /api/process — dispatch processing job to background task."""
from __future__ import annotations

import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import soundfile as sf
from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.jobs import JOB_REGISTRY
from api.models import ProcessResponse
from api.uploads import UPLOAD_REGISTRY
from pipeline.batch_runner import run_batch

router = APIRouter()


def _run_job(job_id: str) -> None:
    """Background task: process uploaded WAV through full pipeline, update JOB_REGISTRY."""
    try:
        JOB_REGISTRY[job_id]["status"] = "running"
        JOB_REGISTRY[job_id]["total"] = 1

        job = JOB_REGISTRY[job_id]
        upload_path = job["upload_path"]  # absolute path string

        duration = sf.info(upload_path).duration
        annotations_df = pd.DataFrame(
            [
                {
                    "filename": Path(upload_path).name,
                    "start": 0.0,
                    "end": duration,
                }
            ]
        )
        recordings_dir = Path(upload_path).parent  # UPLOAD_DIR
        output_dir = Path(job["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        def progress_cb(done: int, total: int) -> None:
            JOB_REGISTRY[job_id]["progress"] = done

        results = run_batch(
            annotations_df,
            recordings_dir,
            output_dir,
            progress_callback=progress_cb,
        )

        JOB_REGISTRY[job_id].update(
            {
                "status": "complete",
                "results": results,
                "progress": len(results),
                "total": len(results),
            }
        )
    except Exception as e:  # noqa: BLE001
        JOB_REGISTRY[job_id].update(
            {
                "status": "failed",
                "error": str(e) + "\n" + traceback.format_exc(),
            }
        )


@router.post("/api/process", response_model=ProcessResponse)
async def trigger_process(
    file_id: str,
    background_tasks: BackgroundTasks,
) -> ProcessResponse:
    """Look up uploaded file by file_id, register a job, and dispatch background processing."""
    upload_path = UPLOAD_REGISTRY.get(file_id)
    if upload_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"file_id '{file_id}' not found — upload the file first",
        )

    job_id = str(uuid.uuid4())
    output_dir = Path("data/outputs") / job_id

    JOB_REGISTRY[job_id] = {
        "status": "queued",
        "progress": 0,
        "total": 0,
        "results": [],
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "upload_path": upload_path,
        "output_dir": str(output_dir),
    }

    background_tasks.add_task(_run_job, job_id)
    return ProcessResponse(job_id=job_id)
