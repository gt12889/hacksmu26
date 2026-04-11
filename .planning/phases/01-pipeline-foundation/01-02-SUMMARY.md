---
phase: 01-pipeline-foundation
plan: 02
subsystem: audio-dsp
tags: [librosa, numpy, stft, istft, spectral-flatness, infrasonic, phase-preservation]

# Dependency graph
requires:
  - phase: 01-pipeline-foundation plan 01
    provides: "N_FFT=8192, HOP_LENGTH=512, FLATNESS_TONAL_THRESHOLD, FLATNESS_BROADBAND_THRESHOLD, verify_resolution()"

provides:
  - "compute_stft(y, sr) — STFT with phase separation, returns 7-key dict (S, magnitude, phase, freq_bins, sr, n_fft, hop_length)"
  - "reconstruct_audio(magnitude, phase) — artifact-free ISTFT using original phase"
  - "classify_noise_type(y_noise, sr) — spectral flatness classifier returning generator/car/plane/mixed"

affects:
  - Phase 02 (comb masking): uses compute_stft + reconstruct_audio for mask application/ISTFT round-trip
  - Phase 02 (denoising strategy): uses classify_noise_type to select stationary vs non-stationary noisereduce

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase-preserved STFT: separate magnitude and phase immediately, reconstruct via magnitude * exp(1j * phase)"
    - "Noise guard pattern: empty/silent guard at function entry, warn + return fallback, never crash"
    - "TDD RED→GREEN: write failing import test first, then implement module"

key-files:
  created:
    - pipeline/spectrogram.py
    - pipeline/noise_classifier.py
    - tests/test_spectrogram.py
    - tests/test_noise_classifier.py
  modified: []

key-decisions:
  - "Phase-preserved ISTFT via np.exp(1j * phase): original phase from compute_stft() used in reconstruct_audio() — eliminates phase artifacts without estimation"
  - "Noise classifier thresholds from config: FLATNESS_TONAL_THRESHOLD=0.1 and FLATNESS_BROADBAND_THRESHOLD=0.4 imported from pipeline.config, not hardcoded"
  - "Generator detected via dual condition: low spectral flatness AND concentrated 25-100 Hz energy (low_freq_ratio > 0.3)"
  - "Car vs plane separated by temporal variance of column-wise mean power (threshold 0.05)"

patterns-established:
  - "Pattern: compute_stft → apply comb mask to magnitude → reconstruct_audio (Phase 2 data flow)"
  - "Pattern: classify_noise_type returns type that selects stationary vs non-stationary noisereduce mode"
  - "Pattern: use warnings.warn(RuntimeWarning) for graceful degradation on bad inputs"

requirements-completed: [SPEC-01, SPEC-02, SPEC-03]

# Metrics
duration: 3min
completed: 2026-04-11
---

# Phase 01 Plan 02: Spectrogram and Noise Classifier Summary

**STFT with phase-preserved round-trip (N_FFT=8192, round-trip error 3.6e-07) and spectral flatness classifier correctly identifying 60 Hz tonal noise as generator and white noise as broadband**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-11T23:32:54Z
- **Completed:** 2026-04-11T23:35:57Z
- **Tasks:** 2
- **Files modified:** 4 (2 implementation, 2 test)

## Accomplishments

- `compute_stft()` computes STFT at n_fft=8192 (5.38 Hz/bin at 44100 Hz), separates magnitude and phase, returns 7-key dict with all metadata — no hardcoded values, all from `pipeline.config`
- `reconstruct_audio()` reconstructs audio from masked magnitude + original phase via `magnitude * np.exp(1j * phase)`, achieving a round-trip error of 3.6e-07 on a 20 Hz sine (well under 1e-3 threshold)
- `classify_noise_type()` correctly classifies tonal 60 Hz sine as "generator" (flatness=0.000, low_freq_ratio=287), white noise as "car" (broadband), and empty/silent arrays as "mixed" with RuntimeWarning

## Task Commits

Each task was committed atomically using TDD RED→GREEN:

1. **Task 1 RED: failing tests for spectrogram** - `2dc6343` (test)
2. **Task 1 GREEN: implement compute_stft + reconstruct_audio** - `3f18e96` (feat)
3. **Task 2 RED: failing tests for noise classifier** - `d71049a` (test)
4. **Task 2 GREEN: implement classify_noise_type** - `dbf4509` (feat)

**Plan metadata:** _(docs commit follows)_

_Note: TDD tasks have separate RED (test) and GREEN (implementation) commits._

## Files Created/Modified

- `pipeline/spectrogram.py` — compute_stft() and reconstruct_audio() using N_FFT/HOP_LENGTH from config
- `pipeline/noise_classifier.py` — classify_noise_type() with spectral flatness + low_freq_ratio decision tree
- `tests/test_spectrogram.py` — 7 tests: dict keys, N_FFT constants, freq_bins length, shape match, ISTFT tolerance, round-trip error, verify_resolution called
- `tests/test_noise_classifier.py` — 8 tests: return dict keys, generator detection, white noise classification, empty/silent fallback with RuntimeWarning, flatness range, ratio non-negative

## Decisions Made

- Phase-preserved ISTFT via `np.exp(1j * phase)` eliminates phase estimation artifacts — original phase preserved from compute_stft() to reconstruct_audio()
- Noise classifier uses dual condition for "generator": low spectral flatness (< 0.1) AND concentrated 25-100 Hz energy (low_freq_ratio > 0.3) — both conditions prevent false positives
- Car vs plane distinguished by temporal variance of column-wise mean power: car (transient, high variance > 0.05) vs plane (steady drone, low variance)
- All thresholds imported from pipeline.config — no hardcoded values in either module

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The `librosa.stft` + `np.exp(1j * phase)` approach for phase-preserved reconstruction achieved a round-trip error of 3.6e-07 on a 20 Hz sine at 44100 Hz — far below the 1e-3 tolerance specified.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 2 can import:
- `from pipeline.spectrogram import compute_stft, reconstruct_audio` — STFT with phase separation + artifact-free ISTFT
- `from pipeline.noise_classifier import classify_noise_type` — selects stationary vs non-stationary noisereduce strategy

Phase 2 data flow: `compute_stft(y, sr)` → apply harmonic comb mask to `result["magnitude"]` → `reconstruct_audio(masked_magnitude, result["phase"])`

All 31 tests pass (config: 7, ingestor: 9, spectrogram: 7, noise_classifier: 8).

---
*Phase: 01-pipeline-foundation*
*Completed: 2026-04-11*
