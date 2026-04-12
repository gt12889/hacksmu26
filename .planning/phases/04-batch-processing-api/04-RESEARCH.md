# Phase 4: Batch Processing & API - Research

**Researched:** 2026-04-11
**Domain:** Python batch orchestration + FastAPI async job queue + Raven Pro export
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BATCH-01 | Process all 212 calls through full pipeline without manual intervention | `process_call()` already works per-call; need orchestrator loop + annotation-driven dispatch |
| BATCH-02 | Per-call confidence score (0–100%) based on harmonics survived, SNR improvement, harmonic integrity | `compute_snr_db()` already exists in demo_spectrograms.py; need to canonicalize and extend |
| BATCH-03 | Export each cleaned call as standalone WAV at native sample rate | `sf.write()` already used in process_call.py; batch runner adds path management |
| BATCH-04 | Summary CSV: filename, f0, SNR_before, SNR_after, confidence, noise_type | pandas DataFrame + `to_csv()` after collecting per-call result dicts |
| BATCH-05 | Raven Pro compatible export: WAV + selection table .txt | Raven Pro selection table format is plain TSV; document column schema |
| API-01 | POST /api/upload accepts audio file and stores it | FastAPI `UploadFile` + `tempfile` or `data/uploads/` staging dir |
| API-02 | POST /api/process triggers pipeline on uploaded file, returns job_id | BackgroundTasks dispatch; in-memory job registry |
| API-03 | GET /api/status/{job_id} returns status and progress | Poll-friendly dict: status/progress/eta |
| API-04 | GET /api/result/{job_id} returns cleaned audio + spectrogram data | `FileResponse` for WAV; JSON for spectrogram metadata; PNG for figure |
| API-05 | GET /api/batch/summary returns batch processing summary | Reads from summary CSV or live job registry |
| API-06 | API uses BackgroundTasks for async processing | FastAPI `BackgroundTasks`; no Celery/Redis |
</phase_requirements>

---

## Summary

Phase 4 builds two things that share a common orchestration layer: (1) a batch runner that drives all 212 calls through the existing `process_call()` entry point, scoring each and writing outputs, and (2) a FastAPI server that exposes upload/process/status/result endpoints backed by the same orchestration logic via `BackgroundTasks`.

The pipeline itself is complete. Phase 4 is primarily *plumbing*: connecting the per-call function to a loop, attaching a confidence scoring formula, serializing results to CSV and Raven Pro format, and wrapping everything behind a thin HTTP interface. The biggest design decision is the shape of the in-memory job registry and how it maps to the API response schema — get that right up front and all six API endpoints are mechanical.

FastAPI, uvicorn, and python-multipart are not yet in `requirements.txt` and must be added. Everything else the batch runner needs (librosa, soundfile, pandas, numpy, tqdm) is already installed.

**Primary recommendation:** Build the batch runner as a standalone Python module first (`pipeline/batch_runner.py`), validate it on 5 calls, then wrap it in FastAPI — never implement the pipeline inside route handlers.

---

## Standard Stack

### What is already installed (requirements.txt verified)

| Library | Version pinned | Role in Phase 4 |
|---------|----------------|-----------------|
| librosa | 0.11.0 | Audio loading via `load_call_segment()` (already used) |
| soundfile | >=0.12 | WAV export at native sr (`sf.write`) |
| numpy | >=1.26 | Array ops in confidence scoring |
| pandas | >=2.0 | Summary CSV generation, annotation iteration |
| tqdm | >=4.66 | Progress bar for batch loop |
| matplotlib | >=3.8 | Server-side spectrogram PNG (reuse `make_demo_figure` pattern) |

### What must be added to requirements.txt

| Library | Version | Purpose | Install |
|---------|---------|---------|---------|
| fastapi | 0.115+ | HTTP framework with BackgroundTasks and UploadFile | `pip install fastapi` |
| uvicorn[standard] | >=0.29 | ASGI server | `pip install "uvicorn[standard]"` |
| python-multipart | >=0.0.9 | Required by FastAPI `UploadFile` — file upload silently fails without this | `pip install python-multipart` |

### Installation command for missing packages

```bash
pip install fastapi "uvicorn[standard]" python-multipart
```

Then add these three lines to `requirements.txt` under a `# Web API` comment.

---

## Architecture Patterns

### Recommended project structure additions for Phase 4

```
hacksmu26/
├── pipeline/
│   ├── batch_runner.py        # NEW: orchestrates all 212 calls, emits results list
│   └── scoring.py             # NEW: compute_confidence(), compute_snr_db() (lifted from demo_spectrograms.py)
├── api/
│   ├── main.py                # NEW: FastAPI app, CORS, lifespan
│   ├── jobs.py                # NEW: in-memory job registry dict
│   ├── models.py              # NEW: Pydantic request/response schemas
│   └── routes/
│       ├── upload.py          # NEW: POST /api/upload
│       ├── process.py         # NEW: POST /api/process
│       ├── status.py          # NEW: GET /api/status/{job_id}
│       ├── result.py          # NEW: GET /api/result/{job_id}
│       └── batch.py           # NEW: GET /api/batch/summary
└── scripts/
    └── batch_process.py       # NEW: CLI entrypoint for offline batch run
```

### Pattern 1: Batch Runner as Pure Python Module

**What:** `pipeline/batch_runner.py` iterates over annotation rows, calls `process_call()` per row, collects result dicts, computes confidence scores, and writes outputs. Takes a progress callback so the FastAPI background task can update the job registry.

**When to use:** Always — this is the only safe architecture. Do not put annotation iteration or file I/O inside FastAPI route handlers.

**Example:**
```python
# pipeline/batch_runner.py
def run_batch(
    annotations: pd.DataFrame,
    recordings_dir: Path,
    output_dir: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """
    Process all rows in annotations DataFrame through process_call().

    Args:
        annotations: DataFrame from parse_annotations() — must have filename, start, end
        recordings_dir: Directory containing source WAV files
        output_dir: Directory to write cleaned WAVs and spectrograms
        progress_callback: Optional fn(completed, total) called after each call

    Returns:
        List of per-call result dicts (one per annotation row)
    """
    results = []
    total = len(annotations)
    for i, row in enumerate(annotations.itertuples()):
        wav_path = recordings_dir / row.filename
        y, sr = load_call_segment(wav_path, row.start, row.end)
        # ... noise classification + process_call() + scoring ...
        results.append(result_dict)
        if progress_callback:
            progress_callback(i + 1, total)
    return results
```

### Pattern 2: In-Memory Job Registry

**What:** A module-level dict `JOB_REGISTRY: dict[str, dict]` holds all job state. FastAPI reads and writes it from background tasks and route handlers. No Redis, no SQLite.

**When to use:** Single-server hackathon demo with at most a handful of concurrent jobs.

**Shape:**
```python
JOB_REGISTRY = {
    "abc123": {
        "status": "running",   # "queued" | "running" | "complete" | "failed"
        "progress": 47,        # calls completed
        "total": 212,
        "results": [],         # populated when complete
        "error": None,         # set if status == "failed"
        "created_at": "2026-04-11T12:00:00Z",
    }
}
```

**Pitfall to avoid:** Job registry must be a module-level singleton, not instantiated per-request. Import from `api/jobs.py` everywhere — do not recreate the dict in each route.

### Pattern 3: FastAPI BackgroundTasks Dispatch

**What:** POST /api/process creates a job_id, registers it in JOB_REGISTRY as "queued", then uses `background_tasks.add_task(run_batch_job, job_id, ...)` to run processing after the response is sent.

**Critical detail:** `BackgroundTasks` runs in the same process as the server. CPU-bound NumPy operations do not yield the event loop. For 212 calls this is acceptable (one user, demo) but means the server becomes unresponsive during processing for other requests. For Phase 5 (React frontend), the frontend only polls — it never sends concurrent requests that need to be served while batch runs.

**Example:**
```python
# api/routes/process.py
from fastapi import APIRouter, BackgroundTasks
from api.jobs import JOB_REGISTRY
from pipeline.batch_runner import run_batch
import uuid

router = APIRouter()

@router.post("/api/process")
async def trigger_process(background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    JOB_REGISTRY[job_id] = {"status": "queued", "progress": 0, "total": 0, "results": []}
    background_tasks.add_task(_run_job, job_id)
    return {"job_id": job_id}

def _run_job(job_id: str) -> None:
    try:
        JOB_REGISTRY[job_id]["status"] = "running"
        results = run_batch(..., progress_callback=lambda done, total: _update_progress(job_id, done, total))
        JOB_REGISTRY[job_id]["status"] = "complete"
        JOB_REGISTRY[job_id]["results"] = results
    except Exception as e:
        JOB_REGISTRY[job_id]["status"] = "failed"
        JOB_REGISTRY[job_id]["error"] = str(e)
```

### Pattern 4: CORS Middleware (required before React frontend)

Phase 5 React dev server runs on port 5173. CORS must be added to `api/main.py` in the first commit — not when debugging.

```python
# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For hackathon local-only use, `allow_origins=["*"]` is acceptable.

### Pattern 5: Confidence Score Formula

**What:** Combine three signals into a 0–100 normalized score.

**Formula:**
```python
# pipeline/scoring.py

def compute_confidence(
    ctx: dict,
    snr_before: float,
    snr_after: float,
    harmonic_bins_total: int,
    harmonic_bins_masked: int,
) -> float:
    """
    0–100 confidence score for a processed call.

    Components:
      - SNR improvement (0–40 points): delta SNR capped at 20 dB maps to 40 pts
      - Harmonic mask coverage (0–40 points): fraction of harmonic bins retained
      - f0 stability (0–20 points): 1 - (f0_std / f0_mean), capped at 1.0

    Returns:
        float in [0.0, 100.0]
    """
    # SNR improvement component
    snr_delta = max(0.0, snr_after - snr_before)
    snr_score = min(snr_delta / 20.0, 1.0) * 40.0

    # Harmonic integrity (fraction of expected harmonic bins that have non-zero mask)
    if harmonic_bins_total > 0:
        integrity_score = (harmonic_bins_masked / harmonic_bins_total) * 40.0
    else:
        integrity_score = 0.0

    # f0 stability (lower variance = higher confidence)
    f0 = ctx["f0_contour"]
    f0_mean = float(np.mean(f0))
    f0_std = float(np.std(f0))
    stability = max(0.0, 1.0 - (f0_std / (f0_mean + 1e-6)))
    stability_score = stability * 20.0

    return float(snr_score + integrity_score + stability_score)
```

`compute_snr_db()` already exists in `scripts/demo_spectrograms.py` — lift it verbatim into `pipeline/scoring.py`.

### Pattern 6: Raven Pro Selection Table Format

**What:** Raven Pro reads a tab-delimited `.txt` file alongside the WAV. The minimum columns required by Raven Pro are:

```
Selection\tView\tChannel\tBegin Time (s)\tEnd Time (s)\tLow Freq (Hz)\tHigh Freq (Hz)
```

**Example generator function:**
```python
# pipeline/batch_runner.py (or pipeline/raven_export.py)
import csv

def write_raven_selection_table(
    output_path: Path,
    calls: list[dict],  # each dict has: start, end, f0_median, confidence
) -> None:
    """Write Raven Pro compatible selection table TSV."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow([
            "Selection", "View", "Channel",
            "Begin Time (s)", "End Time (s)",
            "Low Freq (Hz)", "High Freq (Hz)"
        ])
        for i, call in enumerate(calls, start=1):
            writer.writerow([
                i, "Spectrogram 1", 1,
                f"{call['start']:.6f}",
                f"{call['end']:.6f}",
                f"{call['f0_median'] * 0.5:.2f}",   # half-octave below f0
                f"{call['f0_median'] * 10:.2f}",     # 10x f0 (covers harmonics)
            ])
```

Raven Pro DOES NOT require any special binary format — plain TSV with the column header row above is sufficient. Verified against Raven Pro 2.0 documentation and common community usage.

### Pattern 7: Server-Side Spectrogram PNG for API Result

Reuse `make_demo_figure()` from `scripts/demo_spectrograms.py`. The function already accepts `ctx` and writes a PNG. For the API, call it during batch processing and store the PNG path in the job results dict. Serve via `FileResponse`.

```python
# In batch_runner.py, after process_call():
from scripts.demo_spectrograms import make_demo_figure
png_path, wav_path = make_demo_figure(noise_type, ctx, y, output_dir / call_id)
```

Or more cleanly, lift `make_demo_figure` into `pipeline/` so it is importable without the `scripts/` path hack.

### Anti-Patterns to Avoid

- **Pipeline code inside route handlers:** Putting `process_call()` directly in a FastAPI `@router.post` handler — can't test it standalone, import errors break the whole API.
- **Synchronous processing without BackgroundTasks:** Running batch in the request handler — HTTP timeout after 30s, React shows a failed request.
- **Re-instantiating job registry per request:** `JOB_REGISTRY = {}` inside an `__init__` call — jobs from previous requests disappear.
- **`await` on NumPy operations:** Writing `await process_call(...)` — NumPy is synchronous; `await` does nothing and gives false confidence in async behavior.
- **Loading all 212 audio arrays into RAM before processing:** Collect all `(y, sr)` pairs in a list before iterating — triggers OOM. Process one call at a time, discard the array after writing output.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP file upload | Manual socket or base64 JSON | FastAPI `UploadFile` + python-multipart | Handles chunked transfer, Content-Type, temp file |
| Async job execution | Thread management, asyncio.create_task | FastAPI `BackgroundTasks` | Built-in; works correctly with ASGI lifecycle |
| WAV export | Raw PCM byte writing | `soundfile.sf.write()` | Handles subtype (PCM_16/FLOAT), sample rate, metadata |
| CSV export | Manual file.write() | `pandas.DataFrame.to_csv()` | Handles quoting, encoding, None values |
| CORS headers | Manual response header injection | `fastapi.middleware.cors.CORSMiddleware` | Handles preflight OPTIONS, all methods |
| UUID job IDs | Timestamp or counter | `uuid.uuid4()` | Collision-resistant, sortable with UUIDv7 if needed |
| Spectrogram PNG | Custom matplotlib pipeline | Reuse `make_demo_figure()` from Phase 3 | Already written, tested, matches publication quality |

**Key insight:** The batch runner is new code, but it is *thin* — it combines existing pieces. The only genuinely new logic is the confidence formula and the Raven Pro TSV writer.

---

## Common Pitfalls

### Pitfall 1: FastAPI Blocking on CPU-Bound Batch Processing

**What goes wrong:** Batch runs inside `BackgroundTasks` but blocks the event loop. GET /api/status polls return no response while batch is running. React frontend shows spinner forever.

**Why it happens:** NumPy/librosa are synchronous. `BackgroundTasks` runs in the ASGI event loop by default.

**How to avoid:** For a single-user demo this is acceptable — the frontend only polls, so the 2s polling requests just queue up and fire when the batch tick completes. If polling must be truly concurrent, wrap the batch call in `asyncio.get_event_loop().run_in_executor(None, run_batch, ...)`. This is not required for Phase 4 but is a clean upgrade.

**Warning signs:** GET /api/status returns nothing during batch run (not even a timeout — just hangs). Add a `time.sleep(0)` yield at the top of `_update_progress()` to force event loop ticks.

### Pitfall 2: progress_callback Race Condition

**What goes wrong:** progress_callback writes to `JOB_REGISTRY[job_id]["progress"]` from the background task while a request handler reads it simultaneously. In CPython the GIL prevents true corruption, but the read may see a stale value.

**Why it happens:** No locking around the shared dict.

**How to avoid:** For this demo (one server, one batch job at a time) the GIL is sufficient protection. Do not add threading.Lock unless you see actual corruption — it adds complexity for no benefit at this scale.

### Pitfall 3: Annotation Rows Without Matching WAV Files

**What goes wrong:** `parse_annotations()` returns rows for recordings not present in `recordings_dir`. Batch runner crashes on the first missing file, losing all prior results.

**Why it happens:** The 44 recordings may not all be present (gitignored, not copied to server).

**How to avoid:** At the start of `run_batch()`, validate all `wav_path.exists()` before starting. Log missing files and skip them (don't crash). Return a `"skipped"` status in the result dict for those rows.

### Pitfall 4: generate_snr_db Called With Wrong Magnitude

**What goes wrong:** `compute_snr_db(ctx["magnitude"], ...)` is called on the *original* pre-denoising spectrogram for SNR_before and SNR_after. Developer mistakenly uses `ctx["masked_magnitude"]` for SNR_after instead of re-computing STFT on `ctx["audio_clean"]`.

**Why it happens:** `masked_magnitude` looks like it should measure the cleaned signal power. But it is the comb-masked original — it does not reflect the additional noisereduce pass.

**How to avoid:** For SNR_after: call `compute_stft(ctx["audio_clean"], sr)` to get the true post-noisereduce magnitude, then compute SNR on that. This is exactly what `make_demo_figure()` already does (it calls `ctx_clean = compute_stft(ctx["audio_clean"], sr)`). Replicate that pattern in `scoring.py`.

### Pitfall 5: WAV Clipping on Export

**What goes wrong:** `audio_clean` values exceed ±1.0 after noisereduce. `sf.write(..., subtype="PCM_16")` clips silently, introducing distortion.

**Why it happens:** noisereduce can produce outputs with amplitudes slightly above the input range.

**How to avoid:** Normalize before writing: `audio_norm = audio / (np.abs(audio).max() + 1e-10)`. Already done in `make_demo_figure()` — replicate this in the batch runner's WAV export.

### Pitfall 6: Missing python-multipart Causes Silent Upload Failure

**What goes wrong:** FastAPI `UploadFile` raises a 422 error with body `{"detail":"..."}` if `python-multipart` is not installed. The error message does not mention the missing package.

**Why it happens:** FastAPI lists python-multipart as an optional dependency.

**How to avoid:** Add `python-multipart` to requirements.txt now, before writing any upload route.

### Pitfall 7: Raven Pro Rejects TSV with Wrong Decimal Separator

**What goes wrong:** On non-English locale systems, Python's default float formatting may use commas as decimal separators. Raven Pro requires dots.

**How to avoid:** Use `f"{value:.6f}"` for all float fields in the TSV writer. Do not use `str(float_value)` on locale-sensitive systems.

---

## Code Examples

### File upload endpoint

```python
# api/routes/upload.py
# Source: FastAPI official docs — https://fastapi.tiangolo.com/tutorial/request-files/
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()

@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{file_id}_{file.filename}"
    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)
    return {"file_id": file_id, "filename": file.filename, "path": str(dest)}
```

### Status endpoint

```python
# api/routes/status.py
from fastapi import APIRouter, HTTPException
from api.jobs import JOB_REGISTRY

router = APIRouter()

@router.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in JOB_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    job = JOB_REGISTRY[job_id]
    eta_seconds = None
    if job["status"] == "running" and job["progress"] > 0:
        # Rough ETA based on elapsed rate — not shown here for brevity
        pass
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "total": job["total"],
        "eta_seconds": eta_seconds,
    }
```

### Summary CSV generation

```python
# pipeline/batch_runner.py (write_summary_csv)
import pandas as pd
from pathlib import Path

def write_summary_csv(results: list[dict], output_path: Path) -> None:
    """
    Write per-call metrics to CSV.

    Required columns: filename, f0_median_hz, snr_before_db, snr_after_db,
                      confidence, noise_type
    """
    rows = []
    for r in results:
        rows.append({
            "filename": r["filename"],
            "f0_median_hz": round(r["f0_median"], 2),
            "snr_before_db": round(r["snr_before"], 2),
            "snr_after_db": round(r["snr_after"], 2),
            "confidence": round(r["confidence"], 1),
            "noise_type": r["noise_type"],
            "status": r.get("status", "complete"),
        })
    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"[batch] Summary CSV written: {output_path} ({len(rows)} rows)")
```

### Result endpoint (WAV + metadata)

```python
# api/routes/result.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from api.jobs import JOB_REGISTRY

router = APIRouter()

@router.get("/api/result/{job_id}")
async def get_result(job_id: str):
    if job_id not in JOB_REGISTRY:
        raise HTTPException(status_code=404, detail="Job not found")
    job = JOB_REGISTRY[job_id]
    if job["status"] != "complete":
        raise HTTPException(status_code=202, detail=f"Job status: {job['status']}")
    # Return summary metadata; WAV/PNG served by separate /audio and /spectrogram routes
    return {"job_id": job_id, "results": job["results"]}

@router.get("/api/result/{job_id}/audio/{call_index}")
async def get_audio(job_id: str, call_index: int):
    job = JOB_REGISTRY.get(job_id)
    if not job or job["status"] != "complete":
        raise HTTPException(status_code=404)
    result = job["results"][call_index]
    return FileResponse(result["clean_wav_path"], media_type="audio/wav")

@router.get("/api/result/{job_id}/spectrogram/{call_index}")
async def get_spectrogram(job_id: str, call_index: int):
    job = JOB_REGISTRY.get(job_id)
    if not job or job["status"] != "complete":
        raise HTTPException(status_code=404)
    result = job["results"][call_index]
    return FileResponse(result["png_path"], media_type="image/png")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Celery + Redis for background tasks | FastAPI BackgroundTasks for single-server | FastAPI 0.90+ | Eliminates 2 infrastructure dependencies; BackgroundTasks runs in-process |
| Pydantic v1 models | Pydantic v2 required | FastAPI 0.100+ | `model_dump()` replaces `.dict()`; `model_validate()` replaces `.parse_obj()` |
| `scipy.signal.spectrogram()` | `scipy.signal.ShortTimeFFT` | scipy 1.13 | Not relevant here — pipeline uses librosa STFT; just don't mix |
| Manual multipart parsing | `python-multipart` via FastAPI `UploadFile` | FastAPI early versions | All upload handling is declarative |

**Deprecated/outdated:**
- `Pydantic v1 .dict()` / `.parse_obj()`: Both removed in Pydantic v2. FastAPI 0.115+ requires Pydantic v2. Use `model_dump()` and `model_validate()`.

---

## Open Questions

1. **Does the annotations file have a `noise_type` column?**
   - What we know: `demo_spectrograms.py` checks for `noise_type_col` and falls back to auto-classification.
   - What's unclear: Whether the 212-row annotation spreadsheet has this column pre-populated.
   - Recommendation: Design batch_runner to use the column if present, fall back to `classify_noise_type()` per recording if absent. This is already the pattern in `select_calls_from_annotations()`.

2. **Batch run: sequential vs. parallel?**
   - What we know: STACK.md recommends `concurrent.futures.ProcessPoolExecutor`. ARCHITECTURE.md notes the first bottleneck is CPU-heavy STFT.
   - What's unclear: How many CPU cores are available on the demo machine.
   - Recommendation: Start sequential with tqdm. If a full run takes >20 minutes, add `ProcessPoolExecutor(max_workers=4)`. Sequential is simpler and avoids pickling issues with large NumPy arrays across process boundaries.

3. **How should the upload endpoint handle the full-recording-plus-annotations case?**
   - What we know: API-01 says "accepts audio file." The batch pipeline needs both WAV files and an annotation CSV.
   - What's unclear: Whether upload will receive individual call clips (already segmented) or full recordings + CSV.
   - Recommendation: Design POST /api/upload to accept either: (a) a single WAV clip for immediate processing, or (b) a WAV + CSV pair for batch. Return a `upload_type: "clip" | "batch"` field in the response. Phase 5 React frontend can then decide which /process mode to trigger.

---

## Sources

### Primary (HIGH confidence)
- FastAPI official docs (fastapi.tiangolo.com) — BackgroundTasks, UploadFile, CORS middleware, FileResponse patterns. All patterns cited above are from the official tutorial section.
- Existing codebase: `pipeline/harmonic_processor.py`, `pipeline/ingestor.py`, `pipeline/spectrogram.py`, `pipeline/config.py`, `scripts/process_call.py`, `scripts/demo_spectrograms.py` — all read directly. Entry points, return shapes, and scoring helpers confirmed from source.
- `requirements.txt` — verified FastAPI/uvicorn/python-multipart are absent; all DSP libraries are present.

### Secondary (MEDIUM confidence)
- Raven Pro selection table format: TSV with header row `Selection\tView\tChannel\tBegin Time (s)\tEnd Time (s)\tLow Freq (Hz)\tHigh Freq (Hz)` — confirmed from multiple community sources and Cornell Lab Raven Pro documentation excerpts. The exact column names match what Raven Pro 2.0 imports.
- `compute_snr_db()` formula in `scripts/demo_spectrograms.py` — used as the basis for `pipeline/scoring.py`. Already validated by the Phase 3 demo run.

### Tertiary (LOW confidence — verify before implementing)
- Confidence score weights (40/40/20 for SNR/integrity/stability) — proposed formula, not validated against domain literature. Treat as a starting point; adjust weights after reviewing batch output on real calls.

---

## Metadata

**Confidence breakdown:**
- Standard stack (FastAPI/uvicorn/python-multipart): HIGH — FastAPI official docs, verified against existing requirements.txt
- Batch runner architecture: HIGH — derived directly from reading existing `process_call()`, `ingestor.py`, and `demo_spectrograms.py` code
- Raven Pro format: MEDIUM — TSV schema from community sources, not from Raven Pro source code
- Confidence formula weights: LOW — proposed heuristic, no published standard for this domain

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (FastAPI stable; no fast-moving dependencies introduced)
