"""Demo router — serves the 3-noise-type demo for the frontend."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, BackgroundTasks, HTTPException

router = APIRouter(prefix="/api/demo", tags=["demo"])

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "data" / "outputs" / "demo"
METADATA_FILE = DEMO_DIR / "metadata.json"

_job_state = {
    "status": "idle",  # idle | running | done | error
    "progress": 0,
    "message": "",
}
_job_lock = Lock()


def _demo_ready() -> bool:
    required = [
        DEMO_DIR / f"{t}_demo.png" for t in ("generator", "car", "plane")
    ] + [
        DEMO_DIR / f"{t}_clean.wav" for t in ("generator", "car", "plane")
    ]
    return all(f.exists() for f in required)


def _run_demo_script() -> None:
    """Invoke scripts/demo_spectrograms.py --synthetic to regenerate demo assets."""
    with _job_lock:
        _job_state.update(status="running", progress=10, message="Generating demo spectrograms...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.demo_spectrograms", "--synthetic",
             "--output-dir", str(DEMO_DIR)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            with _job_lock:
                _job_state.update(
                    status="error", progress=0,
                    message=f"demo script failed: {result.stderr[:200]}",
                )
            return
        # Write default metadata if not present
        if not METADATA_FILE.exists():
            _write_default_metadata()
        with _job_lock:
            _job_state.update(status="done", progress=100, message="Demo ready")
    except Exception as e:
        with _job_lock:
            _job_state.update(status="error", progress=0, message=str(e)[:200])


def _write_default_metadata() -> None:
    """Write placeholder metadata matching the synthetic demo output."""
    default = {
        "generator": {
            "snr_before": 5.2, "snr_after": 18.7, "snr_improvement": 13.5,
            "f0_min": 12.5, "f0_max": 16.8, "f0_median": 14.2, "duration": 3.0,
        },
        "car": {
            "snr_before": 4.8, "snr_after": 17.3, "snr_improvement": 12.5,
            "f0_min": 13.1, "f0_max": 17.4, "f0_median": 15.0, "duration": 3.0,
        },
        "plane": {
            "snr_before": 3.9, "snr_after": 16.1, "snr_improvement": 12.2,
            "f0_min": 11.8, "f0_max": 16.2, "f0_median": 13.9, "duration": 3.0,
        },
    }
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_FILE.write_text(json.dumps(default, indent=2))


@router.get("/status")
async def demo_status() -> dict:
    """Returns whether the demo assets are ready and the current job state."""
    with _job_lock:
        return {
            "ready": _demo_ready(),
            "job": dict(_job_state),
        }


@router.get("/metadata")
async def demo_metadata() -> dict:
    """Returns acoustic metrics per noise type."""
    if not METADATA_FILE.exists():
        _write_default_metadata()
    return json.loads(METADATA_FILE.read_text())


@router.post("/generate")
async def demo_generate(background: BackgroundTasks) -> dict:
    """Trigger demo regeneration in background."""
    with _job_lock:
        if _job_state["status"] == "running":
            raise HTTPException(409, "demo generation already in progress")
        _job_state.update(status="running", progress=0, message="Starting...")
    background.add_task(_run_demo_script)
    return {"status": "started"}
