# ElephantVoices Denoiser

## What This Is

A domain-specific audio denoising system for ElephantVoices that extracts elephant vocalizations from field recordings contaminated by mechanical noise (generators, cars, planes). Built for HackSMU 2026, it exploits the strict harmonic structure of elephant rumbles to surgically isolate calls even when they share the exact same frequency band as the noise. Delivered as a Python pipeline + FastAPI + React web demo.

## Core Value

Denoise elephant vocalizations by exploiting their harmonic integer-multiple structure — the one technique that separates us from generic AI denoising tools that fail on infrasonic bioacoustics.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Parse spreadsheet timestamps and auto-segment 212 calls from 44 recordings
- [ ] Classify noise type per recording (generator, car, plane) to adapt strategy
- [ ] Compute high-resolution spectrograms with n_fft=8192+ for infrasonic frequency resolution
- [ ] Apply HPSS with Zeppelzauer spectro-temporal enhancement to separate harmonic content
- [ ] Detect elephant f0 via subharmonic summation (exploiting stronger 2nd harmonic)
- [ ] Build time-varying harmonic comb masks at integer multiples of detected f0
- [ ] Apply residual noise cleanup via noisereduce spectral gating
- [ ] Batch process all 212 calls with per-call confidence scoring (0-100%)
- [ ] Export cleaned calls as standalone WAVs compatible with Raven Pro
- [ ] Serve results via FastAPI with upload/process/result endpoints
- [ ] Visualize before/after spectrograms with harmonic comb mask overlay
- [ ] Audio playback with A/B toggle between noisy and cleaned versions
- [ ] Side-by-side comparison against LALAL.AI to demonstrate domain-specific advantage
- [ ] Separate overlapping multi-elephant calls into individual caller tracks (stretch)
- [ ] Dashboard with sortable/filterable confidence scores across all 212 calls

### Out of Scope

- ML model training (U-Net, GAN) — not feasible on 44 recordings in 24 hours
- Real-time field deployment or mobile app — hackathon demo only
- Cloud deployment or multi-tenancy — local demo for judges
- Automated recording acquisition — data already in hand
- Modification of original recordings — always output new files

## Context

- **Domain:** Elephant bioacoustics. Rumbles have fundamentals at 10-20Hz with harmonics up to 1000Hz. The 2nd harmonic is significantly stronger than the fundamental.
- **Key challenge:** Engine noise fundamental (~30Hz) with 2nd harmonic at 60Hz directly overlaps elephant rumble fundamentals. Generic tools trained on speech/music frequencies fail on infrasonic content.
- **Scientific basis:** Zeppelzauer spectro-temporal enhancement, NSSH (normalized subharmonic summation from cetacean research — 30% more precision/recall than spectrogram cross-correlation at low SNR)
- **Data:** 44 field recordings, 212 annotated calls with timestamps, noise types include generators (constant tonal), cars (transient), planes (slow-sweep)
- **Hackathon resources:** LALAL.AI and media.io available as baseline comparison tools
- **Pitch angle:** "We don't just remove noise. We exploit the mathematical structure of elephant vocalizations to surgically extract calls even when they share the exact same frequency band as the noise."

## Constraints

- **Timeline:** 24 hours (HackSMU hackathon)
- **Team:** 2-3 people working in parallel
- **Tech stack:** Python (librosa, noisereduce, scipy, numpy, pandas) + FastAPI + React (Vite + TypeScript)
- **FFT resolution:** Must use n_fft=8192+ (most teams use 1024 → garbage below 50Hz)
- **Data:** 44 recordings, 212 calls — pipeline must handle all without manual intervention

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Harmonic comb masking over generic ML | Exploits domain-specific structure, no training data needed, works in 24hrs | — Pending |
| Subharmonic summation for f0 detection | 2nd harmonic stronger than fundamental; detecting f0 from harmonics is more robust | — Pending |
| n_fft=8192 over default 1024 | Need ~5Hz frequency resolution for infrasonic fundamentals at 10-20Hz | — Pending |
| Python + FastAPI + React | Team familiarity, rich DSP ecosystem (librosa), fast web demo | — Pending |
| LALAL.AI as baseline, not primary tool | Trained on speech/music, fails on infrasonic; useful as comparison foil | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-11 after initialization*
