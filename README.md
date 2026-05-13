# ElephantVoices Denoiser — HackSMU 2026

Hackathon project for **HackSMU** at SMU: a **bioacoustic denoising pipeline** for elephant field recordings contaminated by mechanical noise (generators, cars, aircraft). Generic speech/music denoisers fail on infrasonic rumbles (roughly 10–20 Hz fundamentals with harmonics into the kHz range) that overlap engine noise. This repo uses **harmonic structure** (STFT, HPSS-style separation, comb masking, scoring) plus optional **multi-speaker** separation, exposed through a **FastAPI** service and a **React + Vite** demo UI.

## Pipeline logic

Constants live in `pipeline/config.py` (e.g. `N_FFT=8192`, `HOP_LENGTH=512`, padding and flatness thresholds). The processing chain is designed so **HPSS informs f0 detection**, but **reconstruction uses the original magnitude × comb mask + original phase**, and **noisereduce runs last** on the comb-masked waveform.

### 1. Ingestion (`pipeline/ingestor.py`)

- Parse annotation **CSV/XLSX** with normalized columns `filename`, `start`, `end` (and optional metadata).
- **Load call segments** with librosa at **native sample rate** (`sr=None`) and configurable padding (`PAD_SECONDS`).
- **Extract noise-only gaps** between calls (minimum gap duration from config) for profiling **generator** hum.
- **Frequency resolution check** (`verify_resolution`): ensures STFT bin width meets the infrasonic requirement before spectrograms are built.

### 2. Spectrogram (`pipeline/spectrogram.py`)

- **STFT** with large `n_fft` (8192) for fine low-frequency bins (~5 Hz/bin at 44.1 kHz) so fundamentals near 8–25 Hz are resolvable.
- Store **complex STFT**, then **magnitude** and **phase** separately. Phase is reused in ISTFT so masking does not require phase estimation.

### 3. Noise classification (`pipeline/noise_classifier.py`)

From a **noise-only** segment:

- **Spectral flatness** (tonal vs broadband) and **low-band energy ratio** (25–100 Hz) to detect **generator** harmonic hum.
- **Broadband** noise: split **car** vs **plane** using **temporal variance** of frame power (transient vs steady sweep/drone).
- Otherwise **mixed**. This selects **noisereduce** mode later: **stationary** (with noise clip) for generator, **non-stationary** for car/plane/mixed.

### 4. Harmonic processing (`pipeline/harmonic_processor.py`) — per-call chain

Order is fixed:

1. **`compute_stft`** — build magnitude, phase, `freq_bins`.
2. **`hpss_enhance`** — librosa **HPSS** on the **magnitude** with kernels tuned for infrasonic horizontal structure; produces `magnitude_harmonic` for f0 estimation only (not for final reconstruction magnitude).
3. **`detect_f0_shs`** — **subharmonic summation (NSSH)**: sweep f0 candidates ~8–25 Hz; per frame, score each candidate by mean normalized power at harmonics up to ~1000 Hz; pick best; **octave correction** if energy at f0/2 rivals f0; **median filter** the f0 contour over time.
4. **`build_comb_mask`** — time-varying **soft triangular** mask at integer multiples of f0 (soft edges reduce musical-noise artifacts vs hard binary masks). Mask is built using **original** magnitude shape; reference magnitude for geometry is the full STFT magnitude.
5. **`apply_comb_mask`** — multiply **original** magnitude by comb mask; **ISTFT** with **original phase** → `audio_comb_masked`.
6. **`apply_noisereduce`** — **noisereduce** on `audio_comb_masked`: stationary + noise clip for generator when available; else non-stationary. Output: **`audio_clean`**.

Important design rules encoded in code:

- **SHS runs on `magnitude_harmonic`** to reduce engine-bias in f0 votes.
- **Comb mask applies to original magnitude** so amplitude relationships and harmonics are preserved correctly.
- **noisereduce after** comb masking, not before HPSS.

### 5. Scoring (`pipeline/scoring.py`)

- **SNR (dB)**: ratio of power in **harmonic bands** (around k·f0) vs **out-of-band** power on the spectrogram.
- **Confidence 0–100**: combines **SNR improvement** (before vs after), **harmonic integrity** (fraction of harmonic bins covered by the mask), and **f0 stability** (spread of the f0 contour).

### 6. Batch processing (`pipeline/batch_runner.py`)

- Iterate annotation rows: load call + noise clip → classify noise → **`process_call`** → recompute STFT on cleaned audio for “after” SNR → confidence → export normalized WAV and optional CSV/Raven-friendly summaries.

### 7. Multi-speaker (`pipeline/multi_speaker.py`) — optional Phase 6

- **Top-k SHS** per frame to get multiple f0 candidates; **greedy track linking** across time with jump tolerance; optional **two-caller** gate via score ratio (`MIN_SCORE_RATIO`, etc. in `config.py`).
- Per-track **comb mask + separation** into caller WAVs when overlapping elephants are detected.



### More techincal details on the approach:



The denoiser exploits a property unique to elephant rumbles: their energy lives on integer multiples of a fundamental frequency f₀ between roughly 8–25 Hz, while mechanical noise (generators, cars, planes) has its own unrelated harmonic series or broadband shape — so per-frame, we run subharmonic summation (SHS) on the HPSS-enhanced magnitude to find the f₀ that best explains the rumble's harmonic stack (with an octave-correction step to prevent locking onto f₀/2, then a median filter over time so the f₀ contour doesn't jitter into engine territory). Once we have a time-varying f₀, we build a soft triangular comb mask at integer multiples k·f₀ (soft edges instead of hard binary gates, which kills the "musical noise" artifact common in spectral subtraction), multiply it against the original magnitude spectrogram (not the HPSS-enhanced one — HPSS is used only as a voting aid for f₀), and reconstruct audio via ISTFT using the original phase, which keeps the rumble's transient structure intact. Finally, the residual noise that fell inside the comb's pass-bands is removed by noisereduce, which we run last with a key twist: the noise classifier upstream (noise_classifier.py) inspects spectral flatness and 25–100 Hz energy ratio in the silence between calls to pick the right mode automatically stationary with an explicit noise profile when a generator is detected, non-stationary for car/plane/mixed where the noise floor sweeps over time — so the same pipeline adapts per recording without manual tuning.





### 8. API and demo

- **`api/main.py`**: FastAPI app **ElephantVoices Denoiser API** — routers for upload, process, status, result, batch, demo; static demo assets under `/static/demo`.
- **`frontend/`**: Vite + React UI for uploads, job polling, spectrogram / A–B playback, and comparison panels (see `App.tsx` and components).

---

## Repository layout

| Path | Purpose |
|------|---------|
| `pipeline/` | DSP: ingest, spectrograms, noise classification, harmonic processing, scoring, batch runner, multi-speaker |
| `api/` | FastAPI app: upload, process, job status, results, batch, demo assets |
| `frontend/` | Vite + TypeScript + React demo (spectrogram views, A/B audio, confidence UI, upload flow) |
| `scripts/` | CLI helpers (`batch_process.py`, `demo_multi_speaker.py`, `ingest.py`, `process_call.py`, `start_demo.sh`) |
| `tests/` | `pytest` coverage for pipeline, API, scoring, batch runner |
| `tasks/` | PRD and product notes (`prd-elephant-denoiser.md`) |
| `.planning/` | Internal roadmap and phase notes (optional reading) |

## Prerequisites

- **Python 3.10+** (recommended)
- **Node.js 18+** and npm (for the frontend)

## Backend setup

From the repo root:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-backend.txt
```

Run the API on **port 8001** so it matches the Vite dev server proxies for `/api` and `/static` (see `frontend/vite.config.ts`):

```bash
uvicorn api.main:app --reload --port 8001
```

- Root health check: `GET http://localhost:8001/` → `{"status":"ok","service":"ElephantVoices Denoiser API"}`
- Routers include upload, process, status, result, batch, and demo; demo static files are served under `/static/demo` when present.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Vite serves the app at **http://localhost:5173**. API calls use relative `/api/...` paths and are proxied to the backend (see `frontend/vite.config.ts`).

## One-command demo (Linux/macOS)

```bash
bash scripts/start_demo.sh
```

Installs Python deps if needed, starts `uvicorn` on port **8001**, then runs `npm run dev` in `frontend/` when `node_modules` exists (matches `vite.config.ts` proxies for `/api` and `/static`).

## Running tests

```bash
pytest
```

## Tech stack (high level)

- **Audio / DSP:** librosa, scipy, numpy, soundfile, noisereduce, matplotlib, pandas  
- **API:** FastAPI, uvicorn, python-multipart  
- **UI:** React 18, Vite 5, TypeScript, axios  



