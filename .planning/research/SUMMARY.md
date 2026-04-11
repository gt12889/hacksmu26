# Research Summary: ElephantVoices Denoiser

## Executive Summary

Domain-specific bioacoustic DSP pipeline, not a generic audio denoiser. Core differentiator: exploiting mathematical structure in elephant rumbles (f0 at 10-25Hz, 2nd harmonic stronger than fundamental) where generic ML tools fail. Classical signal processing pipeline: STFT at n_fft=8192 → HPSS → subharmonic summation → time-varying comb mask → noisereduce residual gate. No ML training needed or appropriate with 44 recordings in 24 hours.

## Key Findings

**Stack:** librosa 0.11.0 + scipy ShortTimeFFT + noisereduce 3.0.3 + soundfile (Python); FastAPI 0.115+ with BackgroundTasks (API); React 18 + Vite + wavesurfer.js 7.x (frontend). n_fft must be 8192+; librosa.load must use sr=None; use scipy ShortTimeFFT not legacy spectrogram().

**Table Stakes:** Harmonic comb masking + f0 detection, before/after spectrogram with mask overlay, A/B audio toggle, batch processing all 212 calls, WAV export at native sr (Raven Pro compatible).

**Differentiators:** LALAL.AI side-by-side comparison, per-call confidence scoring, noise type classifier, three-panel spectrogram overlay (noisy/mask/cleaned), n_fft=8192 as talking point.

**Anti-Features (skip):** Multi-elephant source separation (PhD-level problem), real-time streaming, ML model training.

**Architecture:** Linear context-dict stage pipeline (compute_stft → apply_hpss → detect_f0_shs → build_comb_mask → apply_spectral_gate → reconstruct_audio), each stage a pure function. pipeline/ decoupled from api/. In-memory job registry (no Redis/Celery). Server-side spectrogram PNG generation. Poll-based job status (2s interval, not WebSockets).

**Watch Out For:**
1. n_fft=2048 destroys infrasonic resolution — set 8192 globally, assert sr/n_fft < 6Hz at startup
2. librosa silent resampling — always sr=None, assert sr >= 44100
3. SHS octave error from 2nd-harmonic dominance — add octave-check heuristic, validate on 5 known calls
4. Generic noisereduce before HPSS corrupts harmonic structure — always run HPSS first
5. Synchronous FastAPI processing times out React — BackgroundTasks from day one

## Suggested Phase Structure (Coarse — 5 phases)

1. **Pipeline Foundation** — STFT config, ingestor, annotation parser, audio loading validation
2. **Harmonic Detection & Comb Masking** — HPSS, SHS f0 detection, comb mask, residual cleanup, listening test on 5 calls
3. **Batch Pipeline & API Layer** — Scale to 212 calls, confidence scoring, FastAPI with BackgroundTasks, CORS
4. **React Frontend & Demo** — Spectrogram viz, A/B toggle, LALAL.AI comparison, confidence dashboard
5. **Validation & Demo Prep** — Full batch run, demo rehearsal, stretch features if time

## Confidence Assessment

| Area | Level | Notes |
|------|-------|-------|
| Stack | HIGH | All libraries verified against official docs |
| Features | MEDIUM | Judge priorities inferred, not HackSMU-specific |
| Architecture | HIGH | Established patterns matching real bioacoustic pipelines |
| Pitfalls | MEDIUM-HIGH | DSP fundamentals HIGH; elephant-specific SHS octave error MEDIUM |

## Open Questions

- Annotations CSV exact format (column names, timestamp format)
- Actual sample rates in 44 recordings (assumed 44100Hz, could be 48/96kHz)
- f0 range validation on actual recordings (literature: 10-25Hz)
- LALAL.AI upload limits and processing time — must verify before hackathon

---
*Synthesized: 2026-04-11 from STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md*
