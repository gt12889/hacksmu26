# Slides — ElephantVoices Denoiser

**HackSMU 2026** | 3-5 minute pitch

---

## Slide 1 — Title

# ElephantVoices Denoiser 🐘

**Surgical extraction of elephant rumbles from field recordings contaminated by mechanical noise**

HackSMU 2026 | Team [Your Team]

---

## Slide 2 — The Problem

### Elephants talk at 10-25 Hz

**Fundamentals** in the infrasonic range. Harmonics up to 1000 Hz. The 2nd harmonic is *stronger than the fundamental*.

### Engines talk at 30 Hz

**Generator fundamentals:** ~30 Hz. Second harmonic: 60 Hz. Third: 90 Hz.

### The collision

> Engine harmonics sit **directly on top of** elephant rumble harmonics.

Generic denoisers (LALAL.AI, Demucs, RNNoise) are trained on speech/music. They can't even hear below 50 Hz.

---

## Slide 3 — The Insight

Elephant calls have a mathematical signature that noise doesn't:

> **Strict integer-multiple harmonic series** anchored to one fundamental.

Even when noise shares the frequency band, the *structure* is different.

**We don't remove noise — we extract harmonic structure.**

---

## Slide 4 — The Approach

```
Raw audio (48kHz)
   ↓
High-res STFT (n_fft=8192, 5.4Hz/bin)
   ↓
HPSS — Zeppelzauer spectro-temporal enhancement
   ↓
Subharmonic Summation (NSSH) — detect f0
   ↓
Octave-check — prevent 2f0 false positives
   ↓
Harmonic comb mask — preserve kf0, suppress rest
   ↓
noisereduce — residual cleanup
   ↓
Clean audio + f0 contour + harmonic structure
```

**Classical DSP with domain priors. No training data required.**

---

## Slide 5 — Why n_fft=8192?

| n_fft | Resolution at 48 kHz | Can resolve 14 Hz vs 20 Hz? |
|-------|---------------------|------------------------------|
| 1024 (default) | **47 Hz/bin** | **No — same bin!** |
| 4096 | 11.7 Hz/bin | Barely |
| **8192 (ours)** | **5.9 Hz/bin** | **Yes** |
| 16384 | 2.9 Hz/bin | Yes (overkill) |

*"Most teams use n_fft=1024. It's the default. And it makes the problem unsolvable."*

---

## Slide 6 — Live Demo

**Three real ElephantVoices recordings:**

| Noise Type | Recording | Duration |
|------------|-----------|----------|
| Generator | `090224-09_generator_01.wav` | 2.9s call |
| Vehicle | `04-040920-02_vehicle_1.wav` | 2.8s call |
| Airplane | `1989-06_airplane_01.wav` | 4.0s call |

**Show:**
1. Before spectrogram (noisy)
2. Comb mask overlay (cyan — what we preserve)
3. After spectrogram (cleaned + f₀ contour in lime)
4. Audio A/B toggle — hear the rumble emerge

---

## Slide 7 — Multi-Speaker Separation (Bonus)

When two elephants call at once, their harmonics **cross** in the time-frequency plane.

**Top-K SHS** returns multiple f₀ candidates per frame.

**Greedy track linker** connects them across time via pitch continuity.

→ Two separate WAV files. Two separate conversations. One recording.

*Validated on synthetic 14 Hz + 18 Hz mixture.*

---

## Slide 8 — Impact

- ✅ **212 real rumbles** validated across **44 field recordings** (48 kHz)
- ✅ **174 tests passing** — production-quality, reproducible
- ✅ **Raven Pro compatible** — drops into ElephantVoices' existing workflow
- ✅ **Full-stack demo**: FastAPI backend + React frontend + CLI tools
- ✅ **Open source** (MIT)

**Cost to run on all 212 calls:** ~5 minutes on a laptop. No GPU. No cloud.

---

## Slide 9 — The Pitch

> "Every previous attempt at bioacoustic denoising has been generic."
>
> "We built something that **understands elephants** — specifically, that their harmonic structure is their mathematical signature."
>
> "When the noise tries to hide in the same band, the math still works."
>
> **"That's the difference between removing noise and extracting science."**

---

## Slide 10 — Try It

```bash
git clone https://github.com/gt12889/hacksmu26
cd hacksmu26
pip install -r requirements.txt
cd frontend && npm install && cd ..
bash scripts/start_demo.sh
# → http://localhost:5173
```

**Thank you — questions?**

---

*Generated for HackSMU 2026 — v1.1 Phase 11*
