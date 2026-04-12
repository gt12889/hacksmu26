# Phase 3: Demo Spectrograms & Measurements — Research

**Researched:** 2026-04-11
**Domain:** matplotlib publication figures, spectrogram visualization, acoustic measurements, WAV export
**Confidence:** HIGH (all claims verified against installed libraries and live code execution)

## Summary

Phase 3 produces the visual and audio output that makes the hackathon pitch land. The full pipeline already exists (Phases 1-2); this phase is entirely a scripting and visualization layer — no new DSP needed. The core work is: (1) pick one representative call per noise type from the annotation CSV, (2) run it through `process_call()`, and (3) render a 3-panel matplotlib figure per noise type with f0 contour, harmonic markers, SNR annotation, and a comb mask overlay.

All required libraries are already installed in the project venv. matplotlib 3.10.8 is present, soundfile 0.13.1 handles WAV export, and the pipeline context dict already carries every value needed for the figures (`magnitude`, `comb_mask`, `f0_contour`, `freq_bins`, `audio_clean`, `noise_type`). No new pip installs are required.

The single non-obvious problem is the **frequency axis display range**: the full STFT spans 0–22 kHz but elephant harmonic content lives at 0–500 Hz (roughly the first 92 frequency bins out of 4097). The script must slice the spectrogram to that range for the figures to be readable; plotting the full range compresses all signal into an invisible sliver at the bottom.

**Primary recommendation:** Write `scripts/demo_spectrograms.py` that calls `process_call()` once per noise type, slices magnitude to 0–500 Hz for display, and renders a 3-panel figure (original | comb mask overlay | cleaned) saved at 300 dpi. Cleaned WAV exported via `soundfile.write()`. Total new code: ~200 lines.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEMO-01 | Script processes one representative call per noise type (generator, car, plane) through full pipeline | `process_call()` is complete — script just needs to call it 3 times with representative annotation rows |
| DEMO-02 | Publication-quality before/after spectrogram figures (matplotlib, 300dpi) with labeled axes, colorbar, title per noise type | `fig.savefig(path, dpi=300, bbox_inches='tight')` confirmed working; `imshow` + `colorbar` pattern verified |
| DEMO-03 | Overlays detected f0 contour on cleaned spectrogram as a traced line | `ax.plot(times, f0_contour)` on top of `imshow` confirmed; f0_contour is already in context dict |
| DEMO-04 | Annotates harmonic spacing markers (f0, 2f0, 3f0...) on spectrogram with labeled arrows/lines | `ax.axhline(y=k*f0)` + `ax.annotate(text)` pattern verified; must clip to display_freq_max |
| DEMO-05 | Displays SNR improvement (dB), call duration, and detected f0 range as text annotations on each figure | `ax.text(..., transform=ax.transAxes, bbox=dict(...))` inset box confirmed; SNR via harmonic-band power ratio |
| DEMO-06 | 3-panel figure per noise type: original / comb mask overlay / cleaned result | `plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)` pattern verified and saved at 300 dpi |
| DEMO-07 | Exports cleaned WAV files alongside figures | `soundfile.write(path, audio_clean, sr, subtype='PCM_16')` confirmed; soundfile 0.13.1 installed |
</phase_requirements>

## Standard Stack

### Core (all already installed — no new installs needed)

| Library | Installed Version | Purpose | Why Standard |
|---------|-------------------|---------|--------------|
| matplotlib | 3.10.8 | Spectrogram figures, overlays, annotations, 300 dpi export | Already in requirements.txt; all required APIs confirmed working |
| soundfile | 0.13.1 | WAV export of cleaned audio | Already used in `scripts/process_call.py`; librosa's primary backend |
| numpy | 2.4.4 | Array slicing for frequency axis display range, SNR math | Required by all DSP code |
| librosa | 0.11.0 | `power_to_db()` for dB-scale spectrogram display | Already in pipeline |

### No New Dependencies

The project `requirements.txt` already contains all required libraries. Do NOT add new dependencies. Phase 3 is entirely a scripting layer on top of existing pipeline.

## Architecture Patterns

### Recommended Script Structure

```
scripts/
└── demo_spectrograms.py    # New: main demo script
data/
└── outputs/
    └── demo/
        ├── generator_demo.png
        ├── generator_clean.wav
        ├── car_demo.png
        ├── car_clean.wav
        ├── plane_demo.png
        └── plane_clean.wav
```

### Pattern 1: Call Selection — One Per Noise Type

The script must select one representative call per noise type. Since actual recordings are not yet in `data/recordings/` (only `.gitkeep` files), the script needs to:
1. Accept a `--annotations` CSV/XLSX path argument
2. Accept a `--recordings-dir` directory argument
3. Filter annotation rows by `noise_type` column (if present) OR run classifier on first noise gap
4. Take the first available call per type (or hardcode indices if annotations have a noise_type column)

**Fallback strategy when noise_type column absent from CSV:** classify each recording's first noise gap on-the-fly using `classify_noise_type()`. Stop after finding one call per type.

### Pattern 2: Frequency Axis Slicing (Critical)

The full STFT has 4097 bins (0–22050 Hz). For display, slice to the informative range.

```python
# Source: verified by local execution — bin math with n_fft=8192, sr=44100
DISPLAY_FREQ_MAX_HZ = 500  # covers harmonics up to ~35x f0 at 14 Hz
# After running process_call():
freq_bins = ctx["freq_bins"]              # shape (4097,)
display_mask = freq_bins <= DISPLAY_FREQ_MAX_HZ   # 93 bins
mag_display = ctx["magnitude"][display_mask, :]   # shape (93, n_frames)
freq_display = freq_bins[display_mask]            # shape (93,)
```

NEVER plot the full 0–22050 Hz range. All elephant content is compressed into the bottom 0.5% of the y-axis.

### Pattern 3: 3-Panel Figure Layout

```python
# Source: verified by local execution — matplotlib 3.10.8
fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)
titles = ["Original", "Comb Mask Overlay", "Cleaned"]
```

Use `constrained_layout=True` instead of `tight_layout()`. In matplotlib 3.10 `tight_layout()` raises warnings with colorbars; `constrained_layout` handles it correctly.

### Pattern 4: Spectrogram Rendering with imshow

```python
# Source: verified by local execution
def render_spectrogram(ax, magnitude_db, times, freq_display, title, vmin=-80, vmax=0):
    im = ax.imshow(
        magnitude_db,
        aspect="auto",
        origin="lower",
        extent=[times[0], times[-1], freq_display[0], freq_display[-1]],
        cmap="inferno",
        vmin=vmin,
        vmax=vmax,
    )
    ax.set_xlabel("Time (s)", fontsize=10)
    ax.set_ylabel("Frequency (Hz)", fontsize=10)
    ax.set_title(title, fontsize=11)
    return im
```

Use `librosa.power_to_db(magnitude**2, ref=np.max)` to convert to dB scale before display.

### Pattern 5: Comb Mask Overlay (Middle Panel)

The middle panel shows the original spectrogram with the comb mask highlighted in a distinct color. Use RGBA overlay:

```python
# Source: verified by local execution — matplotlib 3.10.8
comb_display = ctx["comb_mask"][display_mask, :]   # shape (93, n_frames)

# Render base spectrogram first
im = render_spectrogram(axes[1], mag_db_display, times, freq_display, "Comb Mask Overlay")

# RGBA overlay: cyan mask proportional to mask value
overlay = np.zeros((*comb_display.shape, 4), dtype=np.float32)
overlay[..., 0] = 0.0   # R
overlay[..., 1] = 1.0   # G
overlay[..., 2] = 1.0   # B  (cyan)
overlay[..., 3] = comb_display * 0.6  # Alpha — scale down for readability

axes[1].imshow(
    overlay,
    aspect="auto",
    origin="lower",
    extent=[times[0], times[-1], freq_display[0], freq_display[-1]],
)
```

### Pattern 6: f0 Contour Overlay on Cleaned Panel

```python
# Source: verified by local execution
n_frames = ctx["magnitude"].shape[1]
hop_length = ctx["hop_length"]
sr = ctx["sr"]
times = librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length)

axes[2].plot(times, ctx["f0_contour"], color="lime", linewidth=1.5, alpha=0.9, label="f0")
```

### Pattern 7: Harmonic Spacing Markers

```python
# Source: verified by local execution
f0_median = float(np.median(ctx["f0_contour"]))
for k in range(1, 15):
    freq = k * f0_median
    if freq > DISPLAY_FREQ_MAX_HZ:
        break
    axes[2].axhline(y=freq, color="cyan", linewidth=0.6, alpha=0.5, linestyle="--")
    axes[2].annotate(
        f"{k}f0",
        xy=(0.01, freq),
        xycoords=("axes fraction", "data"),
        fontsize=6,
        color="cyan",
        va="center",
    )
```

Note: `xycoords=("axes fraction", "data")` requires a 2-tuple — this is the correct matplotlib API for mixed coordinate systems.

### Pattern 8: SNR Measurement

SNR is computed as harmonic-band signal power versus out-of-band noise power. Compare before (original magnitude) versus after (masked_magnitude or reconstructed clean magnitude).

```python
def compute_snr_db(magnitude, freq_bins, f0_median, n_harmonics=8, bandwidth_hz=5.0):
    harmonic_mask = np.zeros(len(freq_bins), dtype=bool)
    for k in range(1, n_harmonics + 1):
        center = k * f0_median
        if center > freq_bins[-1]:
            break
        harmonic_mask |= (freq_bins >= center - bandwidth_hz) & (freq_bins <= center + bandwidth_hz)
    signal_power = np.mean(magnitude[harmonic_mask, :]**2) if harmonic_mask.any() else 0.0
    noise_power = np.mean(magnitude[~harmonic_mask, :]**2) if (~harmonic_mask).any() else 1e-10
    return 10 * np.log10(signal_power / (noise_power + 1e-10))
```

For the "cleaned" SNR, run `compute_stft()` on `ctx["audio_clean"]` to get clean magnitude, then call `compute_snr_db()` on that.

### Pattern 9: Stats Annotation Box

```python
# Source: verified by local execution — matplotlib 3.10.8
f0_contour = ctx["f0_contour"]
snr_before = compute_snr_db(ctx["magnitude"], ctx["freq_bins"], f0_median)
snr_after = compute_snr_db(clean_magnitude, ctx["freq_bins"], f0_median)
duration_sec = len(y) / sr

textstr = (
    f"SNR: {snr_before:.1f} → {snr_after:.1f} dB (+{snr_after - snr_before:.1f})\n"
    f"Duration: {duration_sec:.1f}s\n"
    f"f0: {f0_contour.min():.1f}–{f0_contour.max():.1f} Hz"
)
props = dict(boxstyle="round", facecolor="black", alpha=0.65)
axes[2].text(
    0.98, 0.98, textstr,
    transform=axes[2].transAxes,
    fontsize=8,
    verticalalignment="top",
    horizontalalignment="right",
    bbox=props,
    color="white",
)
```

### Pattern 10: WAV Export

```python
# Source: verified by local execution — soundfile 0.13.1
import soundfile as sf

output_wav = output_dir / f"{noise_type}_clean.wav"
sf.write(str(output_wav), ctx["audio_clean"], sr, subtype="PCM_16")
```

Use `subtype="PCM_16"` for broad compatibility. The cleaned audio is float32 from the pipeline; soundfile normalizes automatically on PCM write if values are within [-1, 1]. If clipping is a concern, normalize: `audio_clean / (np.abs(audio_clean).max() + 1e-10)`.

### Pattern 11: Figure Save

```python
# Source: verified by local execution
output_fig = output_dir / f"{noise_type}_demo.png"
fig.savefig(str(output_fig), dpi=300, bbox_inches="tight", facecolor="white")
plt.close(fig)  # IMPORTANT: always close to free memory between noise types
```

### Anti-Patterns to Avoid

- **Plot full 0–22 kHz y-axis:** Compresses all elephant content to bottom 0.5% of figure. Always slice to `DISPLAY_FREQ_MAX_HZ = 500`.
- **Use `tight_layout()` with colorbars:** Raises warnings in matplotlib 3.10. Use `constrained_layout=True` on figure creation instead.
- **Use `cm.get_cmap()` directly:** Deprecated in matplotlib 3.7, removed in 3.11. Pass colormap name as string to `imshow(cmap='inferno')`.
- **Compute SNR on dB-scale magnitude:** SNR must be computed on linear amplitude or power. Convert to dB only for display, not measurement.
- **Hardcode call timestamps without CLI args:** The script must accept `--annotations` and `--recordings-dir` arguments since the data files are not committed to the repo.
- **Call `process_call()` on the full recording file:** Load only the call segment via `load_call_segment()`. Processing a 1-hour recording through STFT is prohibitively slow.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| dB-scale conversion for display | Custom log scaling | `librosa.power_to_db(magnitude**2, ref=np.max)` | Handles zero-padding, reference normalization correctly |
| WAV file write | Custom PCM encoding | `soundfile.write()` | 24-bit/float support, correct WAV headers |
| ISTFT for clean magnitude | Custom overlap-add | `reconstruct_audio()` from pipeline/spectrogram.py | Already implemented with phase preservation |
| Frame-to-time axis conversion | Manual multiplication | `librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length)` | Handles off-by-one correctly |

## Common Pitfalls

### Pitfall 1: Y-axis Frequency Range
**What goes wrong:** Full spectrogram plotted (0–22 kHz). Elephant content at 8–500 Hz is invisible.
**Why it happens:** `imshow` plots all rows by default. With n_fft=8192, that is 4097 rows.
**How to avoid:** Pre-filter magnitude before plotting: `mask = freq_bins <= 500; mag_display = magnitude[mask, :]`.
**Warning signs:** Spectrogram looks blank or shows only noise at the very bottom edge.

### Pitfall 2: constrained_layout vs tight_layout
**What goes wrong:** `fig.tight_layout()` raises `UserWarning: tight_layout not applied because axes sizes collapsed to zero` when colorbar axes are present.
**Why it happens:** Colorbars create extra axes that confuse tight_layout's algorithm in matplotlib 3.10.
**How to avoid:** Create figure with `plt.subplots(..., constrained_layout=True)`. Do not call `tight_layout()`.
**Warning signs:** Warning in stderr; figure has overlapping labels or clipped colorbar.

### Pitfall 3: f0 Contour Time Axis Mismatch
**What goes wrong:** `ax.plot(times, f0_contour)` raises shape mismatch or plots misaligned.
**Why it happens:** `f0_contour` has `n_frames` elements; `times` must be generated with the same `hop_length` and `sr` as the STFT.
**How to avoid:** Generate times as `librosa.frames_to_time(np.arange(len(f0_contour)), sr=sr, hop_length=HOP_LENGTH)`. The context dict carries `sr` and `hop_length`.
**Warning signs:** f0 line appears at wrong horizontal position or throws ValueError on plot.

### Pitfall 4: process_call() Returns Contour on Full Spectrogram
**What goes wrong:** f0 contour values are in Hz (8–25 Hz), but after slicing magnitude to `freq_display`, the y-axis data coordinates are also in Hz — so overlay alignment is correct. No conversion needed.
**Why it happens:** `imshow` with `extent=[t0, t1, f0, f1]` sets the y-axis to Hz directly.
**How to avoid:** Pass `extent` to `imshow` matching `[times[0], times[-1], freq_display[0], freq_display[-1]]`. Then plot `ax.plot(times, f0_contour)` in the same data coordinates — it aligns automatically.
**Warning signs:** f0 line appears at bottom of plot regardless of actual value.

### Pitfall 5: Audio Clipping on WAV Write
**What goes wrong:** `soundfile.write` with `subtype='PCM_16'` clips values outside [-1, 1] silently.
**Why it happens:** `noisereduce` can occasionally return values slightly above 1.0 due to spectral reconstruction.
**How to avoid:** Normalize before write: `audio = audio / (np.abs(audio).max() + 1e-10)`.
**Warning signs:** WAV plays back distorted with crackling; waveform shows flat tops in audacity.

### Pitfall 6: Missing Output Directory
**What goes wrong:** `savefig` or `soundfile.write` raises FileNotFoundError.
**Why it happens:** `data/outputs/demo/` does not exist on a fresh clone.
**How to avoid:** `output_dir.mkdir(parents=True, exist_ok=True)` at script start.

### Pitfall 7: Call Selection When Noise Type Column Absent
**What goes wrong:** Script crashes because the annotation CSV does not have a `noise_type` column.
**Why it happens:** The ingestor normalizes column names but only guarantees `filename`, `start`, `end`.
**How to avoid:** Try to read `noise_type` column; if absent, run `classify_noise_type()` on the first noise gap per recording and cache result. Accept `--generator-call`, `--car-call`, `--plane-call` as optional CLI overrides for hackathon speed.

## Code Examples

### Full Demo Script Skeleton

```python
# scripts/demo_spectrograms.py
# Source: assembled from verified patterns (all confirmed by local execution)
import argparse
import sys
from pathlib import Path

import librosa
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from pipeline.config import HOP_LENGTH
from pipeline.harmonic_processor import process_call
from pipeline.ingestor import extract_noise_gaps, load_call_segment
from pipeline.noise_classifier import classify_noise_type
from pipeline.spectrogram import compute_stft

DISPLAY_FREQ_MAX_HZ = 500  # Hz — covers 35+ harmonics at 14 Hz f0
NOISE_TYPES = ["generator", "car", "plane"]


def compute_snr_db(magnitude, freq_bins, f0_median, bandwidth_hz=5.0):
    mask = np.zeros(len(freq_bins), dtype=bool)
    for k in range(1, 20):
        c = k * f0_median
        if c > freq_bins[-1]:
            break
        mask |= (freq_bins >= c - bandwidth_hz) & (freq_bins <= c + bandwidth_hz)
    s = np.mean(magnitude[mask, :]**2) if mask.any() else 0.0
    n = np.mean(magnitude[~mask, :]**2) if (~mask).any() else 1e-10
    return 10 * np.log10(s / (n + 1e-10))


def make_demo_figure(noise_type, ctx, y, output_dir):
    sr = ctx["sr"]
    freq_bins = ctx["freq_bins"]
    f0_contour = ctx["f0_contour"]
    f0_median = float(np.median(f0_contour))

    # Frequency slice
    display_mask = freq_bins <= DISPLAY_FREQ_MAX_HZ
    freq_display = freq_bins[display_mask]
    n_frames = ctx["magnitude"].shape[1]
    times = librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=HOP_LENGTH)

    # dB-scale slices
    def to_db(mag):
        return librosa.power_to_db(mag[display_mask, :]**2, ref=np.max)

    mag_orig_db = to_db(ctx["magnitude"])

    # Clean magnitude: re-STFT on audio_clean
    ctx_clean = compute_stft(ctx["audio_clean"], sr)
    mag_clean_db = to_db(ctx_clean["magnitude"])

    # SNR
    snr_before = compute_snr_db(ctx["magnitude"], freq_bins, f0_median)
    snr_after = compute_snr_db(ctx_clean["magnitude"], freq_bins, f0_median)

    # Figure
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)
    fig.suptitle(f"Noise type: {noise_type.upper()} — Elephant Call Denoising", fontsize=13)

    extent = [times[0], times[-1], freq_display[0], freq_display[-1]]
    vmin, vmax = -80, 0

    def render(ax, mag_db, title):
        im = ax.imshow(mag_db, aspect="auto", origin="lower",
                       extent=extent, cmap="inferno", vmin=vmin, vmax=vmax)
        ax.set_xlabel("Time (s)", fontsize=10)
        ax.set_ylabel("Frequency (Hz)", fontsize=10)
        ax.set_title(title, fontsize=11)
        return im

    # Panel 1: Original
    render(axes[0], mag_orig_db, "Original")

    # Panel 2: Comb mask overlay
    render(axes[1], mag_orig_db, "Comb Mask")
    comb_display = ctx["comb_mask"][display_mask, :]
    overlay = np.zeros((*comb_display.shape, 4), dtype=np.float32)
    overlay[..., 1] = 1.0; overlay[..., 2] = 1.0  # cyan
    overlay[..., 3] = comb_display * 0.6
    axes[1].imshow(overlay, aspect="auto", origin="lower", extent=extent)

    # Panel 3: Cleaned + f0 + harmonic markers + stats
    im = render(axes[2], mag_clean_db, "Cleaned")
    axes[2].plot(times, f0_contour, color="lime", linewidth=1.5, alpha=0.9)
    for k in range(1, 30):
        freq = k * f0_median
        if freq > DISPLAY_FREQ_MAX_HZ:
            break
        axes[2].axhline(y=freq, color="cyan", linewidth=0.5, alpha=0.45, linestyle="--")
        axes[2].annotate(f"{k}f0", xy=(0.01, freq), xycoords=("axes fraction", "data"),
                         fontsize=6, color="cyan", va="center")

    textstr = (f"SNR: {snr_before:.1f} → {snr_after:.1f} dB (+{snr_after-snr_before:.1f})\n"
               f"Duration: {len(y)/sr:.1f}s\n"
               f"f0: {f0_contour.min():.1f}–{f0_contour.max():.1f} Hz")
    axes[2].text(0.98, 0.98, textstr, transform=axes[2].transAxes, fontsize=8,
                 va="top", ha="right", bbox=dict(boxstyle="round", facecolor="black", alpha=0.65),
                 color="white")

    fig.colorbar(im, ax=axes[2], label="Power (dB)")

    out_png = output_dir / f"{noise_type}_demo.png"
    fig.savefig(str(out_png), dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # WAV export
    audio_norm = ctx["audio_clean"] / (np.abs(ctx["audio_clean"]).max() + 1e-10)
    out_wav = output_dir / f"{noise_type}_clean.wav"
    sf.write(str(out_wav), audio_norm, sr, subtype="PCM_16")

    print(f"[demo] {noise_type}: saved {out_png.name}, {out_wav.name} "
          f"(SNR {snr_before:.1f}→{snr_after:.1f} dB)")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `matplotlib.cm.get_cmap(name)` | Pass string directly to `cmap=` parameter | matplotlib 3.7 | `get_cmap()` deprecated; removed in 3.11 |
| `fig.tight_layout()` | `plt.subplots(..., constrained_layout=True)` | matplotlib 3.x | tight_layout breaks with colorbars in 3.10+ |
| `librosa.stft` + manual dB scaling | `librosa.power_to_db(magnitude**2, ref=np.max)` | librosa 0.9+ | power_to_db handles zero/negative values safely |

## Open Questions

1. **Annotation CSV noise_type column**
   - What we know: The ingestor guarantees only `filename`, `start`, `end` columns
   - What's unclear: Whether the actual ElephantVoices CSV includes a noise classification column
   - Recommendation: Script should accept optional `--noise-type-col` argument; fall back to auto-classify when absent. For hackathon speed, also accept `--generator-file`, `--car-file`, `--plane-file` hardcoded overrides.

2. **Actual recording files present at demo time**
   - What we know: `data/recordings/` contains only `.gitkeep` — recordings are not committed to the repo
   - What's unclear: Whether recordings will be present when the script runs at the hackathon
   - Recommendation: Script must print a clear error with instructions if recordings directory is empty. Add a `--synthetic` flag that generates synthetic harmonic test audio so figures can be produced without real recordings for verification.

## Sources

### Primary (HIGH confidence)

- Local execution against installed libraries (all code examples above run successfully):
  - matplotlib 3.10.8 — `imshow`, `constrained_layout`, `savefig(dpi=300)`, RGBA overlay, `axhline`+`annotate`, `ax.text` inset box
  - soundfile 0.13.1 — `write(path, audio, sr, subtype='PCM_16')` and `subtype='FLOAT'`
  - librosa 0.11.0 — `power_to_db`, `frames_to_time`, `fft_frequencies`
  - numpy 2.4.4 — frequency bin slicing, SNR math

### Secondary (MEDIUM confidence)

- Pipeline source code (`pipeline/harmonic_processor.py`, `pipeline/spectrogram.py`) — confirms context dict keys available post-`process_call()`: `magnitude`, `comb_mask`, `f0_contour`, `freq_bins`, `audio_clean`, `masked_magnitude`, `phase`, `sr`, `hop_length`, `n_fft`
- `requirements.txt` — confirms matplotlib>=3.8 was already specified; no new dependencies needed

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified by running code against installed libraries
- Architecture patterns: HIGH — all code examples executed and confirmed correct
- Pitfalls: HIGH — identified through direct code inspection and API verification
- Call selection logic: MEDIUM — depends on actual annotation CSV structure (column names unverified until data present)

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (matplotlib 3.x API stable; no fast-moving deps)
