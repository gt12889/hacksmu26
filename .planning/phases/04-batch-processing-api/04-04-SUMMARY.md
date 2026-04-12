---
phase: 04-batch-processing-api
plan: "04"
subsystem: api
tags: [fastapi, api, upload, process, status, result, batch, tdd, cors]
dependency_graph:
  requires: [pipeline.batch_runner.run_batch, pipeline.scoring, pipeline.harmonic_processor]
  provides: [api.main.app, api.jobs.JOB_REGISTRY, api.uploads.UPLOAD_REGISTRY, POST /api/upload, POST /api/process, GET /api/status/{job_id}, GET /api/result/{job_id}, GET /api/batch/summary]
  affects: [frontend React app]
tech_stack:
  added: [fastapi==0.135.3, uvicorn==0.44.0, python-multipart==0.0.26, pydantic==2.12.5, httpx (test dep)]
  patterns: [singleton-registry, BackgroundTasks-dispatch, UPLOAD_REGISTRY-process-handoff, TestClient-pytest]
key_files:
  created:
    - api/__init__.py
    - api/main.py
    - api/jobs.py
    - api/uploads.py
    - api/models.py
    - api/routes/__init__.py
    - api/routes/upload.py
    - api/routes/process.py
    - api/routes/status.py
    - api/routes/result.py
    - api/routes/batch.py
    - tests/test_api.py
  modified: []
decisions:
  - "UPLOAD_REGISTRY singleton in api/uploads.py; process.py resolves file_id to path via UPLOAD_REGISTRY.get() — 404 on miss"
  - "_run_job builds annotations_df from soundfile.info().duration with filename=Path(upload_path).name, start=0.0, end=duration; recordings_dir=Path(upload_path).parent"
  - "Spectrogram endpoint returns 404 with 'spectrogram not available' (not 500 or stub PNG) — batch_runner produces no PNG files in Phase 4"
  - "BackgroundTasks (not asyncio.create_task) used for _run_job — consistent with FastAPI lifecycle"
  - "datetime.now(timezone.utc) used instead of deprecated datetime.utcnow() — auto-fixed Rule 1"
metrics:
  duration: "5 minutes"
  completed_date: "2026-04-12"
  tasks_completed: 2
  files_changed: 12
---

# Phase 04 Plan 04: FastAPI API Package Summary

Complete `api/` package with FastAPI app, in-memory JOB_REGISTRY and UPLOAD_REGISTRY singletons, Pydantic v2 models, six route modules (upload, process, status, result, batch), CORS middleware, and 14-test pytest suite via TestClient — all 136 project tests pass.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create api/ package — all route files | ddd2674 | api/__init__.py, api/main.py, api/jobs.py, api/uploads.py, api/models.py, api/routes/{__init__,upload,process,status,result,batch}.py |
| 2 (RED+GREEN) | pytest suite for all API endpoints | add5fe2 | tests/test_api.py, api/routes/process.py (utcnow fix) |

## Decisions Made

- UPLOAD_REGISTRY singleton in `api/uploads.py`; routes import via `from api.uploads import UPLOAD_REGISTRY`. No re-instantiation anywhere.
- `_run_job` resolves upload path from `job["upload_path"]` (already absolute), builds a 1-row DataFrame with `filename=Path(upload_path).name`, `start=0.0`, `end=sf.info(upload_path).duration`, and sets `recordings_dir=Path(upload_path).parent` — this matches what `run_batch()` needs.
- Spectrogram endpoint returns 404 `{"detail": "spectrogram not available"}` when `png_path` key is absent or path doesn't exist. `batch_runner` produces no PNG files in Phase 4 — this is by design, not a stub.
- BackgroundTasks used for `_run_job` dispatch — keeps request handler non-blocking per FastAPI pattern.
- `datetime.now(timezone.utc)` replaces deprecated `datetime.utcnow()` (Python 3.12+ deprecation, auto-fixed Rule 1).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed datetime.utcnow() deprecation**
- **Found during:** Task 2 (test warnings)
- **Issue:** `datetime.utcnow()` is deprecated in Python 3.12+ and was generating DeprecationWarning in test output
- **Fix:** Replaced with `datetime.now(timezone.utc)` in `api/routes/process.py`
- **Files modified:** api/routes/process.py
- **Commit:** add5fe2

**2. [Rule 3 - Blocking] Installed httpx for FastAPI TestClient**
- **Found during:** Task 2 test collection
- **Issue:** `starlette.testclient` requires `httpx` but it was not in requirements.txt
- **Fix:** `pip install httpx` in venv. Note: httpx should be added to requirements.txt as a dev/test dependency
- **Files modified:** None (pip only)
- **Commit:** N/A (runtime fix)

## Known Stubs

None — all endpoints are fully implemented. The spectrogram endpoint intentionally returns 404 (not a stub — it documents that batch_runner produces no PNG files in Phase 4).

## Self-Check: PASSED
