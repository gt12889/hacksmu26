---
phase: 03-demo-spectrograms-measurements
plan: 01
subsystem: visualization
tags: [matplotlib, spectrogram, harmonic, snr, wav-export, synthetic-audio, pytest]

requires:
  - phase: 02-harmonic-detection-denoising
    provides: process_call() returning ctx dict with magnitude, comb_mask, f0_contour, audio_clean

provides:
  - scripts/demo_spectrograms.py — one-command demo producing 3 PNG + 3 WAV per noise type
  - tests/test_demo_spectrograms.py — 6 pytest tests with no real recordings required
  - data/outputs/demo/ — {generator,car,plane}_demo.png + {generator,car,plane}_clean.wav

affects:
  - phase 04 (web demo) — figures are the pitch artifact; WAVs used for A/B toggle
  - judge pitch — spectrograms are primary evidence shown to judges

tech-stack:
  added: []
  patterns:
    - "3-panel matplotlib figure: constrained_layout=True, no tight_layout()"
    - "Frequency slicing to DISPLAY_FREQ_MAX_HZ=500 before imshow (never plot 0-22kHz)"
    - "RGBA cyan overlay for comb mask: overlay[...,3] = comb_mask * 0.6"
    - "SNR measured on linear magnitude**2 (never dB-scale)"
    - "WAV normalization before sf.write: audio / (abs(audio).max() + 1e-10)"
    - "Synthetic call fixture: f0=14Hz harmonics up to 500Hz + white noise at 0dB SNR"

key-files:
  created:
    - scripts/demo_spectrograms.py
    - tests/test_demo_spectrograms.py
    - .gitignore
  modified: []

key-decisions:
  - "DISPLAY_FREQ_MAX_HZ=500: slices 4097-bin STFT to 93 display bins — all elephant content visible"
  - "constrained_layout=True on figure creation (not tight_layout) — avoids matplotlib 3.10 colorbar warning"
  - "SNR computed on linear power not dB-scale magnitude — standard acoustic measurement convention"
  - "build_synthetic_call uses f0=14Hz fundamental to match real elephant rumble range (8-25 Hz)"
  - "Re-STFT on ctx[audio_clean] for clean panel magnitude — not using masked_magnitude directly"

patterns-established:
  - "Pattern: frequency-sliced imshow with extent=[t0,t1,f_low,f_high] — f0 contour overlaid in same Hz data coordinates"
  - "Pattern: compute_snr_db returns float(-999.0) sentinel when no harmonic bins found — never raises"

requirements-completed: [DEMO-01, DEMO-02, DEMO-03, DEMO-04, DEMO-05, DEMO-06, DEMO-07]

duration: 4min
completed: 2026-04-12
---

# Phase 3 Plan 01: Demo Spectrograms Summary

**3-panel before/after spectrogram figures (300 dpi) with comb mask overlay, f0 contour, harmonic markers, and SNR annotation — plus cleaned PCM_16 WAV exports — produced from synthetic audio in one command**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-12T02:06:44Z
- **Completed:** 2026-04-12T02:10:41Z
- **Tasks:** 2 (Task 1: demo script, Task 2: test suite)
- **Files modified:** 3 created

## Accomplishments

- `scripts/demo_spectrograms.py` implemented with `--synthetic` mode producing 6 files in one command
- 3-panel figures (Original | Comb Mask Overlay | Cleaned) at 300 dpi, ~5 MB each
- SNR improvement of ~6 dB shown in annotation box (15.6 dB before, 21+ dB after)
- All 6 pytest tests pass without real recordings, covering DEMO-01 through DEMO-07
- Clean run with no matplotlib warnings (constrained_layout avoids tight_layout conflict)

## Task Commits

1. **Task 1 (TDD RED): failing tests** - `d69becf` (test)
2. **Task 1 (TDD GREEN): demo script implementation** - `93736ae` (feat)
3. **Deviation: .gitignore** - `7d829cb` (chore)

## Files Created/Modified

- `scripts/demo_spectrograms.py` — Main demo script: `build_synthetic_call`, `compute_snr_db`, `make_demo_figure`, `select_calls_from_annotations`, `main`
- `tests/test_demo_spectrograms.py` — 6-test pytest suite with synthetic numpy fixtures; no real recordings required
- `.gitignore` — Excludes generated outputs (`data/outputs/`) and pycache

## Decisions Made

- **DISPLAY_FREQ_MAX_HZ=500**: Full STFT has 4097 bins (0-22 kHz); slicing to 93 bins makes elephant content visible instead of compressed into bottom 0.5% of figure
- **constrained_layout=True**: matplotlib 3.10 raises `UserWarning: tight_layout not applied` when colorbars present — constrained_layout handles this correctly per RESEARCH.md
- **SNR on linear power**: Computed as `10*log10(harmonic_band_power / noise_power)` on `magnitude**2`, not on dB-converted values
- **Re-STFT for clean panel**: `compute_stft(ctx["audio_clean"], sr)` called separately for clean magnitude — this is the correct approach since `masked_magnitude` is pre-noisereduce and `ctx_clean["magnitude"]` is post-noisereduce clean spectrum
- **build_synthetic_call f0=14 Hz**: Center of elephant rumble range (8-25 Hz); harmonic series at 14, 28, 42, ... Hz up to 500 Hz provides realistic test fixture

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added .gitignore**
- **Found during:** Task 1 post-commit check
- **Issue:** `data/outputs/` (generated PNG/WAV files) and `__pycache__/` were untracked — would pollute commits on future runs
- **Fix:** Created `.gitignore` excluding `data/outputs/`, `__pycache__/`, `.venv/`
- **Files modified:** `.gitignore` (created)
- **Verification:** `git status` shows no untracked runtime output
- **Committed in:** `7d829cb`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** .gitignore is essential repo hygiene. No scope creep.

## Issues Encountered

None — plan executed cleanly with all patterns from RESEARCH.md working as documented.

## Known Stubs

None — all output is wired to real pipeline (`process_call` + `compute_stft`). Synthetic audio generates real spectrograms, not placeholder images.

## Next Phase Readiness

- Phase 4 (web demo / batch processing) has clean artifacts to reference
- 3 PNG figures ready for judge pitch at `data/outputs/demo/`
- 3 WAV files ready for A/B audio playback
- `make_demo_figure()` is importable by future scripts that need figure rendering
- `compute_snr_db()` available for batch confidence scoring in Phase 4+

---
*Phase: 03-demo-spectrograms-measurements*
*Completed: 2026-04-12*
