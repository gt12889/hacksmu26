---
phase: 04-batch-processing-api
plan: "02"
subsystem: pipeline/batch_runner
tags: [batch, orchestration, csv-export, raven-pro, tdd]
dependency_graph:
  requires: [pipeline.harmonic_processor.process_call, pipeline.ingestor.load_call_segment, pipeline.scoring.compute_snr_db, pipeline.scoring.compute_confidence, pipeline.spectrogram.compute_stft]
  provides: [pipeline.batch_runner.run_batch, pipeline.batch_runner.write_summary_csv, pipeline.batch_runner.write_raven_selection_table]
  affects: [api/main.py]
tech_stack:
  added: []
  patterns: [TDD-red-green, re-STFT-snr-after, normalize-before-write, locale-safe-tsv]
key_files:
  created: [pipeline/batch_runner.py, tests/test_batch_runner.py]
  modified: []
decisions:
  - "Result dict uses f0_median_hz, snr_before_db, snr_after_db (not short names from research doc) — prevents write_summary_csv KeyError"
  - "SNR-after computed via re-STFT on audio_clean (not masked_magnitude) — matches demo_spectrograms.py pattern at line 198-204"
  - "WAV normalization: audio / peak before sf.write — guards against PCM_16 clipping from noisereduce output"
  - "Raven TSV floats use f'{value:.6f}' — locale-safe, no comma-decimal ambiguity per Pitfall 7"
  - "noise_type annotation column bypasses classify_noise_type() for speed and determinism in tests"
metrics:
  duration: "4 minutes"
  completed_date: "2026-04-12"
  tasks_completed: 1
  files_changed: 2
---

# Phase 04 Plan 02: Batch Runner Summary

`pipeline/batch_runner.py` created with `run_batch`, `write_summary_csv`, and `write_raven_selection_table`. The batch runner orchestrates all 212 calls through process_call(), attaches SNR/confidence scores, exports normalized cleaned WAVs, and generates Raven Pro selection tables. Full 21-test pytest suite on synthetic fixtures — no real audio required.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 (RED) | Add failing tests for batch_runner | a0da193 | tests/test_batch_runner.py |
| 1 (GREEN) | Implement pipeline/batch_runner.py | 1e92eef | pipeline/batch_runner.py |

## Decisions Made

- Result dict key names use `_hz` and `_db` suffixes (`f0_median_hz`, `snr_before_db`, `snr_after_db`) throughout run_batch, write_summary_csv, and write_raven_selection_table — prevents KeyError if caller uses short names.
- SNR-after uses re-STFT on `audio_clean` (Pattern from `scripts/demo_spectrograms.py` lines 198-204) — measures actual post-denoising spectral state, not the comb-masked intermediate.
- WAV export normalizes by dividing by peak amplitude before `sf.write(..., subtype="PCM_16")` — noisereduce can produce values slightly above 1.0 which cause PCM_16 clipping.
- Raven Pro TSV all float fields formatted as `f"{value:.6f}"` — prevents locale-dependent comma-as-decimal-separator issues on European OS locales (Pitfall 7 from RESEARCH.md).
- `noise_type` annotation column (when present and non-NaN) bypasses `classify_noise_type()` — used in tests for speed and determinism; also useful when annotations already have labeled noise types.

## Deviations from Plan

None — plan executed exactly as written. The research doc's example used `f0_median`, `snr_before`, `snr_after` (short names) in the Raven TSV example, but the plan's `<action>` block explicitly flagged this as wrong and mandated the suffixed names. Implementation followed the plan correctly.

## Known Stubs

None — all three exported functions are fully implemented and return real computed values.

## Self-Check: PASSED
