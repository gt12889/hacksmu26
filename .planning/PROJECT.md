# ElephantVoices Denoiser

## What This Is

A domain-specific audio denoising system for ElephantVoices that extracts elephant vocalizations from field recordings contaminated by mechanical noise (generators, cars, planes). Shipped v1.0 at HackSMU 2026 as a complete Python DSP pipeline + FastAPI backend + React web demo, with publication-quality spectrograms, confidence scoring, and multi-speaker separation.

## Current State

**Shipped:** v1.0 (2026-04-12) — 9 phases, 19 plans, 174 tests passing, ~3400 LOC Python + ~1200 LOC TypeScript

## Current Milestone: v1.1 Real-Data Validation & Pitch Polish

**Goal:** Validate the v1.0 pipeline on actual ElephantVoices field recordings and produce polished pitch artifacts ready for judge presentation.

**Target features:**
- End-to-end run on real recordings (not just synthetic)
- Empirical tuning of f0 detection thresholds
- Pitch deck / slides with before/after spectrograms
- README with GIFs and quickstart
- Demo rehearsal script
- Deployment guide for judges to run locally

## Core Value

Denoise elephant vocalizations by exploiting their harmonic integer-multiple structure — the one technique that separates us from generic AI denoising tools that fail on infrasonic bioacoustics.

## Requirements

### Validated

- ✓ Parse spreadsheet timestamps and auto-segment calls — v1.0
- ✓ Classify noise type per recording (generator, car, plane) — v1.0
- ✓ Compute high-resolution spectrograms with n_fft=8192+ — v1.0
- ✓ Preserve phase for artifact-free ISTFT reconstruction — v1.0
- ✓ HPSS with Zeppelzauer spectro-temporal enhancement — v1.0
- ✓ Subharmonic summation f0 detection with octave-check — v1.0
- ✓ Time-varying harmonic comb masking — v1.0
- ✓ noisereduce residual cleanup (stationary/non-stationary modes) — v1.0
- ✓ Publication-quality before/after spectrograms (f0 contour, harmonic markers, SNR) — v1.0
- ✓ Cleaned WAV export (PCM_16, Raven Pro compatible) — v1.0
- ✓ Batch processing with per-call confidence scoring — v1.0
- ✓ FastAPI backend (upload, process, status, result, batch, demo endpoints) — v1.0
- ✓ React web demo (upload flow + confidence dashboard + static demo cards) — v1.0
- ✓ Multi-speaker separation (top-K SHS + track linking) — v1.0

### Active

- [ ] Run full pipeline on real ElephantVoices field recordings
- [ ] Tune f0 detection octave-check threshold on real data
- [ ] Generate before/after figures from real calls for pitch deck
- [ ] Write README with quickstart, GIFs, and deployment guide
- [ ] Prepare demo rehearsal script and pitch talking points

### Out of Scope

- ML model training (U-Net, GAN) — not feasible on 44 recordings in 24 hours, and classical DSP outperforms on infrasonic content
- Real-time field deployment or mobile app — research workflow tool, not production
- Cloud deployment or multi-tenancy — local demo only

## Context

- **Domain:** Elephant bioacoustics. Rumbles have fundamentals at 10-20Hz with harmonics up to 1000Hz. The 2nd harmonic is significantly stronger than the fundamental.
- **Key challenge:** Engine noise fundamental (~30Hz) with 2nd harmonic at 60Hz directly overlaps elephant rumble fundamentals. Generic tools trained on speech/music frequencies fail on infrasonic content.
- **Scientific basis:** Zeppelzauer spectro-temporal enhancement, NSSH (normalized subharmonic summation from cetacean research — 30% more precision/recall than spectrogram cross-correlation at low SNR)
- **Data:** 44 field recordings, 212 annotated calls with timestamps
- **Shipped v1.0:** Full stack (Python DSP → FastAPI → React) with 174 tests passing
- **Pitch angle:** "We don't just remove noise. We exploit the mathematical structure of elephant vocalizations to surgically extract calls even when they share the exact same frequency band as the noise."

## Constraints

- **Timeline:** 24 hours (HackSMU hackathon — shipped ✓)
- **Team:** 2-3 people working in parallel
- **Tech stack:** Python (librosa, noisereduce, scipy, numpy, pandas, matplotlib) + FastAPI + React (Vite + TypeScript) + wavesurfer.js
- **FFT resolution:** Must use n_fft=8192+ (most teams use 1024 → garbage below 50Hz)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Harmonic comb masking over generic ML | Exploits domain-specific structure, no training data needed, works in 24hrs | ✓ Good — validated in v1.0 |
| Subharmonic summation for f0 detection | 2nd harmonic stronger than fundamental; detecting f0 from harmonics is more robust | ✓ Good — octave-check works |
| n_fft=8192 over default 1024 | Need ~5Hz frequency resolution for infrasonic fundamentals at 10-20Hz | ✓ Good — hard constraint enforced |
| Python + FastAPI + React | Team familiarity, rich DSP ecosystem (librosa), fast web demo | ✓ Good — shipped end-to-end |
| LALAL.AI as baseline, not primary tool | Trained on speech/music, fails on infrasonic; useful as comparison foil | ✓ Good — pitch talking point |
| Multi-speaker separation promoted to v1 | Directly addresses ElephantVoices' hardest unsolved problem | ✓ Good — validated on synthetic 14+18Hz |
| Gap closure phases 7-9 after first audit | Re-audit caught wiring gaps (Vite proxy, orphaned components, missing exports) | ✓ Good — 100% requirements coverage |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition**:
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions

**After each milestone**:
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-12 — v1.1 milestone started (Real-Data Validation & Pitch Polish)*
