---
phase: 02-harmonic-detection-denoising
plan: "01"
subsystem: harmonic-detection-denoising
tags: [hpss, shs, f0-detection, comb-mask, noisereduce, phase2]
dependency_graph:
  requires:
    - pipeline/spectrogram.py (compute_stft, reconstruct_audio)
    - pipeline/noise_classifier.py (classify_noise_type return schema)
    - pipeline/config.py (N_FFT=8192, HOP_LENGTH=512)
  provides:
    - pipeline/harmonic_processor.py (hpss_enhance, detect_f0_shs, build_comb_mask, apply_comb_mask, apply_noisereduce, process_call)
  affects:
    - Phase 3 visualization (reads ctx["f0_contour"], ctx["comb_mask"] for overlay)
    - Phase 3 export (reads ctx["audio_clean"] for WAV output)
tech_stack:
  added:
    - noisereduce==3.0.3
  patterns:
    - Vectorized NSSH (normalized subharmonic summation) using numpy fancy indexing
    - Soft triangular comb mask (float32, values [0,1]) to prevent musical noise
    - HPSS with Hz-calibrated kernel (27 Hz / hz_per_bin) for infrasonic resolution
    - Octave-check heuristic: halve f0 if energy at f0/2 >= 0.7 * energy at f0
    - Noise-type routing: generator+clip → stationary noisereduce; all others → non-stationary
key_files:
  created:
    - pipeline/harmonic_processor.py
    - tests/test_harmonic_processor.py
  modified:
    - requirements.txt (added noisereduce==3.0.3)
decisions:
  - "apply_noisereduce falls back to non-stationary with RuntimeWarning when generator + no noise_clip (does NOT raise ValueError as in research Pattern 5)"
  - "detect_f0_shs uses vectorized NSSH loop (not per-frame Python loop) per plan instruction to avoid 5-20s/call processing time"
  - "build_comb_mask uses original ctx['magnitude'] for shape reference; mask applied to original (not HPSS) magnitude in apply_comb_mask"
metrics:
  duration: "~4 minutes"
  completed: "2026-04-12"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 2 Plan 1: Harmonic Processor — SUMMARY

One-liner: HPSS pre-separation + vectorized NSSH f0 detection with octave-check + time-varying soft comb mask + noisereduce-adaptive cleanup in a single pipeline/harmonic_processor.py module.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add noisereduce to requirements.txt | 97de3fb | requirements.txt |
| 2 (RED) | Add failing TDD tests for harmonic_processor | f205d1e | tests/test_harmonic_processor.py |
| 2 (GREEN) | Implement pipeline/harmonic_processor.py | 99ba577 | pipeline/harmonic_processor.py |

## What Was Built

A single `pipeline/harmonic_processor.py` module with 6 exported functions that form the full Phase 2 chain:

1. **hpss_enhance** — HPSS with a 27 Hz / hz_per_bin harmonic kernel (infrasonic-calibrated vs. default 167 Hz span). margin=(2.0, 2.0) creates a residual bucket to discard ambiguous content. Stores `magnitude_harmonic` and `hz_per_bin` in ctx.

2. **detect_f0_shs** — Vectorized NSSH sweeping 8-25 Hz. Uses `magnitude[harmonic_bins, :]` fancy indexing to process all frames at once. Octave-check: per-frame, if detected f0 > 30 Hz and energy at f0/2 >= 70% of energy at f0, halves the estimate. This corrects the systematic 2nd-harmonic dominance artifact unique to elephant rumbles. Final f0_contour smoothed via median_filter(size=9).

3. **build_comb_mask** — Time-varying float32 comb mask (shape: n_freq_bins × n_frames). For each frame builds triangular teeth at k*f0 for k=1 up to 1000 Hz. Triangular taper (1.0 center, 0.0 at ±bandwidth_bins) prevents hard-edge musical noise artifacts. Uses max() when teeth overlap.

4. **apply_comb_mask** — Multiplies ctx["magnitude"] (original, not HPSS output) by comb_mask. Calls reconstruct_audio(masked_magnitude, ctx["phase"]) using original phase for artifact-free ISTFT.

5. **apply_noisereduce** — Routes to stationary mode (generator + clip provided) or non-stationary (all others). If generator but clip=None: RuntimeWarning + non-stationary fallback, does NOT raise.

6. **process_call** — Entry point. Chains all 5 stages in order: compute_stft → hpss_enhance → detect_f0_shs → build_comb_mask → apply_comb_mask → apply_noisereduce.

## Verification Results

Inline verification on 15 Hz fundamental + 30 Hz dominant 2nd harmonic synthetic signal:

```
audio_clean shape: (132096,)
f0_contour median: 16.074951171875    ← in 8-25 Hz range (not octave-error 30 Hz)
comb_mask shape: (4097, 259)
comb_mask dtype: float32
comb_mask range: 0.0 - 1.0
ALL ASSERTIONS PASSED
```

All 30 unit tests pass (pytest 18s).

## Decisions Made

1. **apply_noisereduce fallback**: Research Pattern 5 raised ValueError for generator+no noise_clip. Plan overrides this: RuntimeWarning + non-stationary fallback. Rationale: field recordings may lack usable noise gaps; crashing the pipeline is worse than degraded output.

2. **Vectorized NSSH**: Plan explicitly selected the vectorized SHS variant from research. The per-frame Python loop would take 5-20s/call; vectorized version processes a 3s call at 44100 Hz in under 1s.

3. **detect_f0_shs reads magnitude_harmonic**: HPSS output (not raw magnitude) is used for SHS to avoid engine harmonic bias from contaminating the f0 vote.

4. **apply_comb_mask reads ctx["magnitude"]**: Original (pre-HPSS) magnitude is used for reconstruction to preserve correct amplitude relationships.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files created/modified:
- FOUND: /home/gt120/projects/hacksmu26/pipeline/harmonic_processor.py
- FOUND: /home/gt120/projects/hacksmu26/tests/test_harmonic_processor.py
- FOUND: noisereduce==3.0.3 in /home/gt120/projects/hacksmu26/requirements.txt

Commits:
- FOUND: 97de3fb (chore: noisereduce to requirements)
- FOUND: f205d1e (test: failing TDD tests)
- FOUND: 99ba577 (feat: harmonic_processor implementation)
