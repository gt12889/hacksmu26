# Pitch Talking Points — ElephantVoices Denoiser

**HackSMU 2026** | Duration: 3-5 minutes

## The One-Liner

> "We exploit the mathematical structure of elephant vocalizations — their strict integer-multiple harmonic series — to surgically extract calls even when they share the exact same frequency band as the noise."

## The Problem (30 seconds)

**Show slide:** Spectrogram of a real elephant recording with generator noise.

- Elephant rumbles: fundamental 10-25 Hz, harmonics up to ~1000 Hz
- The 2nd harmonic is *stronger* than the fundamental (counter-intuitive but well-documented)
- **Engine noise fundamental = ~30 Hz**, 2nd harmonic at 60 Hz
- **→ Engine harmonics sit directly on top of elephant rumble harmonics**
- Generic AI denoisers (LALAL.AI, Demucs) trained on speech/music — they can't hear below 50 Hz and have never seen an elephant

## Our Approach (1 minute)

**Show slide:** Pipeline architecture diagram (6 stages).

### 1. High-resolution STFT (the foundation)
- **n_fft = 8192** → 5.4 Hz frequency resolution
- Most teams use n_fft=1024 → 43 Hz/bin → can't even resolve the difference between a 14 Hz elephant and a 17 Hz elephant
- *This is a free win no one else will take.*

### 2. HPSS + Zeppelzauer enhancement
- Harmonic-Percussive Source Separation
- Median filter along the time axis → enhances horizontal harmonic contours
- Isolates elephant from transient car sounds

### 3. Subharmonic Summation (NSSH)
- For each f0 candidate from 8-25 Hz, sum energy at 2f₀, 3f₀, 4f₀... up to 1000 Hz
- Normalize by number of harmonics summed
- **Detect f0 by working backward from the strong harmonics** (because the 2nd harmonic is stronger than the fundamental)
- Adapted from cetacean bioacoustics research — 30% more precision/recall than spectrogram cross-correlation at low SNR

### 4. Octave-check heuristic
- SHS can return 2f₀ as the "fundamental" because the 2nd harmonic is so strong
- We explicitly check: "does spectrum at f₀/2 match the expected subharmonic?"
- If yes → halve the estimate

### 5. Time-varying harmonic comb mask
- At each frame, build a mask with narrow bandpass at f₀, 2f₀, 3f₀...
- Mask preserves elephant energy, suppresses everything between harmonics
- **This is the technical moat** — generic tools don't have domain priors this specific

### 6. Residual noisereduce
- Stationary mode for generator hum (we have a noise profile from gaps between calls)
- Non-stationary for car/plane (adaptive)

## The Demo (2 minutes)

**Show:** 3 before/after spectrograms from real ElephantVoices recordings:
- Generator noise + rumble → clean rumble
- Vehicle noise + rumble → clean rumble
- Airplane noise + rumble → clean rumble

Each shows:
- Original noisy spectrogram
- Our comb mask overlay (cyan)
- Cleaned output with f₀ contour traced
- Harmonic markers (2f₀, 3f₀...)
- SNR annotation

**Then:** Play the A/B audio — original vs cleaned. The listener hears the rumble emerge from the mechanical noise.

**Bonus:** Multi-speaker separation — synthetic 14 Hz + 18 Hz two-elephant mixture separated into two tracks via top-K SHS + greedy track linking.

## The Impact (30 seconds)

- **212 real rumbles validated** across 44 real field recordings (48 kHz)
- **174 tests passing** — production-quality code
- **Raven Pro-compatible output** — drops into ElephantVoices' existing research workflow
- **Web demo + CLI** — researchers can batch-process 212 calls in minutes
- **Open source** — MIT licensed, reproducible, documented

## The Close

> "Every previous attempt at bioacoustic denoising has been generic. We built something that understands elephants — specifically, that their harmonic structure is their mathematical signature. When the noise tries to hide in the same band, the math still works. That's the difference between removing noise and extracting science."

---

## Key Citations (if asked)

- Zeppelzauer, M. et al. — *Spectro-temporal structure enhancement for elephant rumble detection*
- Normalized Subharmonic Summation (NSSH) — adapted from cetacean acoustic research
- librosa, scipy, noisereduce — open-source stack (no ML training required)

## Anticipated Questions

**Q: Why not use ML?**
A: We have 44 recordings. You can't train a U-Net or GAN on 44 examples without severe overfitting. Classical DSP with domain priors is the right tool when you have mathematical structure to exploit. And ML tools like Demucs/RNNoise are trained on speech/music and can't hear infrasonic content at all.

**Q: Why n_fft=8192?**
A: sr/n_fft gives you frequency resolution. At 48 kHz and n_fft=1024, you get 47 Hz/bin — you literally cannot distinguish a 14 Hz elephant from a 20 Hz elephant. At n_fft=8192, you get 5.86 Hz/bin. The tradeoff is temporal resolution, but elephant rumbles are slow (100ms+) so time resolution isn't critical.

**Q: Does this work on a different species?**
A: Any vocalization with a strict harmonic series — whales, dolphins, some birds. The algorithm is domain-agnostic; the *parameters* (f₀ range, harmonic count) are what you tune per species.

**Q: What about overlapping calls?**
A: Phase 6 handles that — top-K subharmonic summation returns multiple f₀ candidates per frame, then a greedy track linker joins them into per-caller tracks across time. When the harmonics cross (different callers), we keep them separate via pitch continuity.

---

*Generated for HackSMU 2026 pitch — v1.1 Phase 11*
