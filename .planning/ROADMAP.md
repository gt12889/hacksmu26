# Roadmap: ElephantVoices Denoiser

## Overview

Four phases from raw field recordings to judge-ready demo. Phase 1 builds the validated data ingestion and spectral analysis foundation. Phase 2 implements the core differentiator — harmonic comb masking — and proves it works on real calls. Phase 3 generates publication-quality before/after spectrograms with acoustic measurements for the pitch. Phase 4 tackles multi-speaker separation for overlapping elephant calls.

## Phases

- [x] **Phase 1: Pipeline Foundation** - Ingest, segment, and compute high-res spectrograms from field recordings (completed 2026-04-11)
- [ ] **Phase 2: Harmonic Detection & Denoising** - Detect elephant f0, build comb mask, apply residual cleanup — proven on real calls
- [ ] **Phase 3: Demo Spectrograms & Measurements** - Publication-quality before/after figures with f0 contours, harmonic markers, and SNR annotations for pitch
- [ ] **Phase 4: Multi-Speaker Separation** - Detect and separate overlapping elephant calls using crossing harmonic analysis

## Phase Details

### Phase 1: Pipeline Foundation
**Goal**: The system can ingest the 44 field recordings and 212 annotated calls, segment them into individual clips, and compute infrasonic-resolution spectrograms ready for processing
**Depends on**: Nothing (first phase)
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, SPEC-01, SPEC-02, SPEC-03
**Success Criteria** (what must be TRUE):
  1. Running the ingestor on the annotation spreadsheet produces 212 audio clips segmented to ±2s padding, with no manual intervention
  2. Each clip's spectrogram has frequency resolution below 6Hz/bin (n_fft=8192+ confirmed), with infrasonic content visible at 10-25Hz
  3. The startup assertion fires and rejects any configuration where sr/n_fft >= 6Hz — catching misconfiguration before silent failures
  4. Each recording is classified as generator, car, plane, or mixed based on spectral flatness
  5. Phase information is preserved for artifact-free reconstruction via ISTFT
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Config module + ingestor (DSP constants, annotation parser, call segmentation, noise gap extraction)
- [x] 01-02-PLAN.md — Spectrogram + noise classifier (STFT with phase preservation, spectral flatness classification)
- [x] 01-03-PLAN.md — CLI entrypoint + pytest test suite (scripts/ingest.py, tests/test_pipeline.py)

### Phase 2: Harmonic Detection & Denoising
**Goal**: The system detects elephant f0 via subharmonic summation and applies a time-varying harmonic comb mask to extract clean vocalizations — demonstrated to work on at least 5 known calls
**Depends on**: Phase 1
**Requirements**: HARM-01, HARM-02, HARM-03, HARM-04, HARM-05, HARM-06, CLEAN-01, CLEAN-02, CLEAN-03
**Success Criteria** (what must be TRUE):
  1. On 5 manually verified calls, f0 detection outputs values in the 8-25Hz range and the octave-check heuristic prevents 2f0 from being reported as f0
  2. The harmonic comb mask visibly preserves elephant harmonic contours in the cleaned spectrogram while attenuating noise between harmonics
  3. Cleaned audio output is audibly cleaner than the input (rumble present, mechanical noise reduced) on a listening test
  4. Noise cleanup strategy differs between generator recordings (stationary profile) and car/plane recordings (non-stationary), and selection is automatic
**Plans**: TBD

### Phase 3: Demo Spectrograms & Measurements
**Goal**: One representative call per noise type (generator, car, plane) is processed through the full pipeline and presented as publication-quality before/after spectrograms with f0 contour overlays, harmonic spacing markers, SNR annotations, and exported cleaned audio — ready to show judges
**Depends on**: Phase 2
**Requirements**: DEMO-01, DEMO-02, DEMO-03, DEMO-04, DEMO-05, DEMO-06, DEMO-07
**Success Criteria** (what must be TRUE):
  1. Running the demo script produces 3 sets of figures (one per noise type) with no manual intervention
  2. Each figure shows before/after spectrograms side-by-side with the comb mask as a visible overlay panel
  3. f0 contour is traced as a line on the cleaned spectrogram, with harmonic multiples (2f0, 3f0...) marked
  4. SNR improvement (dB), call duration, and f0 range are annotated as text on each figure
  5. Three cleaned WAV files are exported alongside the figures for audio playback during pitch
**Plans**: TBD

### Phase 4: Multi-Speaker Separation
**Goal**: When multiple elephants vocalize simultaneously, the system detects separate f0 tracks, identifies crossing harmonics, and outputs individual cleaned tracks per caller — demonstrated on at least one overlapping call
**Depends on**: Phase 2
**Requirements**: MULTI-01, MULTI-02, MULTI-03, MULTI-04
**Success Criteria** (what must be TRUE):
  1. On a recording with known overlapping calls, the system detects 2+ distinct f0 tracks
  2. Crossing harmonics are correctly identified (harmonics from different callers cross; same-caller harmonics never cross)
  3. Separate cleaned WAV files are exported per detected caller
  4. A multi-speaker spectrogram figure shows separated f0 tracks in different colors
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Pipeline Foundation | 3/3 | Complete | 2026-04-11 |
| 2. Harmonic Detection & Denoising | 0/TBD | Not started | - |
| 3. Demo Spectrograms & Measurements | 0/TBD | Not started | - |
| 4. Multi-Speaker Separation | 0/TBD | Not started | - |
