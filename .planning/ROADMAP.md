# Roadmap: ElephantVoices Denoiser

## Milestones

- ✅ **v1.0 ElephantVoices Denoiser** — Phases 1-9 (shipped 2026-04-12) — [archive](milestones/v1.0-ROADMAP.md)
- 🚧 **v1.1 Real-Data Validation & Pitch Polish** — Phases 10-12 (in progress)

## v1.1 Phase Details

### Phase 10: Real-Data Validation
**Goal**: Run the shipped v1.0 pipeline on real ElephantVoices field recordings, tune f0 detection thresholds empirically, and document any deviations from synthetic performance
**Depends on**: v1.0 complete
**Requirements**: REAL-01, REAL-02, REAL-03, REAL-04, REAL-05
**Success Criteria**:
  1. `batch_process.py` runs on at least 3 real recordings without errors
  2. 3 publication figures generated from real calls (one per noise type)
  3. Octave-check threshold tuned (value justified with evidence)
  4. f0 detection verified in 8-25Hz range on real calls
  5. `.planning/v1.1-VALIDATION-REPORT.md` documents synthetic-vs-real deltas
**Plans**: TBD

### Phase 11: Pitch Artifacts
**Goal**: Produce pitch-ready documentation — README, slides, talking points, and animated GIFs — that a judge can skim and understand the project in under 2 minutes
**Depends on**: Phase 10
**Requirements**: PITCH-01, PITCH-02, PITCH-03, PITCH-04
**Success Criteria**:
  1. Top-level README.md has overview, quickstart, architecture, pitch
  2. 3-5 animated GIFs in `docs/gifs/` show demo interactions
  3. `docs/SLIDES.md` contains pitch narrative
  4. `docs/TALKING-POINTS.md` cites Zeppelzauer + NSSH + octave-check
**Plans**: TBD

### Phase 12: Deployment Guide
**Goal**: Zero-friction local deploy — judge clones, runs one command, opens browser, sees demo working
**Depends on**: Phase 11
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03
**Success Criteria**:
  1. `DEPLOY.md` has step-by-step backend + frontend run instructions
  2. `scripts/start_demo.sh` launches both servers in one terminal
  3. Clean checkout → install → run → browser works without manual config
**Plans**: TBD

## Phases

<details>
<summary>✅ v1.0 ElephantVoices Denoiser (Phases 1-9) — SHIPPED 2026-04-12</summary>

- [x] Phase 1: Pipeline Foundation (3/3 plans) — completed 2026-04-11
- [x] Phase 2: Harmonic Detection & Denoising (2/2 plans) — completed 2026-04-12
- [x] Phase 3: Demo Spectrograms & Measurements (1/1 plan) — completed 2026-04-12
- [x] Phase 4: Batch Processing & API (4/4 plans) — completed 2026-04-12
- [x] Phase 5: React Frontend & Demo (4/4 plans) — completed 2026-04-12
- [x] Phase 6: Multi-Speaker Separation (2/2 plans) — completed 2026-04-12
- [x] Phase 7: Demo Audio & Proxy Fixes (1/1 plan) — completed 2026-04-12 [gap closure]
- [x] Phase 8: Frontend Component Integration (1/1 plan) — completed 2026-04-12 [gap closure]
- [x] Phase 9: Polish Remaining Gaps (1/1 plan) — completed 2026-04-12 [gap closure]

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Pipeline Foundation | v1.0 | 3/3 | Complete | 2026-04-11 |
| 2. Harmonic Detection & Denoising | v1.0 | 2/2 | Complete | 2026-04-12 |
| 3. Demo Spectrograms & Measurements | v1.0 | 1/1 | Complete | 2026-04-12 |
| 4. Batch Processing & API | v1.0 | 4/4 | Complete | 2026-04-12 |
| 5. React Frontend & Demo | v1.0 | 4/4 | Complete | 2026-04-12 |
| 6. Multi-Speaker Separation | v1.0 | 2/2 | Complete | 2026-04-12 |
| 7. Demo Audio & Proxy Fixes | v1.0 | 1/1 | Complete | 2026-04-12 |
| 8. Frontend Component Integration | v1.0 | 1/1 | Complete | 2026-04-12 |
| 9. Polish Remaining Gaps | v1.0 | 1/1 | Complete | 2026-04-12 |
| 10. Real-Data Validation | v1.1 | 1/1 | Complete | 2026-04-12 |
| 11. Pitch Artifacts | v1.1 | 1/1 | Complete | 2026-04-12 |
| 12. Deployment Guide | v1.1 | 1/1 | Complete | 2026-04-12 |
