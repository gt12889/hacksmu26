---
phase: 02-harmonic-detection-denoising
verified: 2026-04-11T00:00:00Z
status: human_needed
score: 5/5 automated must-haves verified
re_verification: false
human_verification:
  - test: "Run process_call.py on 5 real field recordings and confirm f0 is in 8-25 Hz"
    expected: "stdout prints 'f0 contour — median: X.X Hz' with X.X between 8.0 and 25.0 for all 5 calls"
    why_human: "No real WAV files are available in the repo; success criterion requires on-device testing against actual elephant call recordings"
  - test: "Listen to audio_clean output from a real call and compare to input WAV"
    expected: "Elephant rumble is audible in cleaned audio; generator hum / car noise is reduced relative to input"
    why_human: "Audible quality improvement is a stated success criterion and cannot be verified programmatically"
  - test: "View before/after spectrograms of cleaned call and confirm comb mask is visually preserving harmonic contours"
    expected: "Harmonic stripes are clearly visible in cleaned spectrogram; noise floor between harmonics is attenuated"
    why_human: "Visual spectrogram quality is a stated success criterion (Success Criterion 2 in ROADMAP) requiring human inspection"
---

# Phase 2: Harmonic Detection & Denoising Verification Report

**Phase Goal:** The system detects elephant f0 via subharmonic summation and applies a time-varying harmonic comb mask to extract clean vocalizations — demonstrated to work on at least 5 known calls
**Verified:** 2026-04-11
**Status:** human_needed — all automated checks pass; 3 items require human verification on real recordings
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from PLAN frontmatter must_haves)

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1   | process_call() returns dict with audio_clean key containing non-empty float array | VERIFIED | pytest TestProcessCall::test_returns_ctx_with_audio_clean passes; inline script shows shape (132096,) |
| 2   | f0_contour values in 8-25 Hz on synthetic 15 Hz + dominant 30 Hz signal (octave check) | VERIFIED | Inline script: f0_contour median = 16.07 Hz; pytest TestDetectF0Shs::test_f0_median_in_8_to_25_hz passes |
| 3   | comb_mask is float32 array of shape (n_freq_bins, n_frames) with values in [0.0, 1.0] | VERIFIED | Inline script: dtype=float32, shape=(4097,259), range 0.0-1.0; pytest TestBuildCombMask passes 5/5 |
| 4   | Generator noise_type routes to stationary noisereduce; all other types route to non-stationary | VERIFIED | apply_noisereduce lines 234-255: generator+clip → stationary=True, prop_decrease=0.8; else → stationary=False; pytest TestApplyNoisereduce passes 5/5 |
| 5   | HPSS produces magnitude_harmonic with same shape as input magnitude | VERIFIED | pytest TestHpssEnhance::test_magnitude_harmonic_same_shape passes; shapes confirmed equal |

**Score:** 5/5 automated truths verified

### Plan 02 Additional Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| A   | pytest tests/test_harmonic_processor.py passes with zero failures | VERIFIED | 30/30 tests pass in 18.06s |
| B   | scripts/process_call.py --help shows usage without errors | VERIFIED | --help exits 0; shows all 6 args: --wav, --start, --end, --output, --noise-type, --pad |
| C   | On 5 manual calls, detected f0 is in 8-25 Hz range | HUMAN NEEDED | CLI is functional; no real recordings in repo to run against |
| D   | Cleaned audio is audibly different from input | HUMAN NEEDED | Cannot verify programmatically; requires listening test |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `pipeline/harmonic_processor.py` | hpss_enhance, detect_f0_shs, build_comb_mask, apply_comb_mask, apply_noisereduce, process_call | VERIFIED | 293 lines; all 6 functions present and substantive |
| `requirements.txt` | noisereduce==3.0.3 dependency | VERIFIED | `noisereduce==3.0.3` found in Core audio DSP section |
| `tests/test_harmonic_processor.py` | 30-test pytest suite covering all 6 functions | VERIFIED | 30 tests collected and passing |
| `scripts/process_call.py` | CLI with argparse; calls process_call(); saves via soundfile | VERIFIED | argparse wired; process_call() called at line 117; sf.write() at line 125 |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| harmonic_processor.py:hpss_enhance | spectrogram.py:compute_stft | ctx['magnitude'] consumed | WIRED | Line 46: `magnitude = ctx["magnitude"]`; line 67: ctx["magnitude_harmonic"] set |
| harmonic_processor.py:detect_f0_shs | harmonic_processor.py:hpss_enhance | reads ctx['magnitude_harmonic'] | WIRED | Line 86: `magnitude = ctx["magnitude_harmonic"]` (explicit comment: NOT ctx["magnitude"]) |
| harmonic_processor.py:apply_comb_mask | spectrogram.py:reconstruct_audio | calls reconstruct_audio(masked_magnitude, ctx['phase']) | WIRED | Line 206: `ctx["audio_comb_masked"] = reconstruct_audio(masked_magnitude, ctx["phase"])` |
| harmonic_processor.py:apply_noisereduce | noise_classifier.py:classify_noise_type | branches on ctx['noise_type']['type'] == 'generator' | WIRED | Lines 234-254: `if noise_type == "generator":` / else branches |
| tests/test_harmonic_processor.py | pipeline/harmonic_processor.py | imports all 6 functions | WIRED | Lines 88-96: all 6 functions imported in test_imports() |
| scripts/process_call.py | pipeline/harmonic_processor.py:process_call | calls process_call() and saves ctx['audio_clean'] | WIRED | Line 39: `from pipeline.harmonic_processor import process_call`; line 117: ctx = process_call(); line 125: sf.write(...ctx['audio_clean']...) |

### Requirements Coverage

All 9 requirement IDs declared in both PLANs are accounted for. Both 02-01-PLAN.md and 02-02-PLAN.md declare the same full set (HARM-01 through HARM-06, CLEAN-01 through CLEAN-03).

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| HARM-01 | 02-01, 02-02 | HPSS with tuned kernel to separate harmonic content | SATISFIED | hpss_enhance: kernel = max(5, round(27/hz_per_bin)) bins; margin=(2.0,2.0); magnitude_harmonic added |
| HARM-02 | 02-01, 02-02 | Median filtering along time axis for horizontal harmonic contours | SATISFIED | hpss_enhance uses librosa.decompose.hpss which applies median filter along time axis internally; pattern described in module docstring |
| HARM-03 | 02-01, 02-02 | SHS f0 detection sweeping 8-25 Hz, summing power at integer multiples up to 1000 Hz | SATISFIED | detect_f0_shs: f0_candidates = np.arange(8.0, 25.0, hz_per_bin/2); MAX_HARMONIC_HZ=1000.0; vectorized NSSH |
| HARM-04 | 02-01, 02-02 | Octave-check heuristic to prevent 2f0 misdetection | SATISFIED | detect_f0_shs lines 120-130: per-frame check, if f0>30Hz and half_power >= 0.7*best_power, halve f0; test passes on dominant-30Hz signal |
| HARM-05 | 02-01, 02-02 | Time-varying harmonic comb mask at k*f0 with ±5Hz bandwidth | SATISFIED | build_comb_mask: BANDWIDTH_HZ=5.0; triangular taper; loops k=1..1000Hz; float32 output |
| HARM-06 | 02-01, 02-02 | Comb mask applied to magnitude spectrogram; ISTFT reconstruction with original phase | SATISFIED | apply_comb_mask: ctx["magnitude"]*ctx["comb_mask"]; reconstruct_audio called with ctx["phase"] |
| CLEAN-01 | 02-01, 02-02 | noisereduce non-stationary spectral gating on comb-masked output | SATISFIED | apply_noisereduce else branch: nr.reduce_noise(y=audio, sr=sr, stationary=False) |
| CLEAN-02 | 02-01, 02-02 | Stationary noisereduce with noise profile for generator recordings | SATISFIED | apply_noisereduce generator+clip branch: stationary=True, y_noise=noise_clip, prop_decrease=0.8 |
| CLEAN-03 | 02-01, 02-02 | Cleanup strategy selected based on noise type classification | SATISFIED | apply_noisereduce: branches on ctx['noise_type']['type']; fallback RuntimeWarning for generator+no clip |

**No orphaned requirements.** REQUIREMENTS.md maps HARM-01 through HARM-06 and CLEAN-01 through CLEAN-03 to Phase 2; all are addressed in the plans and verified in the implementation.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| None found | — | — | — | — |

Scanned pipeline/harmonic_processor.py, tests/test_harmonic_processor.py, scripts/process_call.py for TODO/FIXME/placeholder/return null/hardcoded empty arrays. No blockers or stubs found. All functions have substantive implementations with real computation.

### Human Verification Required

#### 1. On-Device Test: 5 Real Calls — f0 Range

**Test:** For 5 manually identified calls from the 212-call annotation spreadsheet, run:
```
.venv/bin/python scripts/process_call.py --wav <path> --start <t> --end <t> --output /tmp/clean.wav
```
**Expected:** Each run prints `f0 contour — median: X.X Hz` with X.X between 8.0 and 25.0
**Why human:** No real WAV recordings exist in the repo. The CLI is fully functional and the automated tests use synthetic signals, but the ROADMAP success criterion explicitly requires "demonstrated to work on at least 5 known calls."

#### 2. Listening Test — Audible Noise Reduction

**Test:** Play the input WAV and the cleaned output WAV for one representative call per noise type (generator, car, plane).
**Expected:** Elephant rumble is preserved in cleaned audio; generator hum or broadband car noise is audibly reduced.
**Why human:** Subjective audio quality and the presence of an audible rumble vs. noise floor cannot be measured programmatically without ground-truth SNR labels.

#### 3. Visual Spectrogram Inspection — Comb Mask Effectiveness

**Test:** Use matplotlib or a spectrogram viewer to compare magnitude spectrograms of the raw and cleaned output for one call.
**Expected:** Horizontal harmonic stripes at k*f0 are visible and preserved; energy between harmonics is attenuated relative to the input.
**Why human:** Spectrogram visual quality is ROADMAP Success Criterion 2 ("harmonic comb mask visibly preserves elephant harmonic contours"). No reference spectrogram is checked in.

### Gaps Summary

No automated gaps. All 5 plan must-haves verified. All 9 requirement IDs satisfied with substantive evidence in the codebase. The 3 human verification items are not gaps in implementation — the code is correct and complete — they are the remaining verification steps that require real recordings and human judgment as specified in the ROADMAP success criteria.

The phase goal is achieved at the automated level. Human verification on real data is required to fully confirm the ROADMAP success criteria.

---

_Verified: 2026-04-11_
_Verifier: Claude (gsd-verifier)_
