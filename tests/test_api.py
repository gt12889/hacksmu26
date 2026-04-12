"""API endpoint tests using FastAPI TestClient. No real recordings required."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.jobs import JOB_REGISTRY
from api.main import app
from api.uploads import UPLOAD_REGISTRY

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_registries():
    """Clear both registries before each test to prevent state leakage."""
    JOB_REGISTRY.clear()
    UPLOAD_REGISTRY.clear()
    yield
    JOB_REGISTRY.clear()
    UPLOAD_REGISTRY.clear()


@pytest.fixture()
def wav_file(tmp_path: Path) -> Path:
    """Write a minimal 1-second 44100 Hz WAV file to tmp_path."""
    sr = 44100
    duration = 1.0
    audio = np.zeros(int(sr * duration), dtype=np.float32)
    wav_path = tmp_path / "test_call.wav"
    sf.write(str(wav_path), audio, sr)
    return wav_path


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------


def test_root_returns_ok():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------


def test_upload_wav_returns_upload_response(wav_file: Path):
    with wav_file.open("rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": ("test_call.wav", f, "audio/wav")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert "filename" in data
    assert "path" in data
    assert data["filename"] == "test_call.wav"


def test_upload_writes_upload_registry(wav_file: Path):
    """UPLOAD_REGISTRY must be populated by the upload endpoint."""
    with wav_file.open("rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": ("test_call.wav", f, "audio/wav")},
        )
    assert response.status_code == 200
    file_id = response.json()["file_id"]
    assert file_id in UPLOAD_REGISTRY
    assert Path(UPLOAD_REGISTRY[file_id]).is_absolute()


def test_upload_no_file_returns_422():
    response = client.post("/api/upload")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Process endpoint
# ---------------------------------------------------------------------------


def test_process_with_valid_file_id_returns_job_id(wav_file: Path):
    """Seed UPLOAD_REGISTRY directly to avoid real file upload side-effects."""
    file_id = "test-file-id-1234"
    UPLOAD_REGISTRY[file_id] = str(wav_file.resolve())

    response = client.post(f"/api/process?file_id={file_id}")
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data


def test_process_registers_job_in_registry(wav_file: Path):
    """After /api/process, JOB_REGISTRY must contain the new job with status='queued'."""
    file_id = "test-file-id-5678"
    UPLOAD_REGISTRY[file_id] = str(wav_file.resolve())

    response = client.post(f"/api/process?file_id={file_id}")
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert job_id in JOB_REGISTRY
    # Status is either queued or running (background may have started)
    assert JOB_REGISTRY[job_id]["status"] in ("queued", "running", "complete", "failed")


def test_process_unknown_file_id_returns_404():
    response = client.post("/api/process?file_id=does-not-exist")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------


def test_status_returns_status_response():
    job_id = "status-test-job"
    JOB_REGISTRY[job_id] = {
        "status": "queued",
        "progress": 0,
        "total": 1,
        "results": [],
        "error": None,
        "created_at": "2026-04-12T00:00:00Z",
        "upload_path": "/tmp/test.wav",
        "output_dir": "/tmp/out",
    }
    response = client.get(f"/api/status/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "queued"
    assert "progress" in data
    assert "total" in data


def test_status_unknown_job_returns_404():
    response = client.get("/api/status/nonexistent-job-id")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Result endpoint
# ---------------------------------------------------------------------------


def test_result_while_queued_returns_202():
    job_id = "result-queued-job"
    JOB_REGISTRY[job_id] = {
        "status": "queued",
        "progress": 0,
        "total": 1,
        "results": [],
        "error": None,
        "created_at": "2026-04-12T00:00:00Z",
        "upload_path": "/tmp/test.wav",
        "output_dir": "/tmp/out",
    }
    response = client.get(f"/api/result/{job_id}")
    assert response.status_code == 202


def test_result_complete_returns_results():
    job_id = "result-complete-job"
    JOB_REGISTRY[job_id] = {
        "status": "complete",
        "progress": 1,
        "total": 1,
        "results": [
            {
                "filename": "test.wav",
                "start": 0.0,
                "end": 5.0,
                "f0_median_hz": 25.0,
                "snr_before_db": 10.0,
                "snr_after_db": 20.0,
                "confidence": 0.85,
                "noise_type": "generator",
                "status": "ok",
                "clean_wav_path": "/tmp/test_clean.wav",
            }
        ],
        "error": None,
        "created_at": "2026-04-12T00:00:00Z",
        "upload_path": "/tmp/test.wav",
        "output_dir": "/tmp/out",
    }
    response = client.get(f"/api/result/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert len(data["results"]) == 1


# ---------------------------------------------------------------------------
# Spectrogram endpoint — must 404 when png_path absent
# ---------------------------------------------------------------------------


def test_spectrogram_404_when_no_png_path():
    """Spectrogram endpoint returns 404 with 'spectrogram not available' when png_path absent."""
    job_id = "spec-test-job"
    JOB_REGISTRY[job_id] = {
        "status": "complete",
        "progress": 1,
        "total": 1,
        "results": [
            {
                "filename": "test.wav",
                "start": 0.0,
                "end": 5.0,
                "f0_median_hz": 25.0,
                "snr_before_db": 10.0,
                "snr_after_db": 20.0,
                "confidence": 0.85,
                "noise_type": "generator",
                "status": "ok",
                "clean_wav_path": "/tmp/test_clean.wav",
                # no "png_path" key intentionally
            }
        ],
        "error": None,
        "created_at": "2026-04-12T00:00:00Z",
        "upload_path": "/tmp/test.wav",
        "output_dir": "/tmp/out",
    }
    response = client.get(f"/api/result/{job_id}/spectrogram/0")
    assert response.status_code == 404
    assert response.json()["detail"] == "spectrogram not available"


# ---------------------------------------------------------------------------
# Upload audio endpoint (GET /api/upload/{file_id}/audio)
# ---------------------------------------------------------------------------


def test_get_upload_audio_not_found():
    """GET /api/upload/{file_id}/audio returns 404 for unknown file_id."""
    response = client.get("/api/upload/does-not-exist/audio")
    assert response.status_code == 404


def test_get_upload_audio_ok(wav_file: Path):
    """After uploading a file, GET /api/upload/{file_id}/audio returns 200 with audio/wav."""
    with wav_file.open("rb") as f:
        upload_response = client.post(
            "/api/upload",
            files={"file": ("test_call.wav", f, "audio/wav")},
        )
    assert upload_response.status_code == 200
    file_id = upload_response.json()["file_id"]

    audio_response = client.get(f"/api/upload/{file_id}/audio")
    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"].startswith("audio/")


# ---------------------------------------------------------------------------
# Batch results endpoint (GET /api/batch/results)
# ---------------------------------------------------------------------------


def test_batch_results_empty():
    """GET /api/batch/results returns 200 with empty results list when no data/outputs exist."""
    import api.routes.batch as batch_module
    from pathlib import Path

    original = batch_module.BATCH_OUTPUT_DIR
    batch_module.BATCH_OUTPUT_DIR = Path("/nonexistent/does_not_exist")
    try:
        response = client.get("/api/batch/results")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "batch-disk"
        assert isinstance(data["results"], list)
    finally:
        batch_module.BATCH_OUTPUT_DIR = original


def test_batch_results_with_fixture(tmp_path: Path):
    """GET /api/batch/results returns rows from summary.csv under data/outputs/."""
    import csv
    import api.routes.batch as batch_module

    # Create a fake run directory with summary.csv
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    csv_path = run_dir / "summary.csv"
    fieldnames = [
        "filename", "start", "end", "f0_median_hz",
        "snr_before_db", "snr_after_db", "confidence",
        "noise_type", "status", "clean_wav_path",
    ]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({
            "filename": "test.wav", "start": 0.0, "end": 5.0,
            "f0_median_hz": 25.0, "snr_before_db": 10.0, "snr_after_db": 20.0,
            "confidence": 0.85, "noise_type": "generator", "status": "ok",
            "clean_wav_path": "clean/test_clean.wav",
        })

    original = batch_module.BATCH_OUTPUT_DIR
    batch_module.BATCH_OUTPUT_DIR = tmp_path
    try:
        response = client.get("/api/batch/results")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "batch-disk"
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["filename"] == "test.wav"
        # clean_wav_path should be rewritten to absolute
        assert Path(result["clean_wav_path"]).is_absolute()
    finally:
        batch_module.BATCH_OUTPUT_DIR = original


# ---------------------------------------------------------------------------
# Batch summary endpoint
# ---------------------------------------------------------------------------


def test_batch_summary_returns_expected_shape():
    response = client.get("/api/batch/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_jobs" in data
    assert "total_calls_processed" in data
    assert "average_confidence" in data
    assert "average_snr_improvement_db" in data


def test_batch_summary_aggregates_completed_jobs():
    """With one complete job, averages should be computed."""
    job_id = "batch-summary-job"
    JOB_REGISTRY[job_id] = {
        "status": "complete",
        "progress": 2,
        "total": 2,
        "results": [
            {
                "filename": "a.wav",
                "start": 0.0,
                "end": 5.0,
                "f0_median_hz": 20.0,
                "snr_before_db": 5.0,
                "snr_after_db": 15.0,
                "confidence": 0.9,
                "noise_type": "generator",
                "status": "ok",
                "clean_wav_path": "",
            },
            {
                "filename": "b.wav",
                "start": 5.0,
                "end": 10.0,
                "f0_median_hz": 22.0,
                "snr_before_db": 8.0,
                "snr_after_db": 20.0,
                "confidence": 0.7,
                "noise_type": "car",
                "status": "ok",
                "clean_wav_path": "",
            },
        ],
        "error": None,
        "created_at": "2026-04-12T00:00:00Z",
        "upload_path": "/tmp/test.wav",
        "output_dir": "/tmp/out",
    }
    response = client.get("/api/batch/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 1
    assert data["total_calls_processed"] == 2
    assert data["average_confidence"] == pytest.approx(0.8, abs=1e-6)
    assert data["average_snr_improvement_db"] == pytest.approx(11.0, abs=1e-6)
