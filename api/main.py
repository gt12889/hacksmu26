"""
ElephantVoices Denoiser — FastAPI backend.

Endpoints:
    GET  /api/demo/status      — check if demo outputs exist + job state
    POST /api/demo/generate    — kick off background generation (synthetic mode)
    GET  /api/demo/metadata    — SNR/f0/duration metrics per noise type
    GET  /static/demo/{file}   — serve PNG spectrograms and WAV files
    GET  /                     — serve built React frontend (production)

Development:
    uvicorn api.main:app --reload --port 8000

Frontend (dev, separate terminal):
    cd frontend && npm run dev          # Vite proxies /api and /static → 8000
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Path setup ──────────────────────────────────────────────────────────────
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from pipeline.harmonic_processor import process_call  # noqa: E402
from pipeline.spectrogram import compute_stft  # noqa: E402
from scripts.demo_spectrograms import (  # noqa: E402
    NOISE_TYPES,
    build_synthetic_call,
    compute_snr_db,
    make_demo_figure,
)

# ── Output directory ────────────────────────────────────────────────────────
DEMO_DIR = _repo_root / "data" / "outputs" / "demo"
METADATA_FILE = DEMO_DIR / "metadata.json"

# ── Job state (module-level, single-process) ────────────────────────────────
_job: dict[str, Any] = {"status": "idle", "progress": 0, "message": ""}
_job_lock = threading.Lock()


def _set_job(**kwargs: Any) -> None:
    with _job_lock:
        _job.update(kwargs)


def _get_job() -> dict[str, Any]:
    with _job_lock:
        return dict(_job)


# ── Background generation task ──────────────────────────────────────────────
def _run_generation() -> None:
    import librosa  # local import to avoid slow startup

    _set_job(status="running", progress=0, message="Starting pipeline...")
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, Any] = {}

    try:
        for i, nt in enumerate(NOISE_TYPES):
            _set_job(
                progress=int(i / len(NOISE_TYPES) * 85),
                message=f"Processing {nt} noise type...",
            )

            y, sr, noise_clip, noise_type_dict = build_synthetic_call(nt)
            ctx = process_call(y, sr, noise_type_dict, noise_clip=noise_clip)

            # Save original (noisy) audio for A/B toggle
            orig_norm = y / (float(np.abs(y).max()) + 1e-10)
            sf.write(
                str(DEMO_DIR / f"{nt}_original.wav"),
                orig_norm,
                sr,
                subtype="PCM_16",
            )

            # Save 3-panel spectrogram PNG + cleaned WAV
            make_demo_figure(nt, ctx, y, DEMO_DIR)

            # Compute metadata
            freq_bins = ctx["freq_bins"]
            f0_contour = ctx["f0_contour"]
            f0_median = float(np.median(f0_contour))
            ctx_clean = compute_stft(ctx["audio_clean"], sr)

            snr_before = compute_snr_db(ctx["magnitude"], freq_bins, f0_median)
            snr_after = compute_snr_db(ctx_clean["magnitude"], freq_bins, f0_median)

            metadata[nt] = {
                "snr_before": round(snr_before, 1),
                "snr_after": round(snr_after, 1),
                "snr_improvement": round(snr_after - snr_before, 1),
                "f0_min": round(float(f0_contour.min()), 1),
                "f0_max": round(float(f0_contour.max()), 1),
                "f0_median": round(f0_median, 1),
                "duration": round(len(y) / sr, 1),
            }

        METADATA_FILE.write_text(json.dumps(metadata, indent=2))
        _set_job(status="done", progress=100, message="Complete")

    except Exception as exc:
        _set_job(status="error", progress=0, message=str(exc))
        raise


# ── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="ElephantVoices Denoiser API",
    description="HackSMU 2026 — Harmonic comb masking for infrasonic bioacoustics",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _all_outputs_exist() -> bool:
    return all(
        (DEMO_DIR / f"{nt}_demo.png").exists()
        and (DEMO_DIR / f"{nt}_clean.wav").exists()
        and (DEMO_DIR / f"{nt}_original.wav").exists()
        for nt in NOISE_TYPES
    )


# ── API routes ───────────────────────────────────────────────────────────────
@app.get("/api/demo/status")
def demo_status() -> dict[str, Any]:
    """Check whether demo outputs exist and return current job state."""
    return {"ready": _all_outputs_exist(), "job": _get_job()}


@app.post("/api/demo/generate")
def generate_demo() -> dict[str, Any]:
    """
    Kick off background generation of demo outputs (synthetic mode).
    Idempotent — returns current job state if already running.
    """
    job = _get_job()
    if job["status"] == "running":
        return {"message": "Already running", "job": job}

    _set_job(status="running", progress=0, message="Queued...")
    thread = threading.Thread(target=_run_generation, daemon=True)
    thread.start()
    return {"message": "Started", "job": _get_job()}


@app.get("/api/demo/metadata")
def get_metadata() -> dict[str, Any]:
    """Return per-noise-type metrics (SNR, f0, duration)."""
    if not METADATA_FILE.exists():
        raise HTTPException(status_code=404, detail="Metadata not yet generated. Call POST /api/demo/generate first.")
    return json.loads(METADATA_FILE.read_text())


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "elephantvoices-denoiser"}


# ── Static file mounts ───────────────────────────────────────────────────────
# Demo outputs (PNGs + WAVs) — created lazily when generation runs
DEMO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/demo", StaticFiles(directory=str(DEMO_DIR)), name="demo-static")

# Built React frontend (production) — only if dist/ exists
_dist = _repo_root / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
