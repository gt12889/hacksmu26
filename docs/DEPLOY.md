# Deployment Guide — ElephantVoices Denoiser

Step-by-step guide to run the full stack locally for the HackSMU 2026 demo.

**Time to first demo:** ~5 minutes on a clean machine.

## Prerequisites

- **Python** 3.10 or later
- **Node.js** 18 or later (with npm)
- **Git**
- ~500 MB disk space (mostly node_modules and Python packages)
- No GPU required. No cloud services. Local-only.

## One-Command Launcher

```bash
git clone git@github.com:gt12889/hacksmu26.git
cd hacksmu26

# Python backend
python -m venv .venv
source .venv/bin/activate   # or: .venv\Scripts\activate on Windows
pip install -r requirements-backend.txt

# Frontend
cd frontend && npm install && cd ..

# Launch both
bash scripts/start_demo.sh
```

Open **http://localhost:5173** in your browser.

## What You'll See

The demo has three sections:

1. **Top — Static 3-noise-type demo cards.** Generator, vehicle, airplane. Each card shows a publication-quality before/after spectrogram with f0 contour and harmonic markers, plus A/B audio toggle. These are pre-generated and always visible.

2. **Middle — Upload & Process.** Upload any WAV file. It runs through the full pipeline (HPSS → SHS → comb mask → noisereduce) and shows the result in a CallDetail panel with interactive spectrogram viewer (wavesurfer.js) and A/B playback.

3. **Bottom — Confidence Dashboard.** Sortable/filterable table of all batch-processed calls from `data/outputs/`. Click any row to view its spectrogram and audio inline.

## Manual Launch (Two Terminals)

If the launcher script doesn't work on your OS:

**Terminal 1 — Backend:**
```bash
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```
Backend available at http://localhost:8000 · API docs at http://localhost:8000/docs

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```
Frontend available at http://localhost:5173

## CLI Usage (No Web Server)

If you just want to run the pipeline on files directly:

```bash
# Activate venv first
source .venv/bin/activate

# Process a single call
python scripts/process_call.py --input data/recordings/real/090224-09_generator_01.wav

# Batch process all 212 calls from the annotations spreadsheet
python scripts/batch_process.py --annotations data/annotations.xlsx --output-dir data/outputs/batch

# Generate synthetic demo figures (no real audio needed)
python scripts/demo_spectrograms.py --synthetic --output-dir data/outputs/demo

# Generate real demo figures (requires data/annotations.xlsx + data/recordings/real/)
python scripts/demo_real.py

# Multi-speaker separation on synthetic 14+18 Hz mixture
python scripts/demo_multi_speaker.py
```

## Running Tests

```bash
source .venv/bin/activate
python -m pytest -q
```

All 174 tests should pass in under 30 seconds.

## Troubleshooting

### "Port 8000 already in use"

Another process is using it. Kill it or pick another port:

```bash
uvicorn api.main:app --reload --port 8001
```

Then update `frontend/vite.config.ts` to match (`target: 'http://localhost:8001'` for both `/api` and `/static`).

### "Module not found: librosa / noisereduce"

You didn't activate the venv or didn't install requirements:

```bash
source .venv/bin/activate
pip install -r requirements-backend.txt
```

### "npm run dev fails"

Missing dependencies:

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Frontend loads but shows "Generating demo..."

The frontend expects pre-generated demo PNGs/WAVs at `data/outputs/demo/`. Generate them:

```bash
source .venv/bin/activate
python scripts/demo_spectrograms.py --synthetic --output-dir data/outputs/demo
```

Then refresh the browser, or click the "Regenerate" link in the footer.

### Backend starts but the frontend can't reach it

Check the Vite proxy targets:

```bash
cat frontend/vite.config.ts
```

Both `/api` and `/static` should point to the port where `uvicorn` is running (default 8000).

## Data Layout

```
data/
├── annotations.xlsx            # 212 rumble timestamps (provided by ElephantVoices)
├── recordings/
│   └── real -> ...              # Symlink or copy of 44 real WAV recordings
├── outputs/
│   ├── demo/                    # Static demo figures (pre-generated)
│   │   ├── {generator,car,plane}_demo.png
│   │   ├── {generator,car,plane}_clean.wav
│   │   └── {generator,car,plane}_original.wav
│   ├── real_demo/               # Real-data demo figures (from demo_real.py)
│   └── batch/                   # Batch processing output (from batch_process.py)
│       ├── cleaned/*.wav
│       ├── summary.csv
│       ├── raven_selection.txt
│       └── spectrograms/*.png
└── uploads/                     # Temporary upload storage (API)
```

## Architecture (Brief)

```
React frontend (5173) ←─ Vite proxy ─→ FastAPI (8000)
                                         ↓
                                     Pipeline
                                     ├─ ingestor
                                     ├─ spectrogram (n_fft=8192)
                                     ├─ harmonic_processor
                                     │   ├─ hpss_enhance
                                     │   ├─ detect_f0_shs
                                     │   ├─ build_comb_mask
                                     │   ├─ apply_comb_mask
                                     │   └─ apply_noisereduce
                                     ├─ scoring
                                     ├─ batch_runner
                                     └─ multi_speaker
```

See `README.md` for the full architecture map and pitch narrative.

## For Judges

Run:

```bash
bash scripts/start_demo.sh
```

Open http://localhost:5173. Scroll through the 3 static demo cards. Then upload any WAV (or use the confidence dashboard below to browse pre-processed calls). Toggle A/B audio to hear the denoising work.

**Pitch script:** See `docs/TALKING-POINTS.md` and `docs/SLIDES.md`.

---

*v1.1 Phase 12 — Deployment Guide*
