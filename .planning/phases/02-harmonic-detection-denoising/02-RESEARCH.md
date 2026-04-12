# Phase 2: Harmonic Detection & Denoising - Research

**Researched:** 2026-04-11
**Domain:** Infrasonic f0 detection via subharmonic summation + time-varying harmonic comb masking + noisereduce residual cleanup
**Confidence:** HIGH (HPSS, comb masking, noisereduce API), MEDIUM (SHS octave-check heuristic specifics)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HARM-01 | Apply HPSS with tuned kernel to separate harmonic elephant content from transient noise | librosa.decompose.hpss with margin parameter; kernel sizes must be computed in bin units for n_fft=8192 (see Architecture Patterns) |
| HARM-02 | Apply median filtering along time axis to enhance horizontal harmonic contours (Zeppelzauer method) | scipy.signal.medfilt2d or ndimage.median_filter along axis=1 (time) on STFT magnitude; HPSS with wide harmonic kernel achieves this implicitly |
| HARM-03 | Detect f0 via subharmonic summation sweeping 8-25Hz, summing power at integer multiples up to 1000Hz | Custom numpy SHS loop: sweep candidate f0, index spectrogram at bins for k*f0, accumulate power, argmax = detected f0 |
| HARM-04 | Include octave-check heuristic to prevent 2f0 misdetection as fundamental | Post-SHS: if f0 > 30 Hz and power at f0/2 is > 0.7x power at f0, halve f0; see Code Examples |
| HARM-05 | Build time-varying harmonic comb mask at integer multiples of detected f0 with ±5Hz bandwidth | Soft mask array shape (n_freq_bins, n_frames); for each frame set mask value at ±bandwidth bins around k*f0 |
| HARM-06 | Apply comb mask to magnitude spectrogram and reconstruct audio via ISTFT with original phase | `magnitude * mask` then `reconstruct_audio(masked_mag, original_phase)` from spectrogram.py (already built) |
| CLEAN-01 | Apply noisereduce non-stationary spectral gating on comb-masked output | `noisereduce.reduce_noise(y, sr, stationary=False)` — no noise profile clip required |
| CLEAN-02 | Use stationary noisereduce with noise profile for generator-type recordings | `noisereduce.reduce_noise(y, sr, y_noise=noise_clip, stationary=True, prop_decrease=0.8)` |
| CLEAN-03 | Select cleanup strategy based on noise type classification | Branch on `noise_type["type"]`; "generator" → CLEAN-02; all others → CLEAN-01 |
</phase_requirements>

---

## Summary

Phase 2 builds the three-stage signal extraction chain: HPSS (to pre-isolate harmonic content), SHS f0 detection (to find the elephant fundamental frame-by-frame), and comb masking (to surgically retain only harmonically-structured content). The final step is a noisereduce residual cleanup pass that removes whatever broadband noise slips past the comb.

The fundamental algorithmic challenge is that elephant rumbles are spectrally unusual: the 2nd harmonic (2*f0) is stronger than the fundamental. Standard SHS implementations designed for speech or cetaceans assume the fundamental is strongest — they will systematically return an octave-doubled f0 estimate. Every aspect of Phase 2 must be designed with this inversion in mind.

The Phase 1 modules provide everything needed as inputs: `compute_stft()` returns `magnitude`, `phase`, and `freq_bins`; `classify_noise_type()` returns the `type` field that drives CLEAN-03 branching; `reconstruct_audio()` takes masked magnitude plus the original phase and returns clean audio. Phase 2 only needs to slot new functions between these.

**Primary recommendation:** Implement `hpss_enhance()` → `detect_f0_shs()` → `build_comb_mask()` → `apply_noisereduce()` as four separate pure functions in `pipeline/harmonic_processor.py`. Each function takes and returns the shared context dict. Validate the chain on 5 annotated calls before scaling.

---

## Standard Stack

### Core (all already installed per STACK.md)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| librosa | 0.11.0 | `librosa.decompose.hpss()` — HPSS | Built-in, tuned, accepts margin parameter for infrasound |
| numpy | >=1.26 | SHS loop, comb mask array construction | Native array indexing and vectorized ops for inner loops |
| scipy | >=1.13 | `ndimage.median_filter` for time-axis smoothing; `ndimage.gaussian_filter1d` for f0 smoothing | Already installed; provides both 2D median filter and 1D smoothing |
| noisereduce | 3.0.3 | `reduce_noise()` with stationary and non-stationary modes | Already in stack; bioacoustics-designed; zero tuning needed for stationary generator |

### No new dependencies required

All libraries needed for Phase 2 are present in the installed stack. No new `pip install` commands needed.

---

## Architecture Patterns

### Module: pipeline/harmonic_processor.py

All Phase 2 logic lives in a single new file. Each function takes the shared context dict and returns it with new keys added.

```
pipeline/
├── config.py           (Phase 1 — DSP constants)
├── ingestor.py         (Phase 1 — data loading)
├── spectrogram.py      (Phase 1 — STFT + reconstruct_audio)
├── noise_classifier.py (Phase 1 — classify_noise_type)
└── harmonic_processor.py  (Phase 2 — NEW)
    ├── hpss_enhance(ctx)       → adds ctx["magnitude_harmonic"]
    ├── detect_f0_shs(ctx)      → adds ctx["f0_contour"]
    ├── build_comb_mask(ctx)    → adds ctx["comb_mask"]
    └── apply_noisereduce(ctx)  → adds ctx["audio_clean"]
```

### Pattern 1: HPSS with Infrasonic-Scaled Kernel (HARM-01, HARM-02)

**What:** `librosa.decompose.hpss()` operates on the power spectrogram magnitude. The harmonic kernel is a horizontal median filter in the spectrogram domain. Default kernel size is 31 samples. At n_fft=8192 and 44100 Hz, one bin = 5.4 Hz — so a 31-bin kernel spans 167 Hz horizontally. For elephant rumbles with harmonics at 10-25 Hz, this kernel is too wide and will merge adjacent harmonic lines together.

**Correct kernel sizing:**
- Each bin = sr / n_fft Hz = 44100 / 8192 = 5.38 Hz/bin
- Harmonic spacing = f0 ≈ 10-25 Hz = roughly 2-5 bins
- Harmonic kernel should be narrow enough to not span two harmonic lines: set to 5-7 bins
- Percussive kernel (time dimension): transients are short; default 31 is fine

**When to use:** Always first step; HPSS on magnitude separates harmonic content from impulsive noise. This satisfies HARM-02 (Zeppelzauer method) because the horizontal harmonic filter enhances temporally-continuous harmonic contours.

```python
# Source: librosa.org/doc/main/generated/librosa.decompose.hpss.html
import librosa
import numpy as np

def hpss_enhance(ctx: dict) -> dict:
    """
    HARM-01, HARM-02: HPSS with kernel calibrated for infrasonic harmonics.

    kernel_size is specified in spectrogram frames (not Hz).
    harmonic kernel = narrow frequency span (catches horizontal lines at 10-25 Hz spacing)
    percussive kernel = narrow time span (catches transient noise spikes)
    margin > 1.0 creates a residual bucket — content that is neither clearly harmonic
    nor clearly percussive lands in the residual and is discarded.
    """
    sr = ctx["sr"]
    n_fft = ctx["n_fft"]
    magnitude = ctx["magnitude"]  # shape: (n_freq_bins, n_frames)

    # Calculate bin width to set kernel in physical Hz terms
    hz_per_bin = sr / n_fft  # e.g. 5.38 Hz/bin at 44100/8192

    # Harmonic kernel: 5 frequency bins (~27 Hz span) — narrow enough to
    # resolve 10-25 Hz harmonic lines without merging adjacent harmonics
    harmonic_kernel_bins = max(5, int(round(27 / hz_per_bin)))

    # Percussive kernel: 31 time frames is librosa default; fine for transients
    percussive_kernel_frames = 31

    # margin=(2.0, 2.0): both components must be 2x stronger than residual
    # to be assigned; reduces false assignment of noise to harmonic channel
    S_harmonic, _ = librosa.decompose.hpss(
        magnitude,
        kernel_size=(harmonic_kernel_bins, percussive_kernel_frames),
        margin=(2.0, 2.0),
    )

    ctx["magnitude_harmonic"] = S_harmonic
    ctx["hz_per_bin"] = hz_per_bin
    return ctx
```

### Pattern 2: Subharmonic Summation with Elephant-Aware Octave Check (HARM-03, HARM-04)

**What:** SHS sweeps candidate f0 values in 8-25 Hz. For each candidate, it indexes the spectrogram at 1*f0, 2*f0, 3*f0, ... up to 1000 Hz and sums the power. The candidate with the highest sum wins. This is done per time frame to produce a time-varying f0 contour.

**Octave error mechanism:** The 2nd harmonic of elephant rumbles is stronger than the fundamental. SHS will detect 2*f0 as the "best candidate" because at that frequency, the harmonics it sums (1x, 2x, 3x of 2*f0 = 2*f0, 4*f0, 6*f0) happen to coincide with strong energy. The octave check catches this: if the winner is in 25-50 Hz range and there is strong energy at winner/2, halve the estimate.

**Frame-level smoothing:** Raw f0 estimates are noisy frame-to-frame (quantization to frequency bins). Apply a 1D median filter over 5-11 frames before building the mask.

```python
# Source: domain knowledge from project context + numpy indexing patterns
from scipy.ndimage import median_filter

def detect_f0_shs(ctx: dict) -> dict:
    """
    HARM-03, HARM-04: Subharmonic summation with octave-check heuristic.

    Sweeps f0 candidates in 8-25 Hz. For each candidate, sums power at
    k * f0 for k = 1..N where k*f0 <= 1000 Hz (NSSH: divide by N to normalize).
    Octave-check: if winner > 30 Hz and energy at winner/2 >= 0.7 * energy at winner,
    halve the estimate.
    """
    magnitude = ctx["magnitude_harmonic"]  # use HPSS-enhanced magnitude
    freq_bins = ctx["freq_bins"]           # shape: (n_freq_bins,)
    sr = ctx["sr"]
    n_fft = ctx["n_fft"]
    hz_per_bin = ctx["hz_per_bin"]

    # f0 candidate range per project domain knowledge
    F0_MIN_HZ = 8.0
    F0_MAX_HZ = 25.0
    MAX_HARMONIC_HZ = 1000.0

    n_frames = magnitude.shape[1]
    f0_contour = np.zeros(n_frames)

    # Candidate f0 values: step at half a bin for sub-bin resolution
    f0_candidates = np.arange(F0_MIN_HZ, F0_MAX_HZ, hz_per_bin / 2)

    for t in range(n_frames):
        spectrum = magnitude[:, t]
        best_score = -1.0
        best_f0 = F0_MIN_HZ

        for f0_cand in f0_candidates:
            n_harmonics = int(MAX_HARMONIC_HZ / f0_cand)
            if n_harmonics < 2:
                continue
            score = 0.0
            for k in range(1, n_harmonics + 1):
                harmonic_hz = k * f0_cand
                bin_idx = int(round(harmonic_hz / hz_per_bin))
                if bin_idx >= len(spectrum):
                    break
                score += spectrum[bin_idx]
            # NSSH: normalize by number of harmonics summed
            score /= n_harmonics

            if score > best_score:
                best_score = score
                best_f0 = f0_cand

        # HARM-04: Octave-check heuristic
        # If detected f0 > 30 Hz, check if there is strong energy at half that frequency
        if best_f0 > 30.0:
            half_bin = int(round((best_f0 / 2) / hz_per_bin))
            best_bin = int(round(best_f0 / hz_per_bin))
            if half_bin < len(spectrum) and best_bin < len(spectrum):
                half_power = spectrum[half_bin]
                best_power = spectrum[best_bin]
                if half_power >= 0.7 * best_power:
                    best_f0 = best_f0 / 2  # halve: 2f0 misdetected, real f0 is lower

        f0_contour[t] = best_f0

    # Smooth f0 contour: 1D median filter over 9 frames to remove outliers
    # while preserving pitch glides
    f0_contour = median_filter(f0_contour, size=9)

    ctx["f0_contour"] = f0_contour
    return ctx
```

**Performance note:** The per-frame nested loop above is O(n_frames * n_candidates * max_harmonics). For a 5-second call at hop_length=512 and sr=44100: n_frames ≈ 430, n_candidates ≈ 62, n_harmonics ≈ 40-125. Worst case ~3.3M iterations per call. In Python this is slow (5-20 seconds per call). A vectorized version using numpy broadcast is possible and recommended if demo processing time exceeds budget.

**Vectorized SHS alternative (faster):**
```python
# Vectorize across candidates only; inner harmonic sum becomes a numpy op
for f0_cand in f0_candidates:
    harmonic_bins = np.round(
        np.arange(1, int(MAX_HARMONIC_HZ / f0_cand) + 1) * f0_cand / hz_per_bin
    ).astype(int)
    harmonic_bins = harmonic_bins[harmonic_bins < n_freq_bins]
    # Shape: (n_harmonics, n_frames)
    scores_matrix = magnitude[harmonic_bins, :]  # fancy indexing
    scores_per_frame = scores_matrix.sum(axis=0) / len(harmonic_bins)
    # update best_f0_per_frame via argmax tracking
```

### Pattern 3: Time-Varying Soft Harmonic Comb Mask (HARM-05)

**What:** For each time frame, build a soft mask that peaks at 1.0 at each harmonic bin and tapers to 0.0 within ±bandwidth. Use a triangular or Hann-shaped window per tooth so mask transitions are smooth (avoids hard-edge artifacts).

**Bandwidth:** The requirements specify ±5 Hz. At n_fft=8192 and 44100 Hz, 5 Hz = ~0.93 bins. Round up to ±1 bin minimum. This gives 3-bin-wide teeth (center ± 1 bin on each side). If pitch modulation is visible in spectrograms and warbling is heard, increase to ±2 bins (±10.76 Hz).

```python
# Source: numpy masking pattern, domain-calibrated from project context
def build_comb_mask(ctx: dict) -> dict:
    """
    HARM-05: Time-varying soft harmonic comb mask.

    For each time frame, sets mask value to 1.0 at each harmonic of the detected f0,
    tapering to 0.0 at ±bandwidth_bins. Background mask value is 0.0 (reject everything
    that is not a harmonic).

    Soft mask avoids phase reconstruction artifacts (see Pitfalls research).
    """
    magnitude = ctx["magnitude"]  # original (not HPSS) magnitude for reconstruction
    f0_contour = ctx["f0_contour"]
    freq_bins = ctx["freq_bins"]
    hz_per_bin = ctx["hz_per_bin"]

    n_freq_bins, n_frames = magnitude.shape
    BANDWIDTH_HZ = 5.0
    bandwidth_bins = max(1, int(round(BANDWIDTH_HZ / hz_per_bin)))
    MAX_HARMONIC_HZ = 1000.0

    # Initialize mask to zeros (reject by default)
    comb_mask = np.zeros((n_freq_bins, n_frames), dtype=np.float32)

    for t in range(n_frames):
        f0 = f0_contour[t]
        if f0 <= 0:
            continue

        k = 1
        while k * f0 <= MAX_HARMONIC_HZ:
            center_hz = k * f0
            center_bin = int(round(center_hz / hz_per_bin))

            # Triangular soft window over ±bandwidth_bins
            for delta in range(-bandwidth_bins, bandwidth_bins + 1):
                b = center_bin + delta
                if 0 <= b < n_freq_bins:
                    # Triangular taper: 1.0 at center, 0.0 at edges
                    weight = 1.0 - abs(delta) / (bandwidth_bins + 1)
                    comb_mask[b, t] = max(comb_mask[b, t], weight)
            k += 1

    ctx["comb_mask"] = comb_mask
    return ctx
```

### Pattern 4: Mask Application + ISTFT (HARM-06)

**What:** Multiply original magnitude by comb mask, then call `reconstruct_audio()` from Phase 1.

```python
# Source: spectrogram.py reconstruct_audio() — already built in Phase 1
def apply_comb_mask(ctx: dict) -> dict:
    """
    HARM-06: Apply comb mask to original magnitude, reconstruct audio.

    Uses the original phase (not HPSS-filtered phase) to avoid phase artifacts.
    The comb mask is applied to the original magnitude, not the HPSS harmonic
    magnitude — this preserves the correct amplitude relationship.
    """
    from pipeline.spectrogram import reconstruct_audio

    magnitude = ctx["magnitude"]
    phase = ctx["phase"]
    comb_mask = ctx["comb_mask"]

    # Apply soft mask: values 0.0-1.0
    masked_magnitude = magnitude * comb_mask

    # Reconstruct using original phase (SPEC-02 pattern from Phase 1)
    ctx["audio_comb_masked"] = reconstruct_audio(masked_magnitude, phase)
    ctx["masked_magnitude"] = masked_magnitude
    return ctx
```

### Pattern 5: Noise-Type-Adaptive noisereduce Cleanup (CLEAN-01, CLEAN-02, CLEAN-03)

**What:** After comb masking, residual broadband noise remains. Route to stationary or non-stationary noisereduce based on `noise_type["type"]` from Phase 1.

```python
# Source: github.com/timsainb/noisereduce README + noisereduce 3.0.3 API
import noisereduce as nr

def apply_noisereduce(ctx: dict, noise_clip: np.ndarray | None = None) -> dict:
    """
    CLEAN-01, CLEAN-02, CLEAN-03: Adaptive spectral gating based on noise type.

    Generator (stationary): use noise clip from extract_noise_gaps() as profile.
    Car / plane / mixed (non-stationary): no profile needed, stationary=False.

    noise_clip: numpy array of noise-only audio (from ingestor.extract_noise_gaps).
                Required for generator noise_type. Pass None for non-stationary.
    """
    audio = ctx["audio_comb_masked"]
    sr = ctx["sr"]
    noise_type = ctx["noise_type"]["type"]  # from classify_noise_type()

    if noise_type == "generator":
        # CLEAN-02: stationary mode with noise profile
        if noise_clip is None:
            raise ValueError(
                "Generator noise type requires a noise_clip from extract_noise_gaps(). "
                "Load a noise-only segment from the same recording and pass it here."
            )
        audio_clean = nr.reduce_noise(
            y=audio,
            sr=sr,
            y_noise=noise_clip,
            stationary=True,
            prop_decrease=0.8,  # 80% reduction; tunable without re-running full pipeline
        )
    else:
        # CLEAN-01: non-stationary mode for car / plane / mixed
        audio_clean = nr.reduce_noise(
            y=audio,
            sr=sr,
            stationary=False,
        )

    ctx["audio_clean"] = audio_clean
    return ctx
```

### Pattern 6: Full Pipeline Runner (all Phase 2 requirements combined)

```python
# pipeline/harmonic_processor.py — exported entry point
def process_call(
    y: np.ndarray,
    sr: int,
    noise_type: dict,
    noise_clip: np.ndarray | None = None,
) -> dict:
    """
    Runs full Phase 2 chain on a single call segment.

    Args:
        y:          Audio array from load_call_segment()
        sr:         Native sample rate
        noise_type: Dict from classify_noise_type() — uses ["type"] field
        noise_clip: Audio array of noise-only segment (required for generator)

    Returns:
        Context dict with keys: audio_clean, masked_magnitude, f0_contour, comb_mask,
        and all intermediate Phase 1 outputs
    """
    from pipeline.spectrogram import compute_stft

    ctx = compute_stft(y, sr)
    ctx["noise_type"] = noise_type

    ctx = hpss_enhance(ctx)
    ctx = detect_f0_shs(ctx)
    ctx = build_comb_mask(ctx)
    ctx = apply_comb_mask(ctx)
    ctx = apply_noisereduce(ctx, noise_clip=noise_clip)
    return ctx
```

### Anti-Patterns to Avoid

- **Running noisereduce before HPSS:** Generic spectral gating attenuates infrasonic harmonics before SHS can detect f0. Always HPSS first.
- **Using SHS on raw magnitude instead of HPSS-enhanced magnitude:** Raw spectrogram includes engine noise harmonics that bias the SHS vote.
- **Building comb mask from HPSS magnitude for reconstruction:** Build mask on the original magnitude; apply to original magnitude; reconstruct. Using HPSS-filtered magnitude for reconstruction discards phase information that came from the original STFT.
- **Hard binary comb mask:** A mask of exactly 0 or 1 creates abrupt edges that generate musical noise artifacts on reconstruction. Use soft weights (0.0-1.0 triangular window).
- **Skipping octave check because f0 range "looks correct":** The check is fast and costs nothing; the bug only manifests on low-SNR frames where it matters most.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Harmonic-percussive separation | Custom 2D median filter | `librosa.decompose.hpss()` | librosa's HPSS is thoroughly tested; margin parameter gives exactly the control needed; custom 2D filters have boundary effects and normalization issues |
| Stationary noise spectral gating | Wiener filter from scratch | `noisereduce.reduce_noise(stationary=True)` | noisereduce implements proper multi-band Wiener filtering; rolling noise estimation handles non-uniform noise floors |
| Non-stationary noise estimation | Rolling RMS threshold | `noisereduce.reduce_noise(stationary=False)` | non-stationary mode uses 2D smoothing with prop_decrease; custom RMS gates produce pumping artifacts |
| f0 post-smoothing | Mean filter or EMA | `scipy.ndimage.median_filter` | Median filter preserves step changes in f0 (pitch glides); mean and EMA smear edges and bias toward the outlier direction |

**Key insight:** The custom components in Phase 2 are exactly two things: the SHS loop (no library implements NSSH for infrasonic f0 with the elephant octave bias correction) and the comb mask builder (no library builds time-varying harmonic comb masks from an arbitrary f0 contour). Everything else is library calls.

---

## Common Pitfalls

### Pitfall 1: HPSS Kernel Too Wide — Merges Adjacent Harmonic Lines
**What goes wrong:** Default `kernel_size=31` spans 167 Hz at 5.4 Hz/bin — wider than several elephant harmonic spacings. Adjacent harmonic lines blur together; HPSS cannot distinguish them.
**Why it happens:** Default kernel is calibrated for speech (harmonics 80-500 Hz apart), not infrasound (10-25 Hz apart).
**How to avoid:** Compute `hz_per_bin = sr / n_fft`; set harmonic kernel to `max(5, int(27 / hz_per_bin))` bins — about 27 Hz span regardless of sample rate.
**Warning signs:** HPSS harmonic component in 10-50 Hz region looks like a continuous smeared stripe rather than distinct parallel lines.

### Pitfall 2: SHS Octave Error from 2nd-Harmonic Dominance
**What goes wrong:** Elephant 2nd harmonic is stronger than fundamental. SHS votes for 2*f0 as the "best candidate." Comb mask is built at 2x the correct frequencies, retaining engine noise (which happens to be in the same range) and discarding the real elephant harmonics.
**Why it happens:** SHS was designed for speech/cetaceans where fundamental is dominant. Elephant spectral inversion breaks the algorithm's implicit assumption.
**How to avoid:** Always run the octave-check heuristic after SHS. Validate on 5 annotated calls where f0 is known from the spreadsheet before batch run.
**Warning signs:** Detected f0 values in 25-50 Hz range for known calls whose f0 should be 10-25 Hz.

### Pitfall 3: Comb Mask Built from HPSS-Filtered Magnitude for Reconstruction
**What goes wrong:** Using `magnitude_harmonic` (HPSS output) as the base for reconstruction discards the original amplitude relationships. The comb mask is applied to already-attenuated magnitudes, so the output is quieter than intended.
**Why it happens:** HPSS and comb masking both produce "cleaned" magnitudes; developers naturally chain them. But the comb mask is designed to be applied to the original magnitude.
**How to avoid:** Use `magnitude_harmonic` only for the SHS step (f0 detection). Build the comb mask from `f0_contour`. Apply it to `ctx["magnitude"]` (original). Reconstruct from `ctx["phase"]` (original).
**Warning signs:** Clean output is significantly quieter than expected; listening level difference is more than 6 dB.

### Pitfall 4: f0 Contour Not Smoothed Before Mask Construction
**What goes wrong:** Raw frame-by-frame SHS estimates jump between adjacent quantized frequency values (e.g., 14.1 Hz, 13.7 Hz, 14.8 Hz due to bin quantization). The resulting comb mask flickers frame-to-frame. Output has a "warbling" quality in the low-frequency band.
**Why it happens:** SHS argmax is quantized to frequency bins. Bin-to-bin quantization noise is larger than the actual pitch variation.
**How to avoid:** Apply `scipy.ndimage.median_filter(f0_contour, size=9)` before calling `build_comb_mask()`. The median filter removes outlier frames without smoothing pitch glides.
**Warning signs:** Listening to comb-masked output reveals warbling below 200 Hz; f0 contour plot shows high-frequency jitter frame-to-frame.

### Pitfall 5: No Noise Clip Available for Generator Mode
**What goes wrong:** `apply_noisereduce()` is called with `noise_clip=None` but `noise_type="generator"`. The call raises an error or silently falls back to non-stationary mode, losing the quality advantage of stationary mode with a known profile.
**Why it happens:** The noise clip must come from `ingestor.extract_noise_gaps()` — a separate loading step that must happen before the call is processed.
**How to avoid:** In the call orchestration, always extract noise gaps and load the noise clip before calling `process_call()`. If `extract_noise_gaps()` returns an empty list (no gaps found), fall back to non-stationary mode regardless of `noise_type`. Document this fallback explicitly.
**Warning signs:** Generator recordings output sounds noisier than expected; stationary noisereduce was not applied.

### Pitfall 6: SHS Inner Loop Too Slow for Demo Batch Run
**What goes wrong:** Per-frame per-candidate Python loop takes 10-30 seconds per call. 212 calls * 30s = over an hour for a demo batch run.
**Why it happens:** Python loops on numpy arrays are ~100x slower than vectorized numpy operations.
**How to avoid:** Vectorize the harmonic bin indexing across frames using fancy indexing: `magnitude[harmonic_bins, :]` extracts a (n_harmonics, n_frames) submatrix in one op. Implement the vectorized version first; fall back to the readable loop only for a single-call verification run.
**Warning signs:** Processing a 5-second call takes more than 3 seconds.

---

## Code Examples

### Verified: librosa.decompose.hpss() signature and margin parameter
```python
# Source: librosa.org/doc/main/generated/librosa.decompose.hpss.html
# margin as float: same margin for both components
# margin as tuple: (harmonic_margin, percussive_margin)
harmonic, percussive = librosa.decompose.hpss(
    S,                              # magnitude spectrogram
    kernel_size=(7, 31),           # (freq_bins, time_frames)
    power=2.0,                      # L2 norm
    mask=False,                     # return component arrays (not masks)
    margin=(2.0, 2.0),             # residual bucket threshold
)
```

### Verified: noisereduce API for stationary and non-stationary modes
```python
# Source: github.com/timsainb/noisereduce (3.0.3 README)

# Stationary (generator hum) — provide noise clip
import noisereduce as nr
cleaned = nr.reduce_noise(y=signal, sr=sr, y_noise=noise_clip, stationary=True, prop_decrease=0.8)

# Non-stationary (car / plane / mixed) — no noise clip needed
cleaned = nr.reduce_noise(y=signal, sr=sr, stationary=False)
```

### Verified: scipy.ndimage.median_filter for f0 smoothing
```python
# Source: scipy.org docs — ndimage.median_filter
from scipy.ndimage import median_filter
f0_smooth = median_filter(f0_contour, size=9)  # 9-frame window, ~100ms at hop=512
```

### Vectorized SHS Harmonic Power Accumulation
```python
# Source: numpy fancy indexing pattern — domain implementation
n_freq_bins = magnitude.shape[0]
shs_scores = np.zeros((len(f0_candidates), magnitude.shape[1]))

for i, f0_cand in enumerate(f0_candidates):
    k_max = int(MAX_HARMONIC_HZ / f0_cand)
    harmonic_bins = np.round(
        np.arange(1, k_max + 1) * f0_cand / hz_per_bin
    ).astype(int)
    # Clamp to valid bin range
    harmonic_bins = harmonic_bins[harmonic_bins < n_freq_bins]
    if len(harmonic_bins) == 0:
        continue
    # Sum energy at all harmonic bins for all frames at once
    # magnitude[harmonic_bins, :] has shape (n_harmonics, n_frames)
    shs_scores[i, :] = magnitude[harmonic_bins, :].sum(axis=0) / len(harmonic_bins)

# Best f0 per frame
best_candidate_idx = np.argmax(shs_scores, axis=0)
f0_contour_raw = f0_candidates[best_candidate_idx]
```

---

## Integration with Phase 1 Modules

| Phase 1 Output | Used by Phase 2 As | Notes |
|----------------|-------------------|-------|
| `compute_stft(y, sr)` returns `{"magnitude", "phase", "freq_bins", "sr", "n_fft", "hop_length"}` | Input context dict to all Phase 2 functions | Already has the full context structure Phase 2 needs |
| `reconstruct_audio(magnitude, phase)` | Called by `apply_comb_mask()` after masking | Use `ctx["phase"]` (original, not modified) |
| `classify_noise_type(y_noise, sr)` returns `{"type", ...}` | CLEAN-03 branching in `apply_noisereduce()` | Load noise segment via `load_call_segment()` from a noise gap |
| `extract_noise_gaps(wav_path, calls, duration)` returns list of (start, end) tuples | Provides timestamps for loading noise clip in generator mode | Must be called before `process_call()` in the orchestration layer |
| `config.N_FFT = 8192`, `config.HOP_LENGTH = 512` | Used to compute `hz_per_bin = sr / N_FFT` | Already verified by `verify_resolution()` at load time |

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Standard SHS with f0 range scan | NSSH (normalized by harmonic count) | 30% better precision/recall at low SNR per project research |
| Hard binary comb mask | Soft mask with triangular window at each tooth | Eliminates musical noise artifacts; trivial implementation change |
| Fixed-width noise profile window | Stationary / non-stationary routing from classifier | Prevents noise-profile contamination for transient noise types |
| HPSS with speech-tuned kernel | HPSS with kernel sized in Hz (infrasonic-calibrated) | Resolves 10-25 Hz harmonic lines rather than smearing them |

---

## Open Questions

1. **SHS performance on real recordings**
   - What we know: Synthetic validation works; f0 range 8-25 Hz is from literature
   - What's unclear: Whether the octave-check threshold (0.7x) is well-calibrated for the actual recordings
   - Recommendation: Validate on 5 annotated calls with known f0 from the spreadsheet; tune threshold empirically before batch run

2. **HPSS margin value (2.0 vs. lower)**
   - What we know: Higher margin = more content assigned to residual (discarded), lower margin = more content assigned to harmonic or percussive
   - What's unclear: Whether margin=2.0 is too aggressive for faint calls at low SNR
   - Recommendation: Test margin=(1.5, 1.5) and margin=(2.0, 2.0) on one low-SNR call; compare output spectrogram

3. **Noise clip availability for all generator recordings**
   - What we know: `extract_noise_gaps()` returns empty list if no gap >= 1 second
   - What's unclear: How many generator recordings have no usable noise gap
   - Recommendation: Add fallback in `apply_noisereduce()`: if noise clip is None for generator type, use `stationary=False` with a warning rather than raising an error

4. **SHS bandwidth requirement for calls with strong frequency glides**
   - What we know: Some elephant calls have significant frequency modulation (glides)
   - What's unclear: Whether ±5 Hz comb bandwidth is sufficient to track fast glides, or if ±10 Hz is needed
   - Recommendation: Listen to first 3 processed calls; if warbling is present, increase bandwidth to ±2 bins

---

## Sources

### Primary (HIGH confidence)
- librosa.decompose.hpss: https://librosa.org/doc/main/generated/librosa.decompose.hpss.html — margin parameter, kernel_size format, return convention confirmed
- noisereduce GitHub README (3.0.3): https://github.com/timsainb/noisereduce — stationary/non-stationary API, y_noise parameter, prop_decrease parameter
- scipy.ndimage.median_filter: https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.median_filter.html — size parameter, axis behavior
- Phase 1 source code: pipeline/spectrogram.py, pipeline/noise_classifier.py, pipeline/ingestor.py, pipeline/config.py — all interface contracts verified by reading actual implementation

### Secondary (MEDIUM confidence)
- NSSH description in project context — 30% precision/recall improvement claim sourced from project research notes (not independently re-verified in this session)
- Octave-check threshold (0.7x) — heuristic based on domain knowledge; specific threshold needs empirical tuning on real recordings

### Tertiary (LOW confidence)
- Optimal HPSS margin value for infrasonic content — no published reference specifically for elephant rumble HPSS; 2.0 is informed estimate from general bioacoustic literature
- ±5 Hz bandwidth adequacy for pitch-modulated calls — based on project requirements text (HARM-05 specifies ±5 Hz); actual adequacy needs listening test validation

---

## Metadata

**Confidence breakdown:**
- HPSS integration: HIGH — librosa API confirmed, kernel sizing is arithmetic from known constants
- SHS algorithm: HIGH — numpy implementation pattern is standard, octave-check is deterministic logic
- noisereduce integration: HIGH — API confirmed from GitHub README, same library already in stack
- Octave-check threshold (0.7): MEDIUM — heuristic, empirical tuning required on real recordings
- HPSS margin value (2.0): MEDIUM — reasonable for bioacoustics, not elephant-specific validated

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (stable libraries; noisereduce and librosa APIs are unlikely to change)
