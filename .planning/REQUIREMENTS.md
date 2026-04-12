# Requirements: v1.1 Real-Data Validation & Pitch Polish

**Defined:** 2026-04-12
**Core Value:** Validate the shipped v1.0 pipeline on real ElephantVoices recordings and deliver polished pitch artifacts ready for judges.

## v1.1 Requirements

### Real-Data Validation

- [ ] **REAL-01**: Run `scripts/batch_process.py` on at least 3 real ElephantVoices WAV recordings and verify pipeline completes without errors
- [ ] **REAL-02**: Generate per-noise-type publication figures from real recordings (not synthetic) — generator, car, plane
- [ ] **REAL-03**: Empirically tune SHS octave-check threshold (currently 0.7) against annotated ground-truth f0 values
- [ ] **REAL-04**: Verify f0 detection returns values in 8-25Hz range on real calls (listening test + spectrogram inspection)
- [ ] **REAL-05**: Document any deviations between synthetic and real performance in a VALIDATION-REPORT.md

### Pitch Artifacts

- [ ] **PITCH-01**: Write top-level README.md with project overview, quickstart, architecture diagram, and pitch talking points
- [ ] **PITCH-02**: Generate 3-5 animated GIFs showing demo UI interaction (upload → process → result)
- [ ] **PITCH-03**: Write SLIDES.md with pitch narrative (problem → approach → demo → results) — markdown format judges can skim
- [ ] **PITCH-04**: Document the scientific moat in TALKING-POINTS.md (Zeppelzauer, NSSH, octave-check citations)

### Deployment Guide

- [ ] **DEPLOY-01**: Write DEPLOY.md with step-by-step instructions for running backend + frontend locally
- [ ] **DEPLOY-02**: Create `scripts/start_demo.sh` one-command launcher (backend + frontend in one terminal)
- [ ] **DEPLOY-03**: Verify clean checkout install works: clone → install → run → open browser — zero manual config

## Out of Scope

| Feature | Reason |
|---------|--------|
| Advanced bioacoustic features (call-type classification, clustering) | Post-hackathon research scope |
| Production hardening (auth, monitoring, logging) | Local demo only |
| Mobile / field app | Web demo sufficient for judges |
| Real-time streaming | Research workflow, not real-time |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REAL-01 | Phase 10 | Pending |
| REAL-02 | Phase 10 | Pending |
| REAL-03 | Phase 10 | Pending |
| REAL-04 | Phase 10 | Pending |
| REAL-05 | Phase 10 | Pending |
| PITCH-01 | Phase 11 | Pending |
| PITCH-02 | Phase 11 | Pending |
| PITCH-03 | Phase 11 | Pending |
| PITCH-04 | Phase 11 | Pending |
| DEPLOY-01 | Phase 12 | Pending |
| DEPLOY-02 | Phase 12 | Pending |
| DEPLOY-03 | Phase 12 | Pending |

**Coverage:**
- v1.1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-12*
