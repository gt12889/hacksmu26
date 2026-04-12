# Milestones

## v1.0 ElephantVoices Denoiser v1.0 (Shipped: 2026-04-12)

**Phases completed:** 9 phases, 19 plans, 22 tasks

**Key accomplishments:**

- One-liner:
- STFT with phase-preserved round-trip (N_FFT=8192, round-trip error 3.6e-07) and spectral flatness classifier correctly identifying 60 Hz tonal noise as generator and white noise as broadband
- 25-test pytest suite covering all 8 Phase 1 requirements plus batch ingest CLI with dry-run mode using argparse + tqdm
- 30-test pytest suite covering all 6 harmonic_processor functions plus a CLI script (scripts/process_call.py) that runs the full Phase 2 pipeline on real field recordings with f0 statistics output
- 3-panel before/after spectrogram figures (300 dpi) with comb mask overlay, f0 contour, harmonic markers, and SNR annotation — plus cleaned PCM_16 WAV exports — produced from synthetic audio in one command
- 1. [Rule 1 - Bug] Test for -999.0 sentinel used incorrect f0_median
- `scripts/batch_process.py` CLI entrypoint wraps `run_batch` with argparse, producing batch_summary.csv, raven_selection.txt, and cleaned WAVs from either real recordings or synthetic test audio
- 1. [Rule 1 - Bug] Fixed datetime.utcnow() deprecation
- Three read-only FastAPI endpoints added — batch disk results browsing, upload audio streaming, and path-guarded batch WAV serving — unblocking the React demo's A/B playback and pre-processed call browser
- Vite + React 18 + TypeScript project scaffolded with typed axios client, Pydantic-mirrored TypeScript interfaces, and 2s polling hook — full API surface defined before any UI components
- 1. [Rule 1 - Bug] WavesurferPlayer is default export, not named export
- Full React demo with sortable/filterable 212-call browser, upload flow, spectrogram + comb overlay, A/B toggle, and 3-column SNR comparison — builds clean under strict TypeScript, pending human verification of the end-to-end flow
- Top-2 SHS track linker with modal seeding separates 14+18 Hz synthetic elephant call mixture into two per-caller WAV files using existing comb mask pipeline
- Judge-facing demo script (demo_multi_speaker.py) mixes 14+18 Hz synthetic callers, separates them via SHS track-linking + comb masking, and produces a 300 dpi magma spectrogram with two colored f0 overlays plus two per-caller WAV files
- One-liner:
- One-liner:
- Spectrogram PNGs now generated per call in run_batch via make_demo_figure, and link_f0_tracks drops tracks with fewer than MIN_TRACK_FRAMES valid frames after median smoothing

---
