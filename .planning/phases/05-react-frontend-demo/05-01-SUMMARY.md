---
phase: 05-react-frontend-demo
plan: 01
subsystem: api
tags: [fastapi, python, batch-results, audio-streaming, path-traversal-guard]

# Dependency graph
requires:
  - phase: 04-batch-processing-api
    provides: batch_runner.py writes data/outputs/*/summary.csv; UPLOAD_REGISTRY singleton; FileResponse/JSONResponse patterns in result.py
provides:
  - GET /api/batch/results reads data/outputs/*/summary.csv and returns merged results list
  - GET /api/upload/{file_id}/audio streams original uploaded WAV by file_id
  - GET /api/batch/audio?path= serves clean WAVs with allowlist path-traversal guard
affects: [05-react-frontend-demo, UI-03, UI-02, UI-01]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - BATCH_OUTPUT_DIR as monkeypatchable Path constant for testability
    - _ALLOWED_ROOTS resolved at import time for path-traversal security
    - Tests monkeypatch module-level constants (BATCH_OUTPUT_DIR, _ALLOWED_ROOTS) to avoid real filesystem side-effects

key-files:
  created: []
  modified:
    - api/routes/batch.py
    - api/routes/upload.py
    - tests/test_api.py

key-decisions:
  - "Returns 200 with empty results list (not 404) when data/outputs/ does not exist — empty is valid state for fresh checkout"
  - "clean_wav_path rewritten to absolute path in batch_results so React can pass it directly to /api/batch/audio"
  - "_ALLOWED_ROOTS resolved at import time from repo root via __file__ parents — deterministic regardless of working directory"
  - "batch_audio and batch_results added to same file (batch.py) alongside existing batch_summary — cohesive by batch domain"

patterns-established:
  - "Pattern: Path constants as module-level variables (BATCH_OUTPUT_DIR, _ALLOWED_ROOTS) enable monkeypatching without fixture magic"
  - "Pattern: Security allowlist — resolve path, check starts-with each allowed root + os.sep, 403 otherwise"

requirements-completed: [UI-03, UI-04]

# Metrics
duration: 15min
completed: 2026-04-11
---

# Phase 05 Plan 01: React Frontend Demo API Endpoints Summary

**Three read-only FastAPI endpoints added — batch disk results browsing, upload audio streaming, and path-guarded batch WAV serving — unblocking the React demo's A/B playback and pre-processed call browser**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-11T00:00:00Z
- **Completed:** 2026-04-11T00:15:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added GET /api/batch/results that reads all data/outputs/*/summary.csv files and merges into a unified result list with absolute clean_wav_path values
- Added GET /api/upload/{file_id}/audio to stream original uploaded WAVs by file_id, making A/B toggle robust to page refresh
- Added GET /api/batch/audio?path= with an allowlist path-traversal guard (data/outputs/, cleaned/) so batch-disk rows can render audio; 403 on escape attempts
- 21 tests all green; no regressions against the existing 14-test suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Add GET /api/batch/results endpoint** - `703b873` (feat)
2. **Task 2: Add GET /api/upload/{file_id}/audio** - `f4d978d` (feat)
3. **Task 3: Add tests for GET /api/batch/audio** - `4fa847a` (test)

## Files Created/Modified

- `api/routes/batch.py` - Added BATCH_OUTPUT_DIR constant, _ALLOWED_ROOTS allowlist, batch_results() and batch_audio() routes (alongside existing batch_summary)
- `api/routes/upload.py` - Added get_upload_audio() route with 404 for unknown/missing file_id
- `tests/test_api.py` - Added 7 new tests: test_get_upload_audio_not_found, test_get_upload_audio_ok, test_batch_audio_forbidden, test_batch_audio_not_found, test_batch_audio_ok, test_batch_results_empty, test_batch_results_with_fixture

## Decisions Made

- Returns 200 + empty list (not 404) when data/outputs/ is absent — empty is a valid state for fresh checkout; 404 would confuse the React client
- clean_wav_path rewritten to absolute in batch_results response so React can pass it verbatim to /api/batch/audio
- Path-traversal guard resolves path and checks starts-with each allowed root + os.sep to prevent symlink escapes

## Deviations from Plan

**1. [Rule 1 - Implementation order] batch_audio implemented in Task 1 commit alongside batch_results**
- **Found during:** Task 1 (creating batch.py additions)
- **Issue:** Plan assigned batch_audio to Task 3 but the _ALLOWED_ROOTS constant and batch_audio route naturally belong in the same file edit as BATCH_OUTPUT_DIR and batch_results — splitting would require two separate edits to the same file
- **Fix:** Implemented batch_audio() route in Task 1's file edit; Task 3 added only the tests
- **Files modified:** api/routes/batch.py (Task 1), tests/test_api.py (Task 3)
- **Verification:** All 3 Task 3 tests pass green on first run

---

**Total deviations:** 1 (implementation order — no scope creep, no correctness impact)
**Impact on plan:** Zero. All acceptance criteria met; tests pass; security model intact.

## Issues Encountered

None - implementation was straightforward following existing FileResponse/JSONResponse patterns from result.py.

## User Setup Required

None - no external service configuration required. data/outputs/ is populated by the batch pipeline from Phase 4.

## Next Phase Readiness

- All three endpoints are registered on app.router (15 routes total, up from 12)
- React demo can now browse 212 pre-processed calls via GET /api/batch/results
- React A/B toggle can survive page refresh via GET /api/upload/{file_id}/audio
- SpectrogramView for batch rows unblocked via GET /api/batch/audio?path=
- No new Python dependencies added

---
*Phase: 05-react-frontend-demo*
*Completed: 2026-04-11*
