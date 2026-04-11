# Roadmap: ElephantVoices Denoiser

## Overview

Four phases from raw field recordings to judge-ready demo. Phase 1 builds the validated data ingestion and spectral analysis foundation. Phase 2 implements the core differentiator — harmonic comb masking — and proves it works on real calls. Phase 3 scales to all 212 calls and wraps the pipeline in a FastAPI layer. Phase 4 delivers the React frontend that makes the science visible to judges.

## Phases

- [ ] **Phase 1: Pipeline Foundation** - Ingest, segment, and compute high-res spectrograms from field recordings
- [ ] **Phase 2: Harmonic Detection & Denoising** - Detect elephant f0, build comb mask, apply residual cleanup — proven on real calls
- [ ] **Phase 3: Batch Processing & API** - Scale to all 212 calls with confidence scoring and FastAPI layer
- [ ] **Phase 4: React Frontend & Demo** - Spectrogram visualization, A/B audio toggle, LALAL.AI comparison, confidence dashboard

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
- [ ] 01-02-PLAN.md — Spectrogram + noise classifier (STFT with phase preservation, spectral flatness classification)
- [ ] 01-03-PLAN.md — CLI entrypoint + pytest test suite (scripts/ingest.py, tests/test_pipeline.py)

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

### Phase 3: Batch Processing & API
**Goal**: All 212 calls are processed through the full pipeline in one command, with per-call confidence scores and Raven Pro exports, served via a FastAPI layer that accepts uploads and returns results asynchronously
**Depends on**: Phase 2
**Requirements**: BATCH-01, BATCH-02, BATCH-03, BATCH-04, BATCH-05, API-01, API-02, API-03, API-04, API-05, API-06
**Success Criteria** (what must be TRUE):
  1. A single batch command processes all 212 calls without crashing or requiring intervention, outputting 212 cleaned WAVs at native sample rate
  2. The summary CSV contains one row per call with filename, f0, SNR_before, SNR_after, confidence score (0-100%), and noise type
  3. Raven Pro selection table (.txt) is exported alongside cleaned WAVs and can be loaded in Raven Pro without errors
  4. POST /api/upload → POST /api/process → GET /api/status/{job_id} → GET /api/result/{job_id} completes end-to-end without blocking the server — processing happens in BackgroundTasks
  5. GET /api/batch/summary returns aggregate metrics across all 212 processed calls
**Plans**: TBD

### Phase 4: React Frontend & Demo
**Goal**: Judges can use the web demo to see before/after spectrograms with the harmonic comb mask overlay, toggle A/B audio, compare against LALAL.AI, and browse confidence scores across all 212 calls
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05
**Success Criteria** (what must be TRUE):
  1. The spectrogram panel shows the noisy input and cleaned output side-by-side with the harmonic comb mask rendered in a distinct color as an overlay
  2. The A/B audio toggle switches playback between noisy and cleaned audio at the same timestamp with a single button click
  3. The three-panel comparison (Original | LALAL.AI | Our result) shows SNR metrics beneath each panel — demonstrating our domain-specific advantage
  4. The confidence dashboard table is sortable and filterable; clicking any row loads that call's spectrogram and audio into the main view
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Pipeline Foundation | 1/3 | In Progress|  |
| 2. Harmonic Detection & Denoising | 0/TBD | Not started | - |
| 3. Batch Processing & API | 0/TBD | Not started | - |
| 4. React Frontend & Demo | 0/TBD | Not started | - |
