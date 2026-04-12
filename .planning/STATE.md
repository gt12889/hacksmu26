---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Completed 06-multi-speaker-separation 06-02-PLAN.md
last_updated: "2026-04-12T04:56:44.231Z"
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 16
  completed_plans: 16
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-11)

**Core value:** Denoise elephant vocalizations by exploiting their harmonic integer-multiple structure — surgical extraction where generic AI tools fail on infrasonic content
**Current focus:** Phase 06 — Multi-Speaker Separation

## Current Position

Phase: 06 (Multi-Speaker Separation) — EXECUTING
Plan: 2 of 2

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*
| Phase 01-pipeline-foundation P01 | 4 | 3 tasks | 10 files |
| Phase 01-pipeline-foundation P02 | 3 | 2 tasks | 4 files |
| Phase 01-pipeline-foundation P03 | 2 | 2 tasks | 3 files |
| Phase 02-harmonic-detection-denoising P01 | 4 minutes | 2 tasks | 3 files |
| Phase 02-harmonic-detection-denoising P02 | 2 | 2 tasks | 2 files |
| Phase 03-demo-spectrograms-measurements P01 | 4 | 2 tasks | 3 files |
| Phase 04-batch-processing-api P01 | 2 | 2 tasks | 3 files |
| Phase 04-batch-processing-api P02 | 4 minutes | 1 tasks | 2 files |
| Phase 04-batch-processing-api P03 | 2 | 1 tasks | 1 files |
| Phase 04-batch-processing-api P04 | 5 minutes | 2 tasks | 12 files |
| Phase 05-react-frontend-demo P02 | 2 | 2 tasks | 13 files |
| Phase 05 P01 | 15 | 3 tasks | 3 files |
| Phase 05-react-frontend-demo P03 | 2 | 3 tasks | 3 files |
| Phase 05-react-frontend-demo P04 | 85 | 2 tasks | 6 files |
| Phase 06-multi-speaker-separation P01 | 52 | 2 tasks | 3 files |
| Phase 06-multi-speaker-separation P02 | 25 | 1 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Init: Harmonic comb masking over generic ML — exploits domain structure, no training needed
- Init: n_fft=8192 mandatory — need ~5Hz frequency resolution for infrasonic fundamentals
- Init: SHS f0 detection — 2nd harmonic stronger than fundamental; octave-check heuristic required
- Init: LALAL.AI as comparison foil, not primary tool — trained on speech/music, fails on infrasonic
- Init: BackgroundTasks for FastAPI from day one — synchronous processing blocks React
- [Phase 01-pipeline-foundation]: verify_resolution() accepts optional n_fft parameter to allow per-file override for 96kHz recordings needing n_fft=16384
- [Phase 01-pipeline-foundation]: extract_noise_gaps() handles empty calls list explicitly — returns full recording as noise gap
- [Phase 01-pipeline-foundation]: Phase-preserved ISTFT via np.exp(1j * phase) eliminates phase artifacts in spectrogram reconstruction
- [Phase 01-pipeline-foundation]: Generator detected via dual condition: flatness < 0.1 AND 25-100 Hz low_freq_ratio > 0.3 (prevents false positives)
- [Phase 01-pipeline-foundation]: Car vs plane separated by temporal variance of column-wise mean power (threshold 0.05)
- [Phase 01-pipeline-foundation]: All tests use synthetic numpy fixtures — no real recordings required, making CI portable
- [Phase 01-pipeline-foundation]: CLI scripts use sys.path.insert(0, repo_root) to import pipeline.* without installing as package
- [Phase 02-harmonic-detection-denoising]: apply_noisereduce generator+no-clip fallback: RuntimeWarning + non-stationary (not ValueError raise)
- [Phase 02-harmonic-detection-denoising]: detect_f0_shs uses vectorized NSSH loop (not per-frame Python loop) for <1s/call performance
- [Phase 02-harmonic-detection-denoising]: test_harmonic_processor.py delivered in Plan 01 TDD RED phase; Plan 02 verified 30/30 pass
- [Phase 02-harmonic-detection-denoising]: CLI process_call.py: --noise-type override for testing; auto-detects via classify_noise_type() when omitted
- [Phase 03-demo-spectrograms-measurements]: DISPLAY_FREQ_MAX_HZ=500: slices 4097-bin STFT to 93 display bins so all elephant harmonic content is visible (not compressed into bottom 0.5% of figure)
- [Phase 03-demo-spectrograms-measurements]: constrained_layout=True on figure creation (never tight_layout) — avoids matplotlib 3.10 colorbar layout warnings
- [Phase 03-demo-spectrograms-measurements]: SNR computed on linear magnitude**2 power (not dB-scale) — standard acoustic measurement convention
- [Phase 04-batch-processing-api]: compute_snr_db lifted verbatim from scripts/demo_spectrograms.py — unifies demo and batch scoring implementations
- [Phase 04-batch-processing-api]: compute_confidence takes f0_contour array directly (not ctx dict) — decouples from caller structure
- [Phase 04-batch-processing-api]: Result dict uses f0_median_hz, snr_before_db, snr_after_db — prevents write_summary_csv KeyError
- [Phase 04-batch-processing-api]: SNR-after via re-STFT on audio_clean (not masked_magnitude) — matches demo_spectrograms.py pattern
- [Phase 04-batch-processing-api]: WAV export normalizes before sf.write to prevent PCM_16 clipping from noisereduce output
- [Phase 04-batch-processing-api]: Raven TSV floats formatted as f'{value:.6f}' — locale-safe, no comma-decimal ambiguity
- [Phase 04-batch-processing-api]: Synthetic WAVs include 5-second noise tail so extract_noise_gaps() finds real noise profile (prevents zero-size array crash in noisereduce)
- [Phase 04-batch-processing-api]: UPLOAD_REGISTRY singleton in api/uploads.py — routes import shared ref, never re-instantiate
- [Phase 04-batch-processing-api]: Spectrogram endpoint 404 by design — batch_runner produces no PNG in Phase 4
- [Phase 04-batch-processing-api]: _run_job builds 1-row DataFrame from soundfile.info().duration; recordings_dir=Path(upload_path).parent
- [Phase 05-react-frontend-demo]: React 18.3.1 (not 19.x) locked for wavesurfer.js 7.x compatibility
- [Phase 05-react-frontend-demo]: tsconfig project references split (app + node) required for tsc -b build script
- [Phase 05-react-frontend-demo]: Vite proxy target localhost:8000 — FastAPI runs on port 8000
- [Phase 05]: Returns 200+empty list (not 404) when data/outputs/ absent — empty is valid state for fresh checkout
- [Phase 05]: clean_wav_path rewritten to absolute in batch_results — React passes verbatim to /api/batch/audio
- [Phase 05]: _ALLOWED_ROOTS resolved at import time via __file__.parents[2] — deterministic path-traversal allowlist for batch audio
- [Phase 05-react-frontend-demo]: WavesurferPlayer is default export from @wavesurfer/react (not named export)
- [Phase 05-react-frontend-demo]: ABPlayer captures getCurrentTime() before URL state change, calls setTime() in onReady — prevents A/B timestamp loss
- [Phase 05-react-frontend-demo]: noisyUrl null for batch-disk rows by design — disables ABPlayer, keeps SpectrogramView via cleanUrl
- [Phase 05-react-frontend-demo]: batchAudioUrl(clean_wav_path) for batch-disk cleanUrl — SpectrogramView renders on all 212 batch rows on page load
- [Phase 06-multi-speaker-separation]: Use raw magnitude for SHS in multi-speaker mode: HPSS suppresses weaker of two simultaneous harmonic sources
- [Phase 06-multi-speaker-separation]: F0_JUMP_TOLERANCE_HZ=5.0 (not 4.0): needed for track recovery when 14 Hz candidate absent from top-2
- [Phase 06-multi-speaker-separation]: Fixed 0.5 Hz SHS step in detect_f0_shs_topk: coarse hz_per_bin/2 step cannot resolve sources 4 Hz apart
- [Phase 06-multi-speaker-separation]: Bypass is_multi_speaker gate for synthetic demo — gate unreliable on pure harmonic synthetics; always proceeds with separation and prints gate result informatively
- [Phase 06-multi-speaker-separation]: TRACK_COLORS red/blue (#FF4444/#4488FF) for maximum contrast against magma spectrogram at 300 dpi

### Pending Todos

None yet.

### Blockers/Concerns

- Annotation CSV exact column names/timestamp format unknown — first task of Phase 1
- Actual sample rates of 44 recordings unverified (assumed 44100Hz, could be 48/96kHz)
- LALAL.AI upload limits/processing time for UI-03 comparison — must verify before Phase 4

## Session Continuity

Last session: 2026-04-12T04:56:44.228Z
Stopped at: Completed 06-multi-speaker-separation 06-02-PLAN.md
Resume file: None
