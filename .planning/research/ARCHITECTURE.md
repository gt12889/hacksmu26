# Architecture Research

**Domain:** Bioacoustic audio DSP pipeline with FastAPI backend and React frontend
**Researched:** 2026-04-11
**Confidence:** HIGH (core DSP patterns) / MEDIUM (integration patterns, verified with official docs + multiple sources)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        REACT FRONTEND                           │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────────┐    │
│  │ Upload Panel │  │  Spectrogram  │  │  Dashboard /      │    │
│  │ (drag+drop)  │  │  Viewer (A/B) │  │  Confidence Table │    │
│  └──────┬───────┘  └───────┬───────┘  └─────────┬─────────┘    │
│         │                 │                     │              │
│         └─────────────────┴─────────────────────┘              │
│                           │ HTTP (REST)                         │
├───────────────────────────┼─────────────────────────────────────┤
│                      FASTAPI BACKEND                            │
│  ┌───────────────┐  ┌─────┴──────┐  ┌─────────────────────┐    │
│  │ /upload       │  │ /status    │  │ /results/{job_id}   │    │
│  │ /process      │  │ /{job_id}  │  │ /audio/{call_id}    │    │
│  └──────┬────────┘  └─────┬──────┘  └──────────┬──────────┘    │
│         │                 │                     │              │
│  ┌──────┴─────────────────┴─────────────────────┴──────────┐   │
│  │                  Job Registry (in-memory dict)           │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                             │ BackgroundTasks                   │
├─────────────────────────────┼───────────────────────────────────┤
│                     DSP PIPELINE (Python)                       │
│  ┌────────────┐  ┌──────────┴────────┐  ┌────────────────────┐  │
│  │  Ingestor  │→ │  Batch Orchestr.  │→ │   Per-Call Runner  │  │
│  │  (parse    │  │  (segments.csv    │  │  (processes single │  │
│  │   CSV,     │  │   → call queue)   │  │   call through     │  │
│  │   segment) │  │                   │  │   all stages)      │  │
│  └────────────┘  └───────────────────┘  └──────────┬─────────┘  │
│                                                     │           │
│  ┌──────────────────────────────────────────────────▼─────────┐  │
│  │                     PROCESSING STAGES                      │  │
│  │  1. STFT         → complex spectrogram (n_fft=8192)        │  │
│  │  2. HPSS         → harmonic component isolated             │  │
│  │  3. SHS          → f0 detected per frame                   │  │
│  │  4. Comb Mask    → time-varying harmonic mask built        │  │
│  │  5. Spectral Gate → residual noise floor removed           │  │
│  │  6. ISTFT        → clean audio waveform reconstructed      │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                  FILE STORAGE (local disk)                  │  │
│  │  recordings/   segments/   outputs/   spectrograms/         │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|---------------|----------------|
| Ingestor | Parse annotations CSV, slice 212 calls from 44 WAVs, emit (wav_path, start, end, noise_type) tuples | Python: pandas + librosa.load with offset/duration |
| Batch Orchestrator | Accept call list, dispatch per-call jobs, track progress dict, write confidence scores | Python dataclass job registry |
| Per-Call Runner | Execute all 6 processing stages in sequence, return cleaned WAV + metadata | Pure function: audio_array → result dict |
| STFT Stage | High-resolution time-frequency representation, n_fft=8192, hop_length=512 | librosa.stft |
| HPSS Stage | Separate harmonic from percussive/noise components; Zeppelzauer enhancement = wider harmonic margin | librosa.decompose.hpss with margin parameter |
| SHS Detector | Estimate f0 per frame by summing energy at subharmonic positions; exploit 2nd harmonic dominance in elephant calls | scipy-based: sum spectrogram rows at f, f/2, f/3 candidates |
| Comb Mask Builder | Build time-varying binary/soft mask at f0 and integer multiples (1×, 2×, 3× ... 10×) | numpy: mask[:, t] set true at ±bandwidth around k*f0[t] |
| Spectral Gate | Remove residual broadband noise floor below adaptive threshold | noisereduce: estimate noise profile from non-call frames |
| ISTFT Reconstructor | Convert masked spectrogram back to audio waveform | librosa.istft + soundfile.write |
| Job Registry | Hold {job_id: {status, progress, results}} in memory; no DB required for hackathon | Python dict wrapped in FastAPI state |
| FastAPI Backend | HTTP endpoints for file upload, job trigger, status poll, result download | FastAPI + BackgroundTasks (no Celery needed at this scale) |
| React Frontend | Upload UI, spectrogram viewer (before/after), audio A/B player, confidence dashboard | Vite + TypeScript + wavesurfer.js or custom canvas |

## Recommended Project Structure

```
hacksmu26/
├── pipeline/                  # Pure DSP — no FastAPI imports
│   ├── ingestor.py            # CSV parse, WAV slicing, call list emit
│   ├── orchestrator.py        # Batch dispatch, progress tracking
│   ├── stages/
│   │   ├── stft.py            # Thin wrapper: params, forward/inverse
│   │   ├── hpss.py            # Zeppelzauer margin config
│   │   ├── shs.py             # Subharmonic summation f0 detector
│   │   ├── comb_mask.py       # Time-varying harmonic comb builder
│   │   ├── spectral_gate.py   # noisereduce wrapper with noise profile
│   │   └── reconstruct.py     # ISTFT + WAV export
│   ├── runner.py              # Composes stages for a single call
│   └── scoring.py             # Confidence metric (SNR delta, mask coverage)
├── api/
│   ├── main.py                # FastAPI app, CORS, mounts
│   ├── routes/
│   │   ├── upload.py          # POST /upload (multipart WAV or CSV)
│   │   ├── process.py         # POST /process (trigger batch)
│   │   ├── status.py          # GET /status/{job_id}
│   │   └── results.py         # GET /results/{job_id}, /audio/{call_id}
│   ├── jobs.py                # In-memory job registry
│   └── models.py              # Pydantic request/response schemas
├── frontend/                  # Vite + React + TypeScript
│   ├── src/
│   │   ├── components/
│   │   │   ├── UploadPanel.tsx
│   │   │   ├── SpectrogramViewer.tsx  # before/after + mask overlay
│   │   │   ├── AudioPlayer.tsx        # A/B toggle, wavesurfer or HTML5
│   │   │   └── ConfidenceTable.tsx    # sortable call list
│   │   ├── hooks/
│   │   │   ├── useJobStatus.ts        # polling /status/{id}
│   │   │   └── useAudioPlayer.ts
│   │   └── api/
│   │       └── client.ts              # typed fetch wrappers
│   └── vite.config.ts
├── data/
│   ├── recordings/            # 44 original WAVs (gitignored)
│   ├── segments/              # 212 sliced calls (generated)
│   ├── outputs/               # cleaned WAVs (generated)
│   └── annotations.csv        # timestamps + noise_type labels
└── scripts/
    ├── batch_process.py       # CLI entrypoint: run all 212 calls
    └── compare_lalal.py       # side-by-side SNR comparison script
```

### Structure Rationale

- **pipeline/ isolated from api/:** DSP stages can be tested standalone, run from CLI, and imported by FastAPI without circular dependencies. This also lets two team members work on pipeline vs API simultaneously.
- **stages/ as separate files:** Each stage has a single input/output contract (numpy array in, numpy array or mask out). Swapping parameters or implementations does not ripple across the codebase.
- **api/jobs.py registry:** An in-memory dict is sufficient for a hackathon demo with one server process. Avoids Redis/Celery complexity that would cost multiple hours of setup time.
- **data/ gitignored:** Large binary WAVs stay out of the repository; only annotations.csv is committed.

## Architectural Patterns

### Pattern 1: Linear Stage Pipeline with Named Outputs

**What:** Each processing stage is a pure function that receives a context dict and returns an updated context dict. Stages do not call each other; the runner composes them.

**When to use:** When stages have clear inputs/outputs and must be individually debuggable. Essential here — you need to inspect the spectrogram before and after each stage to verify correctness.

**Trade-offs:** Slightly more memory (context dict holds all intermediate arrays) but makes debugging trivial. For a hackathon this is the correct trade-off.

**Example:**
```python
def run_pipeline(audio: np.ndarray, sr: int, noise_type: str) -> dict:
    ctx = {"audio": audio, "sr": sr, "noise_type": noise_type}
    ctx = compute_stft(ctx)       # adds ctx["S"], ctx["phase"]
    ctx = apply_hpss(ctx)         # adds ctx["S_harmonic"]
    ctx = detect_f0_shs(ctx)      # adds ctx["f0_contour"]
    ctx = build_comb_mask(ctx)    # adds ctx["mask"]
    ctx = apply_spectral_gate(ctx) # adds ctx["S_clean"]
    ctx = reconstruct_audio(ctx)  # adds ctx["audio_clean"]
    return ctx
```

### Pattern 2: Poll-Based Job Status (no WebSocket needed)

**What:** Frontend POST to /process → gets job_id back immediately. Then polls GET /status/{job_id} every 2 seconds until status == "complete". This keeps the API stateless-ish and requires no WebSocket complexity.

**When to use:** Processing jobs that take 5-30 seconds. WebSockets add ~2 hours of complexity for marginal UX benefit.

**Trade-offs:** 2-second polling latency is acceptable for a demo. Not appropriate for production with high job volume.

**Example:**
```python
# api/routes/process.py
@router.post("/process")
async def trigger_processing(background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    job_registry[job_id] = {"status": "queued", "progress": 0}
    background_tasks.add_task(run_batch, job_id)
    return {"job_id": job_id}
```

### Pattern 3: Noise-Type Adaptive Strategy

**What:** HPSS margin and spectral gate aggressiveness vary by noise_type field from the annotations CSV. Generator noise (constant tonal) gets narrow-bandwidth comb removal. Plane noise (slow sweep) gets wider temporal smoothing on the mask.

**When to use:** Any time the same algorithm should have different hyperparameters for different noise regimes. Avoids one-size-fits-all tuning that degrades performance across noise types.

**Trade-offs:** Requires labeled noise types in annotations (already available). Adds a config branch per noise type but is straightforward to implement.

## Data Flow

### Batch Processing Flow

```
annotations.csv + recordings/
        ↓
   Ingestor
   (parse timestamps, slice WAV segments)
        ↓
   segments/ (212 WAV files on disk)
        ↓
   Batch Orchestrator
   (enqueue calls, update progress)
        ↓  (per call, sequential or thread-pool)
   Per-Call Runner
        ↓
   [STFT → HPSS → SHS → CombMask → SpectralGate → ISTFT]
        ↓
   outputs/{call_id}_clean.wav  +  confidence score
        ↓
   Job Registry updated with results dict
```

### Web Request Flow

```
Browser → POST /upload (wav files or CSV)
              ↓
         FastAPI saves to disk, returns file_ids
              ↓
Browser → POST /process (file_ids)
              ↓
         FastAPI creates job_id, fires BackgroundTask
              ↓ (async, non-blocking)
         Pipeline runs all 212 calls
              ↓
Browser → GET /status/{job_id}  (polls every 2s)
              ↓
         Returns {status, progress: 0-212, eta}
              ↓ (when status == "complete")
Browser → GET /results/{job_id}
              ↓
         Returns [{call_id, confidence, noisy_url, clean_url}]
              ↓
Browser renders SpectrogramViewer + AudioPlayer per call
```

### Spectrogram Visualization Flow

```
GET /results → clean_url + noisy_url (WAV endpoints)
    ↓
Frontend: fetch WAV → decode ArrayBuffer → Web Audio API
    ↓
Compute FFT client-side OR fetch pre-rendered PNG from API
    ↓  (recommended: API returns PNG, avoids heavy JS FFT)
<canvas> renders spectrogram with color map
Comb mask overlay: fetch /mask/{call_id} → JSON array of
  (freq_bin, time_frame) pairs → draw as colored bands
```

### Key Data Flows

1. **Annotation CSV → call segments:** pandas reads CSV, extracts (file, start_sec, end_sec, noise_type) per row, librosa.load with offset+duration slices each segment, soundfile.write saves to segments/.
2. **Spectrogram → mask → clean audio:** S_harmonic (from HPSS) is multiplied elementwise by the comb mask; the result is passed through noisereduce; librosa.istft reconstructs waveform. Phase is preserved from the original STFT to avoid musical noise artifacts.
3. **Confidence scoring:** SNR of clean segment vs. estimated noise floor, divided by max observed SNR across the batch, normalized 0-100. Calls with f0 detection confidence below threshold get flagged.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Demo (1 user, 212 calls) | In-memory job registry, FastAPI BackgroundTasks, single process |
| Light production (10 users, on-demand) | Add a persistent job store (SQLite), thread pool executor for parallel calls |
| Heavy production (100+ concurrent uploads) | Celery + Redis for distributed processing, S3 for file storage, PostgreSQL for job tracking |

### Scaling Priorities

1. **First bottleneck:** STFT with n_fft=8192 on 44 long recordings is CPU-heavy. Run calls concurrently with `concurrent.futures.ThreadPoolExecutor(max_workers=4)` if demo time permits.
2. **Second bottleneck:** Serving WAV files — use FastAPI's `FileResponse` with proper Content-Type; cache spectrogram PNGs after first render.

## Anti-Patterns

### Anti-Pattern 1: Coupling DSP Stages with FastAPI

**What people do:** Put librosa calls directly inside route handlers.
**Why it's wrong:** Cannot test pipeline standalone, cannot run CLI batch script, import errors during testing break the entire API.
**Do this instead:** Keep pipeline/ as a pure Python package. API imports from pipeline, never the reverse.

### Anti-Pattern 2: Default n_fft=2048 or Lower

**What people do:** Use librosa defaults (n_fft=2048, giving ~22Hz resolution at 44.1kHz).
**Why it's wrong:** Elephant fundamentals are 10-20Hz. At 44.1kHz with n_fft=2048, frequency bin width is 21.5Hz — you cannot resolve the fundamental at all. You need n_fft=8192 (5.4Hz bins) minimum.
**Do this instead:** Set n_fft=8192 globally as a project constant. Document it prominently. Check frequency resolution = sr / n_fft before starting.

### Anti-Pattern 3: Applying Generic Spectral Subtraction Before HPSS

**What people do:** Run noisereduce on the raw waveform first to "clean it up" before analysis.
**Why it's wrong:** Generic spectral subtraction attenuates the infrasonic fundamental and lower harmonics, corrupting the harmonic structure that SHS depends on to detect f0. The pipeline loses exactly the information it needs.
**Do this instead:** HPSS first to isolate the harmonic component, SHS + comb mask on the harmonic component, noisereduce only as a final residual cleanup stage after the mask has already done the heavy lifting.

### Anti-Pattern 4: Discarding Phase from STFT

**What people do:** Reconstruct audio using random phase or magnitude-only Griffin-Lim.
**Why it's wrong:** Produces "musical noise" (metallic artifacts) that sounds worse than the original noise. Griffin-Lim requires many iterations and still sounds unnatural.
**Do this instead:** Preserve the original phase from librosa.stft, apply magnitude masking only, then librosa.istft with the original phase. One line: `audio_clean = librosa.istft(S_masked * phase, hop_length=hop_length)`.

### Anti-Pattern 5: WebSockets for Job Progress When Polling Works

**What people do:** Add WebSocket support for real-time progress updates.
**Why it's wrong:** Adds 2-3 hours of implementation complexity (CORS, connection management, React state) for a use case with 1 concurrent user.
**Do this instead:** Simple 2-second polling with `setInterval` in React. If progress granularity matters, update the job registry every N calls processed.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LALAL.AI (comparison baseline) | Manual: export cleaned WAVs, process through LALAL.AI web UI, download results, compare SNR in compare_lalal.py | No API access needed — comparison is offline |
| Raven Pro (output compatibility) | WAV export at original sample rate with 24-bit depth via soundfile.write | Raven Pro reads standard WAV; no special format required |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| pipeline/ ↔ api/ | Direct Python import; api calls pipeline.runner.run_pipeline() | No queuing abstraction needed at this scale |
| api/ ↔ frontend/ | REST HTTP + JSON; binary WAV files via FileResponse | CORS must be configured: allow localhost:5173 (Vite dev server) |
| HPSS ↔ SHS | Numpy array in-memory; HPSS outputs S_harmonic which SHS reads directly | No disk I/O between these stages — keep in memory |
| SHS ↔ CombMask | f0_contour: 1D array of floats (Hz), one per time frame | Time-align with STFT frames: length = ceil(n_samples / hop_length) |

## Sources

- librosa HPSS documentation: https://librosa.org/doc/main/generated/librosa.effects.hpss.html
- FastAPI BackgroundTasks: https://fastapi.tiangolo.com/tutorial/background-tasks/
- Scalable bioacoustic preprocessing: https://pmc.ncbi.nlm.nih.gov/articles/PMC6075764/
- Subharmonic summation (Hermes 1988): https://pubmed.ncbi.nlm.nih.gov/3343445/
- Bioacoustic signal denoising review: https://dl.acm.org/doi/abs/10.1007/s10462-020-09932-4
- Noise-resilient bioacoustics feature extraction: https://pmc.ncbi.nlm.nih.gov/articles/PMC12707801/

---
*Architecture research for: ElephantVoices bioacoustic denoising system*
*Researched: 2026-04-11*
