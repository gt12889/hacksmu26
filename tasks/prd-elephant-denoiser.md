# PRD: ElephantVoices Vocalization Denoiser

## Introduction

ElephantVoices has 44 field recordings containing 212 elephant vocalization calls contaminated by mechanical noise (generators, cars, planes). Elephant rumbles occupy the infrasonic range (10-20Hz fundamentals, harmonics up to 1000Hz) which directly overlaps with engine noise (~30Hz fundamental). Generic AI denoising tools (LALAL.AI, media.io) are trained on speech/music frequencies and fail on infrasonic bioacoustics.

Our approach exploits the strict harmonic structure of elephant vocalizations — their calls produce energy at exact integer multiples of a fundamental frequency — to surgically extract calls even when they share the exact same frequency band as the noise. This is backed by peer-reviewed methods: Zeppelzauer spectro-temporal enhancement, normalized subharmonic summation (NSSH), and the critical domain insight that the 2nd harmonic is stronger than the fundamental.

## Goals

- Denoise all 212 elephant calls across 44 recordings with measurable SNR improvement
- Produce per-call confidence scores (0-100%) for research prioritization
- Batch-export cleaned calls as standalone clips compatible with Raven Pro
- Separate overlapping multi-elephant calls into individual caller tracks
- Deliver a web demo with real-time spectrogram visualization for judges
- Demonstrate superiority over generic AI tools with side-by-side comparison

## User Stories

### US-001: Project Scaffolding and Dependencies
**Description:** As a developer, I need the project structure and all dependencies installed so the team can start building in parallel.

**Acceptance Criteria:**
- [ ] Python project with dependencies: librosa, noisereduce, scipy, numpy, pandas, matplotlib, fastapi, uvicorn
- [ ] React app in frontend/ with Vite + TypeScript
- [ ] Directory structure: pipeline/, api/, frontend/, data/, output/
- [ ] README.md with setup instructions

### US-002: Spreadsheet Parser and Call Segmenter
**Description:** As a researcher, I want the system to parse call timestamps and auto-segment recordings into individual call clips.

**Acceptance Criteria:**
- [ ] Reads CSV/Excel spreadsheet with filename, start, end, call_type columns
- [ ] Loads audio with librosa (sr=None to preserve original sample rate)
- [ ] Extracts call segments with configurable padding (default 2s)
- [ ] Extracts noise-only segments from gaps between calls
- [ ] Outputs segment metadata as JSON
- [ ] Handles all 44 recordings / 212 calls

### US-003: Noise Type Classifier
**Description:** As a pipeline developer, I need to classify noise type from non-call segments to adapt the denoising strategy.

**Acceptance Criteria:**
- [ ] Computes spectral flatness for broadband vs tonal discrimination
- [ ] Categories: generator (constant tonal), car (transient), plane (slow-sweep), mixed
- [ ] Detects generator fundamental ~30Hz with harmonics
- [ ] Returns noise profile dict with type, flatness, fundamentals, power spectrum

### US-004: Large-Window STFT Computation
**Description:** As a pipeline developer, I need n_fft=8192+ spectrograms for infrasonic frequency resolution.

**Acceptance Criteria:**
- [ ] STFT with n_fft=8192 or 16384
- [ ] Frequency resolution ≤ 10Hz per bin (sr/n_fft check)
- [ ] Returns magnitude spectrogram + phase for reconstruction
- [ ] Saves visualization-ready spectrogram PNGs

### US-005: Harmonic-Percussive Source Separation
**Description:** As a pipeline developer, I need HPSS with Zeppelzauer spectro-temporal enhancement to separate harmonic elephant content from transient noise.

**Acceptance Criteria:**
- [ ] librosa HPSS with tuned kernel_size for infrasonic content
- [ ] Median filtering along time axis enhances horizontal harmonic contours
- [ ] Returns enhanced harmonic spectrogram
- [ ] Before/after comparison saved as PNG

### US-006: Subharmonic Summation for f0 Detection
**Description:** As a pipeline developer, I need to detect elephant call f0 by exploiting the fact that higher harmonics (especially 2nd) are stronger than the fundamental.

**Acceptance Criteria:**
- [ ] Sweeps f0 candidates 8-25Hz
- [ ] Sums power at 2f0, 3f0, 4f0... up to 1000Hz per candidate
- [ ] NSSH normalization by number of harmonics summed
- [ ] Detects f0 even when fundamental is completely masked
- [ ] Returns f0 per time frame with confidence

### US-007: Harmonic Comb Mask Builder
**Description:** As a pipeline developer, I need a binary mask at integer multiples of f0 that preserves only elephant harmonics.

**Acceptance Criteria:**
- [ ] Narrow bandpass filters at f0, 2f0, 3f0... up to 1000Hz (±5Hz bandwidth)
- [ ] Time-varying mask follows f0 modulation across frames
- [ ] Applies to magnitude spectrogram
- [ ] Reconstructs audio via istft with original phase
- [ ] Dramatic noise reduction audible in output

### US-008: Residual Noise Cleanup
**Description:** As a pipeline developer, I need spectral gating to clean remaining artifacts after comb masking.

**Acceptance Criteria:**
- [ ] noisereduce non-stationary mode for general cleanup
- [ ] Stationary mode with noise profile for generator recordings
- [ ] Strategy selection driven by noise classifier output
- [ ] Final output as WAV with measurable SNR improvement

### US-009: Batch Processing with Confidence Scoring
**Description:** As a researcher, I want all 212 calls processed with per-call confidence scores and Raven Pro compatibility.

**Acceptance Criteria:**
- [ ] Orchestrates full pipeline for all 212 calls
- [ ] Confidence score (0-100%): harmonics survived, SNR improvement, harmonic integrity
- [ ] Standalone WAV per cleaned call
- [ ] Summary CSV with all metrics
- [ ] Raven Pro compatible export (WAV + selection table)
- [ ] Completes in < 30 minutes total

### US-010: FastAPI Backend
**Description:** As a web user, I need API endpoints for upload, processing, and result retrieval.

**Acceptance Criteria:**
- [ ] POST /api/upload, POST /api/process, GET /api/status/{id}, GET /api/result/{id}
- [ ] GET /api/batch/summary for batch results
- [ ] CORS enabled for React frontend

### US-011: Spectrogram Visualization
**Description:** As a judge, I want animated before/after spectrograms with the harmonic comb mask overlaid.

**Acceptance Criteria:**
- [ ] Noisy input spectrogram on top, clean output on bottom
- [ ] Comb mask overlay in distinct color showing kept vs removed
- [ ] Responsive for projector/large screen demo

### US-012: Audio Playback with A/B Toggle
**Description:** As a judge, I want to hear before/after with an A/B toggle at the same timestamp.

**Acceptance Criteria:**
- [ ] Play/pause for original and cleaned
- [ ] A/B toggle switches at same playback position
- [ ] Waveform visualization synced with playback

### US-013: LALAL.AI Baseline Comparison
**Description:** As a presenter, I want side-by-side comparison vs generic AI tools.

**Acceptance Criteria:**
- [ ] Original | LALAL.AI | Ours side-by-side spectrograms
- [ ] SNR metrics for each
- [ ] Narrative explaining infrasonic failure of generic tools

### US-014: Multi-Elephant Speaker Separation (Stretch)
**Description:** As a researcher, I want overlapping calls separated into individual caller tracks.

**Acceptance Criteria:**
- [ ] Detects multiple f0 tracks
- [ ] Identifies crossing harmonics (different callers cross; same-caller never cross)
- [ ] Separate WAV output per detected caller
- [ ] Handles at least 2 simultaneous callers

### US-015: Confidence Dashboard
**Description:** As a researcher, I want a sortable/filterable dashboard of all 212 processed calls.

**Acceptance Criteria:**
- [ ] Table: filename, call#, f0, SNR_before, SNR_after, confidence, noise_type
- [ ] Sortable, filterable by confidence threshold and noise type
- [ ] Click row to view spectrogram and play audio
- [ ] Export filtered results as CSV

## Functional Requirements

- FR-1: Use n_fft=8192+ for all spectral analysis (infrasonic resolution)
- FR-2: Detect f0 via subharmonic summation, not direct fundamental detection
- FR-3: Build time-varying harmonic comb masks at integer multiples of detected f0
- FR-4: Classify noise type per recording and adapt strategy accordingly
- FR-5: Score each cleaned call with quantitative confidence metric
- FR-6: Export all outputs as standard WAV files compatible with Raven Pro
- FR-7: Process all 212 calls in batch mode without manual intervention
- FR-8: Serve results via FastAPI with CORS for React frontend consumption
- FR-9: Render spectrograms as interactive visualizations, not static images

## Non-Goals

- No ML model training (no U-Net, no GAN — not feasible on 44 recordings in 24hrs)
- No real-time field deployment or mobile app
- No automated recording acquisition (data already in hand)
- No modification of original recordings (output is always new files)
- No user authentication or multi-tenancy in the web app
- No cloud deployment (local demo only for hackathon)

## Technical Considerations

- **Python DSP stack:** librosa (STFT, HPSS, spectrogram), noisereduce (spectral gating), scipy (signal processing, filtering), numpy, pandas
- **Critical parameter:** n_fft=8192 at 44.1kHz gives ~5.4Hz resolution; n_fft=16384 gives ~2.7Hz
- **Domain insight:** 2nd harmonic > fundamental in elephant rumbles; engine noise f0 ~30Hz overlaps elephant f0
- **NSSH reference:** Sum power at integer multiples, normalize by harmonic count
- **Zeppelzauer method:** Median filter along time axis for spectro-temporal structure enhancement
- **API:** FastAPI + uvicorn, async processing with job queue
- **Frontend:** React + Vite + TypeScript, wavesurfer.js or custom canvas for spectrograms

## Success Metrics

- SNR improvement ≥ 10dB on generator recordings (easiest)
- SNR improvement ≥ 6dB on car/plane recordings (harder)
- Harmonic integrity: post-cleaning harmonics remain at integer ratios (< 2% deviation)
- All 212 calls processed with confidence scores
- Judge pitch framing: "We exploit mathematical structure, not generic ML"
- Side-by-side demonstrates clear superiority over LALAL.AI on infrasonic content

## Open Questions

- What is the sample rate of the recordings? (Affects n_fft choice)
- Exact format of the timestamp spreadsheet (columns, date format)?
- Are LALAL.AI results pre-generated or do we process live during demo?
- How many recordings have multiple simultaneous callers? (Scopes US-014 effort)

## Key Citations for Pitch

1. **Zeppelzauer et al.** — Spectro-temporal structure enhancement for elephant rumble detection under heavy noise
2. **NSSH (cetacean research)** — 30% more precision/recall than spectrogram cross-correlation at low SNR
3. **Harmonic dominance** — 2nd harmonic significantly stronger than fundamental in elephant rumbles
4. **Engine overlap** — Engine f0 ~30Hz with 2nd harmonic at 60Hz directly overlaps elephant fundamentals
