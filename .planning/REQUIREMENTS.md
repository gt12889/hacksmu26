# Requirements: ElephantVoices Denoiser

**Defined:** 2026-04-11
**Core Value:** Denoise elephant vocalizations by exploiting their harmonic integer-multiple structure

## v1 Requirements

### Data Ingestion

- [x] **INGEST-01**: System parses annotation spreadsheet (CSV/Excel) to extract call timestamps, filenames, and noise type
- [x] **INGEST-02**: System loads audio files at native sample rate (sr=None) without silent resampling
- [x] **INGEST-03**: System segments recordings into individual call clips with configurable padding (default 2s)
- [x] **INGEST-04**: System extracts noise-only segments from gaps between calls for noise profiling
- [x] **INGEST-05**: System asserts sr/n_fft < 6Hz at startup to prevent silent resolution failures

### Spectral Analysis

- [x] **SPEC-01**: System computes STFT with n_fft=8192+ for infrasonic frequency resolution (~5.4Hz/bin at 44.1kHz)
- [x] **SPEC-02**: System preserves original phase for artifact-free reconstruction via ISTFT
- [x] **SPEC-03**: System classifies noise type per recording (generator/car/plane/mixed) using spectral flatness

### Harmonic Processing

- [ ] **HARM-01**: System applies HPSS with tuned kernel to separate harmonic elephant content from transient noise
- [ ] **HARM-02**: System applies median filtering along time axis to enhance horizontal harmonic contours (Zeppelzauer method)
- [ ] **HARM-03**: System detects f0 via subharmonic summation sweeping 8-25Hz, summing power at integer multiples up to 1000Hz
- [ ] **HARM-04**: System includes octave-check heuristic to prevent 2f0 misdetection as fundamental
- [ ] **HARM-05**: System builds time-varying harmonic comb mask at integer multiples of detected f0 (±5Hz bandwidth)
- [ ] **HARM-06**: System applies comb mask to magnitude spectrogram and reconstructs audio via ISTFT with original phase

### Noise Cleanup

- [ ] **CLEAN-01**: System applies noisereduce non-stationary spectral gating on comb-masked output
- [ ] **CLEAN-02**: System uses stationary noisereduce with noise profile for generator-type recordings
- [ ] **CLEAN-03**: System selects cleanup strategy based on noise type classification

### Batch Processing

- [ ] **BATCH-01**: System processes all 212 calls through full pipeline without manual intervention
- [ ] **BATCH-02**: System computes per-call confidence score (0-100%) based on: harmonics survived, SNR improvement, harmonic integrity
- [ ] **BATCH-03**: System exports each cleaned call as standalone WAV at native sample rate
- [ ] **BATCH-04**: System generates summary CSV with metrics per call (filename, f0, SNR_before, SNR_after, confidence, noise_type)
- [ ] **BATCH-05**: System exports in Raven Pro compatible format (WAV + selection table .txt)

### Web API

- [ ] **API-01**: POST /api/upload accepts audio file and stores it
- [ ] **API-02**: POST /api/process triggers pipeline on uploaded file, returns job ID
- [ ] **API-03**: GET /api/status/{job_id} returns processing status and progress
- [ ] **API-04**: GET /api/result/{job_id} returns cleaned audio + spectrogram data
- [ ] **API-05**: GET /api/batch/summary returns batch processing summary
- [ ] **API-06**: API uses BackgroundTasks for async processing (no synchronous blocking)

### Web Frontend

- [ ] **UI-01**: Before/after spectrogram display with harmonic comb mask overlay in distinct color
- [ ] **UI-02**: Audio playback with A/B toggle between noisy and cleaned at same timestamp
- [ ] **UI-03**: Side-by-side comparison panel: Original | LALAL.AI | Our result with SNR metrics
- [ ] **UI-04**: Confidence dashboard with sortable/filterable table of all processed calls
- [ ] **UI-05**: Click any row in dashboard to view spectrogram and play audio

## v2 Requirements (Stretch)

### Multi-Speaker Separation

- **MULTI-01**: System detects multiple f0 tracks when elephants vocalize simultaneously
- **MULTI-02**: System identifies crossing harmonics to distinguish different callers
- **MULTI-03**: System outputs separate cleaned WAV per detected caller

## Out of Scope

| Feature | Reason |
|---------|--------|
| ML model training (U-Net, GAN) | Not feasible on 44 recordings in 24 hours |
| Real-time field deployment | Hackathon demo only, not production system |
| Mobile app | Web demo sufficient for judges |
| Cloud deployment / multi-tenancy | Local demo for hackathon |
| Real-time streaming processing | Wrong use case for research workflow |
| Automated recording acquisition | Data already in hand |
| WebSocket-based job updates | Poll-based is 2hrs faster to build, works fine |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 1 | Complete |
| INGEST-02 | Phase 1 | Complete |
| INGEST-03 | Phase 1 | Complete |
| INGEST-04 | Phase 1 | Complete |
| INGEST-05 | Phase 1 | Complete |
| SPEC-01 | Phase 1 | Complete |
| SPEC-02 | Phase 1 | Complete |
| SPEC-03 | Phase 1 | Complete |
| HARM-01 | Phase 2 | Pending |
| HARM-02 | Phase 2 | Pending |
| HARM-03 | Phase 2 | Pending |
| HARM-04 | Phase 2 | Pending |
| HARM-05 | Phase 2 | Pending |
| HARM-06 | Phase 2 | Pending |
| CLEAN-01 | Phase 2 | Pending |
| CLEAN-02 | Phase 2 | Pending |
| CLEAN-03 | Phase 2 | Pending |
| BATCH-01 | Phase 3 | Pending |
| BATCH-02 | Phase 3 | Pending |
| BATCH-03 | Phase 3 | Pending |
| BATCH-04 | Phase 3 | Pending |
| BATCH-05 | Phase 3 | Pending |
| API-01 | Phase 3 | Pending |
| API-02 | Phase 3 | Pending |
| API-03 | Phase 3 | Pending |
| API-04 | Phase 3 | Pending |
| API-05 | Phase 3 | Pending |
| API-06 | Phase 3 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| UI-04 | Phase 4 | Pending |
| UI-05 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-11*
*Last updated: 2026-04-11 after initial definition*
