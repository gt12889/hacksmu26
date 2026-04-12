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

- [x] **HARM-01**: System applies HPSS with tuned kernel to separate harmonic elephant content from transient noise
- [x] **HARM-02**: System applies median filtering along time axis to enhance horizontal harmonic contours (Zeppelzauer method)
- [x] **HARM-03**: System detects f0 via subharmonic summation sweeping 8-25Hz, summing power at integer multiples up to 1000Hz
- [x] **HARM-04**: System includes octave-check heuristic to prevent 2f0 misdetection as fundamental
- [x] **HARM-05**: System builds time-varying harmonic comb mask at integer multiples of detected f0 (±5Hz bandwidth)
- [x] **HARM-06**: System applies comb mask to magnitude spectrogram and reconstructs audio via ISTFT with original phase

### Noise Cleanup

- [x] **CLEAN-01**: System applies noisereduce non-stationary spectral gating on comb-masked output
- [x] **CLEAN-02**: System uses stationary noisereduce with noise profile for generator-type recordings
- [x] **CLEAN-03**: System selects cleanup strategy based on noise type classification

### Demo Spectrograms & Acoustic Measurements

- [ ] **DEMO-01**: Script processes one representative call per noise type (generator, car, plane) through full pipeline
- [ ] **DEMO-02**: Generates publication-quality before/after spectrogram figures (matplotlib, 300dpi) with labeled axes, colorbar, title per noise type
- [ ] **DEMO-03**: Overlays detected f0 contour on cleaned spectrogram as a traced line
- [ ] **DEMO-04**: Annotates harmonic spacing markers (f0, 2f0, 3f0...) on spectrogram with labeled arrows/lines
- [ ] **DEMO-05**: Displays SNR improvement (dB), call duration, and detected f0 range as text annotations on each figure
- [ ] **DEMO-06**: Generates side-by-side 3-panel figure per noise type: original | comb mask overlay | cleaned result
- [ ] **DEMO-07**: Exports cleaned WAV files alongside figures for audio playback during pitch

### Multi-Speaker Separation

- [ ] **MULTI-01**: System detects multiple f0 tracks when elephants vocalize simultaneously
- [ ] **MULTI-02**: System identifies crossing harmonics to distinguish different callers
- [ ] **MULTI-03**: System outputs separate cleaned WAV per detected caller
- [ ] **MULTI-04**: Generates multi-speaker spectrogram figure showing separated f0 tracks in different colors

## Out of Scope

| Feature | Reason |
|---------|--------|
| ML model training (U-Net, GAN) | Not feasible on 44 recordings in 24 hours |
| FastAPI / REST API | Pivot: judges want spectrograms, not a platform |
| React web frontend / dashboard | Pivot: notebook-style demo with publication figures is more impactful |
| Batch processing all 212 calls | 3 representative calls (one per noise type) is the right demo |
| Confidence dashboard / sorting | Overbuilt for a hackathon pitch |
| LALAL.AI comparison panel | Can mention verbally; not worth building UI for |
| Raven Pro export | Nice-to-have but not demo-critical |
| Real-time field deployment | Hackathon demo only |
| Cloud deployment / multi-tenancy | Local demo for hackathon |

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
| HARM-01 | Phase 2 | Complete |
| HARM-02 | Phase 2 | Complete |
| HARM-03 | Phase 2 | Complete |
| HARM-04 | Phase 2 | Complete |
| HARM-05 | Phase 2 | Complete |
| HARM-06 | Phase 2 | Complete |
| CLEAN-01 | Phase 2 | Complete |
| CLEAN-02 | Phase 2 | Complete |
| CLEAN-03 | Phase 2 | Complete |
| DEMO-01 | Phase 3 | Pending |
| DEMO-02 | Phase 3 | Pending |
| DEMO-03 | Phase 3 | Pending |
| DEMO-04 | Phase 3 | Pending |
| DEMO-05 | Phase 3 | Pending |
| DEMO-06 | Phase 3 | Pending |
| DEMO-07 | Phase 3 | Pending |
| MULTI-01 | Phase 4 | Pending |
| MULTI-02 | Phase 4 | Pending |
| MULTI-03 | Phase 4 | Pending |
| MULTI-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-11*
*Last updated: 2026-04-11 after pivot to focused demo direction*
