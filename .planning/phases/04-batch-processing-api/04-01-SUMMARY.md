---
phase: 04-batch-processing-api
plan: "01"
subsystem: pipeline/scoring
tags: [scoring, snr, confidence, fastapi, tdd]
dependency_graph:
  requires: []
  provides: [pipeline.scoring.compute_snr_db, pipeline.scoring.compute_confidence]
  affects: [pipeline/batch_runner.py, api/main.py]
tech_stack:
  added: [fastapi>=0.115, uvicorn[standard]>=0.29, python-multipart>=0.0.9]
  patterns: [TDD-red-green, lifted-from-script, numpy-array-synthesis]
key_files:
  created: [pipeline/scoring.py, tests/test_scoring.py]
  modified: [requirements.txt]
decisions:
  - "compute_snr_db lifted verbatim from scripts/demo_spectrograms.py — preserves proven logic"
  - "compute_confidence takes f0_contour directly (not ctx dict) — decoupled from caller structure"
  - "Test for sentinel -999.0 uses freq_bins capped at 100 Hz with f0=200 Hz — simpler than exceeding Nyquist"
  - "test_zero_score uses f0=[0]*19+[1000] to guarantee stability clamps to 0 — deterministic"
metrics:
  duration: "2 minutes"
  completed_date: "2026-04-12"
  tasks_completed: 2
  files_changed: 3
---

# Phase 04 Plan 01: Scoring Module and FastAPI Dependencies Summary

Canonical `pipeline/scoring.py` created with `compute_snr_db` (lifted verbatim from demo script) and `compute_confidence` (SNR improvement + harmonic integrity + f0 stability, 0–100 score). FastAPI/uvicorn/python-multipart added to requirements.txt.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create pipeline/scoring.py (TDD) | c05975a | pipeline/scoring.py, tests/test_scoring.py |
| 2 | Add FastAPI deps to requirements.txt | d1ab59e | requirements.txt |

## Decisions Made

- `compute_snr_db` lifted verbatim from `scripts/demo_spectrograms.py` lines 52–86 per plan instruction — avoids duplicating proven logic and ensures demo figures and batch scoring use the same implementation.
- `compute_confidence` takes `f0_contour` as a direct numpy array parameter (not a ctx dict) — decouples the function from any particular caller's data structure.
- TDD sentinel test uses a narrow `freq_bins` array (0–100 Hz) with `f0_median=200` (first harmonic exceeds max) — more deterministic than relying on Nyquist arithmetic.
- Zero-score stability test uses `[0]*19 + [1000]` contour — guarantees std >> mean so stability clamps to exactly 0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test for -999.0 sentinel used incorrect f0_median**
- **Found during:** TDD GREEN phase
- **Issue:** `f0_median=9999.0` with full 44100 Hz freq_bins — first harmonic (9999 Hz) is within range, so no sentinel returned
- **Fix:** Changed test to use `freq_bins` capped at 100 Hz and `f0_median=200 Hz` so the first harmonic exceeds the bin range
- **Files modified:** tests/test_scoring.py
- **Commit:** c05975a

**2. [Rule 1 - Bug] test_zero_score threshold too tight**
- **Found during:** TDD GREEN phase
- **Issue:** Random f0 contour had partial stability (~10 pts), exceeding the < 5.0 assertion
- **Fix:** Replaced random f0 with deterministic `[0]*19 + [1000]` that guarantees stability=0; assertion changed to `== 0.0`
- **Files modified:** tests/test_scoring.py
- **Commit:** c05975a

## Known Stubs

None — both functions return fully computed values on any valid input.

## Self-Check: PASSED
