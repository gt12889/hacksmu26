---
phase: 02-harmonic-detection-denoising
plan: "02"
subsystem: testing
tags: [pytest, harmonic-processor, hpss, shs, comb-mask, noisereduce, cli, soundfile, argparse]

# Dependency graph
requires:
  - phase: 02-01
    provides: "harmonic_processor.py with hpss_enhance, detect_f0_shs, build_comb_mask, apply_comb_mask, apply_noisereduce, process_call"
  - phase: 01-pipeline-foundation
    provides: "compute_stft, load_call_segment, extract_noise_gaps, classify_noise_type"
provides:
  - "30-test pytest suite for all 6 harmonic_processor functions covering HARM-01 through HARM-06 and CLEAN-01 through CLEAN-03"
  - "scripts/process_call.py CLI for manual verification on real field recordings"
  - "f0 range validation (8-25 Hz), octave-check, comb mask shape/dtype/value, noisereduce routing tests"
affects:
  - "Phase 3 — any phase using process_call() output can rely on verified contracts"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Test fixtures chain through pipeline stages using pytest fixture dependencies (ctx_after_stft → ctx_after_hpss → ctx_after_f0 → ctx_after_mask → ctx_after_apply)"
    - "CLI scripts use sys.path.insert(_repo_root) pattern for package import without installation"
    - "Noise type dict pattern: {'type': str, 'spectral_flatness': float, 'low_freq_ratio': float}"

key-files:
  created:
    - tests/test_harmonic_processor.py
    - scripts/process_call.py
  modified: []

key-decisions:
  - "test_harmonic_processor.py was delivered in Plan 01 TDD RED phase (f205d1e) — Plan 02 verified it passes (30/30) rather than recreating it"
  - "CLI uses --noise-type override for testing without real recordings; auto-detects via classify_noise_type() when omitted"
  - "generator noise clip loaded via extract_noise_gaps() for stationary noisereduce; falls back with print warning when no gap found"

patterns-established:
  - "All Phase 2 tests use synthetic sine wave fixtures at sr=44100 — no real WAV files required, making CI portable"
  - "inspect.getsource() used to verify implementation reads correct ctx key (magnitude_harmonic not magnitude)"
  - "CLI scripts print [module] prefixed progress lines to stdout for human monitoring"

requirements-completed: [HARM-01, HARM-02, HARM-03, HARM-04, HARM-05, HARM-06, CLEAN-01, CLEAN-02, CLEAN-03]

# Metrics
duration: 2min
completed: 2026-04-12
---

# Phase 2 Plan 02: Tests and CLI for Harmonic Processor Summary

**30-test pytest suite covering all 6 harmonic_processor functions plus a CLI script (scripts/process_call.py) that runs the full Phase 2 pipeline on real field recordings with f0 statistics output**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-12T01:08:20Z
- **Completed:** 2026-04-12T01:09:49Z
- **Tasks:** 2
- **Files modified:** 1 created (scripts/process_call.py), 1 verified existing (tests/test_harmonic_processor.py)

## Accomplishments

- Verified tests/test_harmonic_processor.py passes with 30/30 tests covering HARM-01 through HARM-06 and CLEAN-01 through CLEAN-03
- Created scripts/process_call.py as CLI entrypoint for manual Phase 2 verification on real recordings
- Full test suite (86 tests across all phases) passes with zero failures and zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Write tests/test_harmonic_processor.py** - `f205d1e` (test — committed in Plan 01 TDD RED phase; verified 30/30 pass in this plan)
2. **Task 2: Create scripts/process_call.py CLI demo script** - `ee65158` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `tests/test_harmonic_processor.py` - 30-test suite covering all 6 harmonic_processor functions; class-grouped by requirement (TestHpssEnhance, TestDetectF0Shs, TestBuildCombMask, TestApplyCombMask, TestApplyNoisereduce, TestProcessCall)
- `scripts/process_call.py` - CLI with argparse for --wav, --start, --end, --output, --noise-type, --pad; auto-detects noise type; loads noise clip for generator mode; prints f0 contour median/min/max; saves cleaned WAV via soundfile

## Decisions Made

- test_harmonic_processor.py was already committed in Plan 01 TDD RED phase (f205d1e). Plan 02 verified its correctness (30/30 pass) rather than recreating it — this is the correct behavior since Plan 01 depends_on is satisfied.
- CLI uses --noise-type override flag to allow testing without full noise classification; auto-detects via classify_noise_type() when not provided.
- Generator noise clip loading re-uses extract_noise_gaps() with the same call bounds — avoids loading full recording.

## Deviations from Plan

None - plan executed exactly as written. Task 1 test file was already committed from Plan 01 TDD RED phase and passes completely. Task 2 created as specified.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 is complete: harmonic_processor.py implemented and tested, CLI available for manual verification
- On 5 manual calls with real recordings, run: `python scripts/process_call.py --wav <path> --start <t> --end <t> --output clean.wav` to verify f0 in 8-25 Hz
- Phase 3 can proceed with publication-quality spectrograms (before/after with f0 contour overlay)

## Known Stubs

None - all pipeline functions are fully implemented and tested with real behavior.

---
*Phase: 02-harmonic-detection-denoising*
*Completed: 2026-04-12*
