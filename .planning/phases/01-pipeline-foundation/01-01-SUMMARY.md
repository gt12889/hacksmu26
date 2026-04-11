---
phase: 01-pipeline-foundation
plan: 01
subsystem: pipeline-foundation
tags: [config, ingestor, dsp, audio, tdd]
dependency_graph:
  requires: []
  provides: [pipeline.config, pipeline.ingestor]
  affects: [pipeline.spectrogram, pipeline.noise_classifier, all downstream pipeline modules]
tech_stack:
  added: [librosa==0.11.0, scipy>=1.13, numpy>=1.26, soundfile>=0.12, pandas>=2.0, openpyxl>=3.1, tqdm>=4.66, matplotlib>=3.8, pytest>=8.0]
  patterns: [config-single-source-of-truth, defensive-annotation-parser, tdd-red-green]
key_files:
  created:
    - pipeline/__init__.py
    - pipeline/config.py
    - pipeline/ingestor.py
    - requirements.txt
    - data/.gitkeep
    - data/recordings/.gitkeep
    - data/segments/.gitkeep
    - data/noise_segments/.gitkeep
    - tests/test_config.py
    - tests/test_ingestor.py
  modified: []
decisions:
  - "verify_resolution() accepts n_fft parameter to allow per-file override (96kHz recordings need n_fft=16384)"
  - "extract_noise_gaps() handles empty calls list by treating entire recording as noise"
  - "MIN_NOISE_DURATION_SEC imported from config into ingestor (not hardcoded)"
metrics:
  duration_minutes: 4
  completed_date: "2026-04-11"
  tasks_completed: 3
  files_created: 10
requirements_covered: [INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05]
---

# Phase 01 Plan 01: Config Module and Ingestor Summary

**One-liner:** DSP constant config with sr/n_fft resolution assertion plus defensive annotation CSV parser and noise gap extractor using sr=None enforcement throughout.

## What Was Built

### pipeline/config.py
Single source of truth for all DSP constants used across the pipeline:
- `N_FFT=8192`, `HOP_LENGTH=512`, `PAD_SECONDS=2.0`, `MAX_FREQ_RESOLUTION_HZ=6.0`, `MIN_NOISE_DURATION_SEC=1.0`
- `verify_resolution(sr, n_fft)` — asserts `sr/n_fft < 6.0 Hz/bin`; raises `AssertionError` with `sr=VALUE` in the message so 96kHz recordings are immediately identifiable

### pipeline/ingestor.py
Three public functions covering INGEST-01 through INGEST-05:
- `parse_annotations(csv_path)` — normalizes column names (lowercase, stripped) to handle unknown Raven Pro export formats; raises `ValueError` with actual column list on missing required cols; prints first 5 rows for manual verification
- `load_call_segment(wav_path, start_sec, end_sec, pad_seconds)` — always uses `librosa.load(..., sr=None)` to prevent silent resampling; calls `verify_resolution(sr)` on every load
- `extract_noise_gaps(wav_path, calls, recording_duration)` — extracts gaps >= `MIN_NOISE_DURATION_SEC` between sorted call intervals; returns `[]` when no usable gaps (callers must handle gracefully)

### requirements.txt
Phase 1 dependencies pinned at `librosa==0.11.0` with `>=` constraints for supporting libraries.

### data/ directory structure
`data/recordings/`, `data/segments/`, `data/noise_segments/` created with `.gitkeep` files per research doc architecture.

## Tests Written (TDD)

16 tests across two files — all pass:
- `tests/test_config.py` — 7 tests covering constants and `verify_resolution` for 44100/48000 (pass) and 96000 Hz (fail with correct error content)
- `tests/test_ingestor.py` — 9 tests covering annotation parsing, noise gap extraction variants, and `sr=None` enforcement via source inspection

## Decisions Made

1. `verify_resolution()` takes an optional `n_fft` parameter (default: `N_FFT` from config) — allows callers to override for 96kHz recordings that need `n_fft=16384`. This was not in the plan spec but prevents a Rule 2 (missing critical functionality) issue.
2. `extract_noise_gaps()` explicitly handles the empty-calls case — returns full recording as noise gap if `>= MIN_NOISE_DURATION_SEC`, otherwise `[]`. Matches research doc Pattern 4 but extends it.
3. `MIN_NOISE_DURATION_SEC` is imported from `pipeline.config` into `ingestor.py` — not re-defined as a local constant.

## Deviations from Plan

### Auto-added: Optional n_fft parameter to verify_resolution (Rule 2)

- **Found during:** Task 1 implementation review
- **Issue:** Research doc Pitfall 4 explicitly notes that 96kHz recordings with `n_fft=8192` give 11.7 Hz/bin (too coarse). Plan spec had `verify_resolution(sr: int)` with no way to pass a different n_fft. Callers handling 96kHz files would need to either monkey-patch `N_FFT` or skip verification.
- **Fix:** Added `n_fft: int = N_FFT` parameter to `verify_resolution()`. Default behavior unchanged; callers can pass `n_fft=16384` when needed.
- **Files modified:** `pipeline/config.py`
- **Commit:** c8dacc5

None — plan executed as written otherwise.

## Known Stubs

None. All functions are fully implemented. `wav_path` parameter in `extract_noise_gaps()` is reserved for future metadata use (documented in docstring) but its absence does not prevent the function's goal.

## Self-Check: PASSED

All created files verified to exist on disk. All 5 task commits verified in git log:
- 89cf524: test(01-01): add failing tests for pipeline.config constants and verify_resolution
- c8dacc5: feat(01-01): implement pipeline.config — DSP constants and resolution assertion
- 33dd947: test(01-01): add failing tests for pipeline.ingestor functions
- 74d2868: feat(01-01): implement pipeline.ingestor — annotation parser, segment loader, noise gap extractor
- 0427710: chore(01-01): add requirements.txt and data directory structure
