---
phase: 07-demo-audio-proxy-fixes
plan: "01"
subsystem: demo-pipeline
tags: [gap-closure, audio-export, vite-proxy, deduplication]
dependency_graph:
  requires: []
  provides: [original-wav-export, unified-proxy, deduplicated-snr-import]
  affects: [frontend-ab-toggle, demo-spectrograms-pipeline]
tech_stack:
  added: []
  patterns: [import-deduplication, 3-tuple-return, wav-normalization]
key_files:
  created: []
  modified:
    - scripts/demo_spectrograms.py
    - frontend/vite.config.ts
    - tests/test_demo_spectrograms.py
decisions:
  - "Import compute_snr_db from pipeline.scoring — single canonical implementation, no duplicates"
  - "make_demo_figure returns 3-tuple (png, clean_wav, original_wav) — enables frontend A/B toggle"
  - "Both Vite proxy rules target port 8000 — FastAPI is a single process, split ports were a configuration bug"
metrics:
  duration_minutes: 5
  completed_date: "2026-04-12"
  tasks_completed: 3
  files_modified: 3
---

# Phase 07 Plan 01: Demo Audio & Proxy Fixes Summary

**One-liner:** Three gap-closure fixes: deduplicated compute_snr_db import from pipeline.scoring, exported {noise_type}_original.wav in make_demo_figure for frontend A/B toggle, and unified Vite proxy to port 8000 for both /api and /static routes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Deduplicate compute_snr_db — import from pipeline.scoring | 71248d0 | scripts/demo_spectrograms.py |
| 2 | Export _original.wav in make_demo_figure | e02694e | scripts/demo_spectrograms.py |
| 3 | Unify Vite proxy to port 8000 | 0e7e49c | frontend/vite.config.ts |
| - | Auto-fix: update tests for 3-tuple return | c4278f8 | tests/test_demo_spectrograms.py |

## Verification

- `grep -c "def compute_snr_db" scripts/demo_spectrograms.py` → 0 (no local definition)
- `grep "from pipeline.scoring import compute_snr_db"` → 1 matching line
- `python scripts/demo_spectrograms.py --synthetic --output-dir /tmp/demo_verify_07b` produces 9 files: 3 PNG + 3 clean WAV + 3 original WAV
- `grep -c "localhost:8000" frontend/vite.config.ts` → 2 (both proxy rules)
- `grep "8001" frontend/vite.config.ts` → no output
- All 171 tests pass (77.88s)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_demo_spectrograms.py for 3-tuple return value**
- **Found during:** Task 2 verification (running full test suite)
- **Issue:** `test_make_demo_figure_creates_files`, `test_all_three_noise_types_produce_files`, and `test_wav_is_valid_pcm` all unpacked only 2 values from `make_demo_figure`, which now returns 3
- **Fix:** Updated all three tests to unpack `(png_path, wav_path, wav_original_path)` and added assertion for `wav_original_path.exists()`
- **Files modified:** tests/test_demo_spectrograms.py
- **Commit:** c4278f8

## Known Stubs

None — all three fixes are complete and wired. The `_original.wav` files are now written by the demo pipeline and will be served by the FastAPI `/static/demo` mount. The Vite proxy now correctly routes all API traffic to port 8000.

## Self-Check: PASSED

- scripts/demo_spectrograms.py: modified (import deduplicated, original WAV export added)
- frontend/vite.config.ts: modified (port 8001 → 8000 for /api)
- tests/test_demo_spectrograms.py: modified (3-tuple unpack)
- Commits 71248d0, e02694e, 0e7e49c, c4278f8: all present in git log
- 9 demo files generated in /tmp/demo_verify_07b
- 171/171 tests pass
