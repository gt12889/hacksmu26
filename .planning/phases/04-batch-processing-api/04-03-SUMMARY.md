---
phase: 04-batch-processing-api
plan: "03"
subsystem: scripts/cli
tags: [batch, cli, argparse, synthetic-mode, csv-export, raven-pro]
dependency_graph:
  requires:
    - phase: 04-batch-processing-api
      provides: pipeline.batch_runner.run_batch, write_summary_csv, write_raven_selection_table
    - phase: 04-batch-processing-api
      provides: pipeline.ingestor.parse_annotations
  provides:
    - scripts/batch_process.py — CLI entrypoint for full offline batch run of all 212 calls
  affects: [api/main.py, README, hackathon demo]
tech-stack:
  added: []
  patterns: [noise-tail-for-gap-detection, synthetic-wav-builder, argparse-synthetic-flag]
key-files:
  created: [scripts/batch_process.py]
  modified: []
key-decisions:
  - "Synthetic WAVs written with 5-second white noise tail appended so extract_noise_gaps() finds a real noise profile (without tail, batch_runner's 30-second lookahead requests audio past end-of-file, returning empty array that crashes noisereduce stationary mode)"
  - "noise_type column set in synthetic DataFrame to bypass classify_noise_type() — matches batch_runner's annotation-column fast path for speed and determinism"
  - "cleaned_dir = output_dir / 'cleaned' passed as output_dir to run_batch — keeps top-level output_dir clean for summary files"
patterns-established:
  - "Synthetic mode pattern: write actual WAVs with appended noise tails rather than mocking I/O — validates the full pipeline end-to-end including gap extraction"
  - "Progress callback guards: only print every 10 calls (or final) to reduce terminal noise during long batch runs"
requirements-completed: [BATCH-01, BATCH-03, BATCH-04, BATCH-05]
duration: 2min
completed: "2026-04-12"
---

# Phase 04 Plan 03: Batch Process CLI Summary

**`scripts/batch_process.py` CLI entrypoint wraps `run_batch` with argparse, producing batch_summary.csv, raven_selection.txt, and cleaned WAVs from either real recordings or synthetic test audio**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-12T03:23:38Z
- **Completed:** 2026-04-12T03:26:28Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created `scripts/batch_process.py` as thin CLI wrapper around `pipeline/batch_runner.run_batch`
- `--synthetic` mode generates 3 noise-type WAVs with noise tails and runs full pipeline without real recordings
- All three outputs verified: `batch_summary.csv` with correct header, `raven_selection.txt` with TSV header, `cleaned/` with 3 WAV files
- All 30 existing tests continue to pass (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scripts/batch_process.py CLI entrypoint** - `dd5fb51` (feat)

**Plan metadata:** (docs commit — see final_commit below)

## Files Created/Modified
- `scripts/batch_process.py` - CLI entrypoint: argparse, synthetic mode, progress callback, output writing

## Decisions Made
- Synthetic WAVs include a 5-second appended noise tail so `extract_noise_gaps()` finds a real noise segment. Without the tail, `batch_runner`'s `recording_duration = row.end + 30.0` lookahead tries to load audio past end-of-file, returning an empty numpy array that causes noisereduce's stationary mode to crash with `zero-size array` ValueError.
- `noise_type` column present in synthetic DataFrame so `batch_runner` uses the annotation fast-path, bypassing `classify_noise_type()` for speed and determinism.
- `cleaned_dir = output_dir / "cleaned"` keeps output root uncluttered for the CSV/TSV files.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed zero-size noise clip crashing noisereduce stationary mode**
- **Found during:** Task 1 (batch_process.py creation + verification run)
- **Issue:** Synthetic WAVs were written with `end=duration` (exact file length). `batch_runner.run_batch` calls `extract_noise_gaps(wav_path, [(start, end)], end + 30.0)`, finding a 30-second "gap" from `end` to `end+30`. `load_call_segment(wav_path, end, end+30, pad_seconds=0.0)` then loads audio past end-of-file, returning an empty array. noisereduce stationary mode called with this empty `y_noise` raised `ValueError: zero-size array to reduction operation maximum which has no identity`.
- **Fix:** Appended a 5-second white noise tail to each synthetic WAV before writing. Now `extract_noise_gaps` correctly finds a real 5-second gap within the file.
- **Files modified:** `scripts/batch_process.py` (`_build_synthetic_annotations`)
- **Verification:** `python scripts/batch_process.py --synthetic --output-dir /tmp/batch_test_output` exits 0, all 3 outputs produced
- **Committed in:** dd5fb51 (Task 1 commit — fix applied during initial implementation before commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Required for correct synthetic mode operation. No scope creep.

## Issues Encountered
- noisereduce stationary mode crash when noise clip is empty (zero-length numpy array from past-end-of-file load). Root cause: batch_runner's 30-second recording-duration lookahead extends beyond synthetic file length. Resolved by appending real noise data to synthetic WAVs.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `scripts/batch_process.py` is executable from repo root: `python scripts/batch_process.py --synthetic --output-dir data/outputs/batch`
- Real recordings mode requires `--annotations` (CSV/XLSX) and `--recordings-dir`
- FastAPI integration (api/main.py) can call `run_batch` directly — same interface used by this CLI

## Self-Check: PASSED

- scripts/batch_process.py: FOUND
- 04-03-SUMMARY.md: FOUND
- Commit dd5fb51: FOUND

---
*Phase: 04-batch-processing-api*
*Completed: 2026-04-12*
