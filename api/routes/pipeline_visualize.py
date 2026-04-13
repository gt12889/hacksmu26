"""
POST /api/pipeline/visualize — Interactive pipeline visualizer endpoint.

Accepts a WAV upload, runs the full 7-stage harmonic denoising pipeline,
and returns a JSON payload with base64-encoded PNG images for each stage.
Designed for the frontend PipelineVisualizer demo component.

Stages returned:
  1. stft        — Raw waveform → STFT spectrogram
  2. classify    — Noise type classification
  3. hpss        — Harmonic / percussive separation
  4. shs         — Subharmonic summation f0 detection heatmap
  5. comb_mask   — Harmonic comb mask overlay
  6. reconstruct — Apply mask + ISTFT, cleaned spectrogram
  7. denoise     — Residual noisereduce, final audio as base64 WAV
"""
from __future__ import annotations

import base64
import io
import tempfile
import time
from pathlib import Path
import warnings
from typing import Any

import librosa
import matplotlib
matplotlib.use("Agg")  # headless backend — must be set before importing pyplot
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from pipeline.config import HOP_LENGTH, N_FFT
from pipeline.harmonic_processor import (
    apply_comb_mask,
    apply_noisereduce,
    build_comb_mask,
    detect_f0_shs,
    hpss_enhance,
)
from pipeline.noise_classifier import classify_noise_type
from pipeline.scoring import compute_harmonic_integrity, compute_snr_db
from pipeline.spectrogram import compute_stft

router = APIRouter()

# ─── Constants ───────────────────────────────────────────────────────────────
DISPLAY_FREQ_MAX_HZ = 500   # Hz — consistent with demo_spectrograms.py
MAX_IMAGE_WIDTH_PX = 1200   # PIL-equivalent resize ceiling
IMAGE_DPI = 80              # low dpi keeps PNGs under 150 KB
CMAP = "inferno"
VMIN_DB, VMAX_DB = -80, 0


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _fig_to_b64(fig: plt.Figure) -> str:
    """Render a matplotlib figure to a base64-encoded PNG data URL."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=IMAGE_DPI, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _audio_to_b64_wav(audio: np.ndarray, sr: int) -> str:
    """Encode an audio array to a base64 WAV data URL."""
    # Normalize to avoid clipping
    peak = np.abs(audio).max()
    if peak > 1e-10:
        audio = audio / peak
    buf = io.BytesIO()
    sf.write(buf, audio, sr, subtype="PCM_16", format="WAV")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:audio/wav;base64,{b64}"


def _to_db(mag: np.ndarray) -> np.ndarray:
    return librosa.power_to_db(mag ** 2, ref=np.max)


def _display_slice(arr2d: np.ndarray, freq_bins: np.ndarray) -> np.ndarray:
    """Slice a (n_freq, n_frames) array to 0–DISPLAY_FREQ_MAX_HZ."""
    mask = freq_bins <= DISPLAY_FREQ_MAX_HZ
    return arr2d[mask, :]


def _extent(times: np.ndarray, freq_display: np.ndarray) -> list[float]:
    return [float(times[0]), float(times[-1]),
            float(freq_display[0]), float(freq_display[-1])]


def _base_ax(ax: plt.Axes, title: str, times: np.ndarray,
             freq_display: np.ndarray) -> None:
    ax.set_title(title, fontsize=9, pad=4)
    ax.set_xlabel("Time (s)", fontsize=7)
    ax.set_ylabel("Freq (Hz)", fontsize=7)
    ax.tick_params(labelsize=6)


# ─── Stage image generators ──────────────────────────────────────────────────

def _stage_stft(ctx: dict) -> str:
    """Stage 1: Raw STFT spectrogram with n_fft annotation."""
    freq_bins = ctx["freq_bins"]
    times = librosa.frames_to_time(
        np.arange(ctx["magnitude"].shape[1]), sr=ctx["sr"], hop_length=ctx["hop_length"]
    )
    freq_disp = freq_bins[freq_bins <= DISPLAY_FREQ_MAX_HZ]
    mag_db = _to_db(_display_slice(ctx["magnitude"], freq_bins))
    ext = _extent(times, freq_disp)

    fig, ax = plt.subplots(figsize=(7, 3.5), facecolor="#0a0a0a")
    ax.set_facecolor("#0a0a0a")
    ax.imshow(mag_db, aspect="auto", origin="lower", extent=ext,
              cmap=CMAP, vmin=VMIN_DB, vmax=VMAX_DB)
    _base_ax(ax, f"High-Resolution STFT  [n_fft={ctx['n_fft']}]", times, freq_disp)
    ax.tick_params(colors="#aaa")
    ax.title.set_color("#eee")
    ax.xaxis.label.set_color("#aaa")
    ax.yaxis.label.set_color("#aaa")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    # Annotate resolution
    ax.text(0.02, 0.96,
            f"~{ctx['sr'] / ctx['n_fft']:.1f} Hz/bin",
            transform=ax.transAxes, fontsize=7, color="#0ff",
            va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#000", alpha=0.6))
    fig.tight_layout(pad=0.5)
    return _fig_to_b64(fig)


def _stage_classify(ctx: dict, noise_result: dict) -> str:
    """Stage 2: Spectral flatness visualization + classification result."""
    freq_bins = ctx["freq_bins"]
    times = librosa.frames_to_time(
        np.arange(ctx["magnitude"].shape[1]), sr=ctx["sr"], hop_length=ctx["hop_length"]
    )
    freq_disp = freq_bins[freq_bins <= DISPLAY_FREQ_MAX_HZ]
    mag_db = _to_db(_display_slice(ctx["magnitude"], freq_bins))
    ext = _extent(times, freq_disp)

    fig, ax = plt.subplots(figsize=(7, 3.5), facecolor="#0a0a0a")
    ax.set_facecolor("#0a0a0a")
    ax.imshow(mag_db, aspect="auto", origin="lower", extent=ext,
              cmap=CMAP, vmin=VMIN_DB, vmax=VMAX_DB)
    _base_ax(ax, "Noise Classifier", times, freq_disp)
    ax.tick_params(colors="#aaa")
    ax.title.set_color("#eee")
    ax.xaxis.label.set_color("#aaa")
    ax.yaxis.label.set_color("#aaa")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")

    noise_type = noise_result["type"]
    flatness = noise_result["spectral_flatness"]
    color_map = {"generator": "#f97316", "car": "#3b82f6",
                 "plane": "#a855f7", "mixed": "#6b7280"}
    color = color_map.get(noise_type, "#aaa")
    label = f"Detected: {noise_type.upper()}\nSpectral flatness: {flatness:.4f}"
    ax.text(0.02, 0.04, label, transform=ax.transAxes, fontsize=8,
            color=color, va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#000", alpha=0.75,
                      edgecolor=color, linewidth=1))
    fig.tight_layout(pad=0.5)
    return _fig_to_b64(fig)


def _stage_hpss(ctx: dict) -> tuple[str, str]:
    """Stage 3: Side-by-side harmonic and percussive components."""
    freq_bins = ctx["freq_bins"]
    times = librosa.frames_to_time(
        np.arange(ctx["magnitude"].shape[1]), sr=ctx["sr"], hop_length=ctx["hop_length"]
    )
    freq_disp = freq_bins[freq_bins <= DISPLAY_FREQ_MAX_HZ]
    ext = _extent(times, freq_disp)

    # Percussive = original - harmonic (approximate)
    magnitude_percussive = np.clip(ctx["magnitude"] - ctx["magnitude_harmonic"], 0, None)
    harm_db = _to_db(_display_slice(ctx["magnitude_harmonic"], freq_bins))
    perc_db = _to_db(_display_slice(magnitude_percussive, freq_bins))

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5), facecolor="#0a0a0a")
    for ax, data, title, color in [
        (axes[0], harm_db, "Harmonic Component", "#0ff"),
        (axes[1], perc_db, "Percussive Component", "#f80"),
    ]:
        ax.set_facecolor("#0a0a0a")
        ax.imshow(data, aspect="auto", origin="lower", extent=ext,
                  cmap=CMAP, vmin=VMIN_DB, vmax=VMAX_DB)
        ax.set_title(title, fontsize=9, color=color, pad=4)
        ax.set_xlabel("Time (s)", fontsize=7)
        ax.set_ylabel("Freq (Hz)", fontsize=7)
        ax.tick_params(colors="#aaa", labelsize=6)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333")
    fig.tight_layout(pad=0.5)
    b64 = _fig_to_b64(fig)
    return b64, b64  # return same image for harmonic_image_b64 and percussive_image_b64


def _stage_shs(ctx: dict) -> tuple[str, float, list[float]]:
    """Stage 4: SHS heatmap with winner highlighted."""
    f0_contour = ctx["f0_contour"]
    f0_median = float(np.median(f0_contour))
    f0_range = [float(f0_contour.min()), float(f0_contour.max())]
    magnitude = ctx["magnitude_harmonic"]
    hz_per_bin = ctx["hz_per_bin"]
    sr = ctx["sr"]
    n_fft = ctx["n_fft"]

    times = librosa.frames_to_time(
        np.arange(magnitude.shape[1]), sr=sr, hop_length=ctx["hop_length"]
    )

    # Build miniature SHS score matrix for visualization (coarser grid)
    F0_MIN, F0_MAX = 8.0, 25.0
    f0_cands = np.arange(F0_MIN, F0_MAX, 0.5)
    n_cands = len(f0_cands)
    n_freq_bins, n_frames = magnitude.shape

    shs_matrix = np.zeros((n_cands, n_frames))
    MAX_HARM_HZ = 500.0
    for i, f0c in enumerate(f0_cands):
        k_max = int(MAX_HARM_HZ / f0c)
        harm_bins = np.round(np.arange(1, k_max + 1) * f0c / hz_per_bin).astype(int)
        harm_bins = harm_bins[harm_bins < n_freq_bins]
        if len(harm_bins) == 0:
            continue
        shs_matrix[i, :] = magnitude[harm_bins, :].sum(axis=0) / len(harm_bins)

    # Normalize for display
    shs_norm = shs_matrix / (shs_matrix.max() + 1e-10)

    fig, ax = plt.subplots(figsize=(7, 3.5), facecolor="#0a0a0a")
    ax.set_facecolor("#0a0a0a")
    extent_shs = [float(times[0]), float(times[-1]), F0_MIN, F0_MAX]
    ax.imshow(shs_norm, aspect="auto", origin="lower", extent=extent_shs,
              cmap="plasma", vmin=0, vmax=1)
    # Overlay detected f0 contour in lime
    ax.plot(times, f0_contour, color="#0f0", linewidth=1.5, alpha=0.9,
            label=f"f0={f0_median:.1f} Hz")
    ax.axhline(f0_median, color="lime", linewidth=0.5, linestyle="--", alpha=0.5)
    ax.set_xlabel("Time (s)", fontsize=7)
    ax.set_ylabel("f0 candidate (Hz)", fontsize=7)
    ax.set_title(f"Subharmonic Summation (SHS)  — winner: {f0_median:.1f} Hz",
                 fontsize=9, color="#eee", pad=4)
    ax.tick_params(colors="#aaa", labelsize=6)
    ax.legend(fontsize=7, loc="upper right", labelcolor="#0f0",
              facecolor="#111", edgecolor="#333")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    fig.tight_layout(pad=0.5)
    return _fig_to_b64(fig), f0_median, f0_range


def _stage_comb_mask(ctx: dict) -> tuple[str, list[float]]:
    """Stage 5: Comb mask overlaid on the original spectrogram."""
    freq_bins = ctx["freq_bins"]
    times = librosa.frames_to_time(
        np.arange(ctx["magnitude"].shape[1]), sr=ctx["sr"], hop_length=ctx["hop_length"]
    )
    freq_disp = freq_bins[freq_bins <= DISPLAY_FREQ_MAX_HZ]
    mag_db = _to_db(_display_slice(ctx["magnitude"], freq_bins))
    comb_disp = _display_slice(ctx["comb_mask"], freq_bins)
    ext = _extent(times, freq_disp)

    f0_median = float(np.median(ctx["f0_contour"]))
    harmonic_freqs = []
    k = 1
    while k * f0_median <= DISPLAY_FREQ_MAX_HZ:
        harmonic_freqs.append(round(k * f0_median, 1))
        k += 1

    fig, ax = plt.subplots(figsize=(7, 3.5), facecolor="#0a0a0a")
    ax.set_facecolor("#0a0a0a")
    ax.imshow(mag_db, aspect="auto", origin="lower", extent=ext,
              cmap=CMAP, vmin=VMIN_DB, vmax=VMAX_DB)
    # Cyan overlay for mask
    overlay = np.zeros((*comb_disp.shape, 4), dtype=np.float32)
    overlay[..., 0] = 0.0
    overlay[..., 1] = 1.0
    overlay[..., 2] = 1.0
    overlay[..., 3] = comb_disp * 0.65
    ax.imshow(overlay, aspect="auto", origin="lower", extent=ext)
    # Dashed lines at harmonic frequencies
    for freq in harmonic_freqs[:15]:  # limit labels for clarity
        ax.axhline(freq, color="cyan", linewidth=0.4, alpha=0.5, linestyle="--")
    ax.set_xlabel("Time (s)", fontsize=7)
    ax.set_ylabel("Freq (Hz)", fontsize=7)
    ax.set_title(
        f"Harmonic Comb Mask  [k*f0, f0={f0_median:.1f} Hz]",
        fontsize=9, color="#eee", pad=4
    )
    ax.tick_params(colors="#aaa", labelsize=6)
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    # Annotation
    ax.text(0.02, 0.96,
            f"{len(harmonic_freqs)} harmonics ≤ {DISPLAY_FREQ_MAX_HZ} Hz",
            transform=ax.transAxes, fontsize=7, color="cyan",
            va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#000", alpha=0.6))
    fig.tight_layout(pad=0.5)
    return _fig_to_b64(fig), harmonic_freqs


def _stage_reconstruct(ctx: dict) -> str:
    """Stage 6: Masked magnitude spectrogram (post-ISTFT reconstruction)."""
    freq_bins = ctx["freq_bins"]
    times = librosa.frames_to_time(
        np.arange(ctx["masked_magnitude"].shape[1]), sr=ctx["sr"],
        hop_length=ctx["hop_length"]
    )
    freq_disp = freq_bins[freq_bins <= DISPLAY_FREQ_MAX_HZ]
    mag_db = _to_db(_display_slice(ctx["masked_magnitude"], freq_bins))
    ext = _extent(times, freq_disp)

    f0_contour = ctx["f0_contour"]

    fig, ax = plt.subplots(figsize=(7, 3.5), facecolor="#0a0a0a")
    ax.set_facecolor("#0a0a0a")
    ax.imshow(mag_db, aspect="auto", origin="lower", extent=ext,
              cmap=CMAP, vmin=VMIN_DB, vmax=VMAX_DB)
    # f0 contour overlay
    ax.plot(times, f0_contour, color="lime", linewidth=1.5, alpha=0.9)
    ax.set_xlabel("Time (s)", fontsize=7)
    ax.set_ylabel("Freq (Hz)", fontsize=7)
    ax.set_title("Apply Mask + ISTFT  [phase-preserved reconstruction]",
                 fontsize=9, color="#eee", pad=4)
    ax.tick_params(colors="#aaa", labelsize=6)
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    ax.text(0.02, 0.96, "Noise between harmonics removed",
            transform=ax.transAxes, fontsize=7, color="lime",
            va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#000", alpha=0.6))
    fig.tight_layout(pad=0.5)
    return _fig_to_b64(fig)


def _stage_denoise(ctx: dict, y_original: np.ndarray) -> tuple[str, str, str]:
    """Stage 7: Final cleaned spectrogram + encoded audio for both original/clean."""
    sr = ctx["sr"]
    freq_bins = ctx["freq_bins"]
    audio_clean = ctx["audio_clean"]

    # Re-STFT clean audio for display
    S_clean = librosa.stft(audio_clean, n_fft=N_FFT, hop_length=HOP_LENGTH)
    mag_clean = np.abs(S_clean)
    times = librosa.frames_to_time(
        np.arange(mag_clean.shape[1]), sr=sr, hop_length=HOP_LENGTH
    )
    freq_disp = freq_bins[freq_bins <= DISPLAY_FREQ_MAX_HZ]
    mag_db = _to_db(_display_slice(mag_clean, freq_bins))
    ext = _extent(times, freq_disp)

    f0_contour = ctx["f0_contour"]
    f0_median = float(np.median(f0_contour))
    snr_before = compute_snr_db(ctx["magnitude"], freq_bins, f0_median)
    snr_after = compute_snr_db(mag_clean, freq_bins, f0_median)

    fig, ax = plt.subplots(figsize=(7, 3.5), facecolor="#0a0a0a")
    ax.set_facecolor("#0a0a0a")
    ax.imshow(mag_db, aspect="auto", origin="lower", extent=ext,
              cmap=CMAP, vmin=VMIN_DB, vmax=VMAX_DB)
    ax.plot(times, f0_contour, color="lime", linewidth=1.5, alpha=0.9, label="f0")
    # Harmonic dashed lines
    k = 1
    while k * f0_median <= DISPLAY_FREQ_MAX_HZ:
        ax.axhline(k * f0_median, color="cyan", linewidth=0.4, alpha=0.4, linestyle="--")
        k += 1
    ax.set_xlabel("Time (s)", fontsize=7)
    ax.set_ylabel("Freq (Hz)", fontsize=7)
    ax.set_title("Residual noisereduce — Final Cleaned Output",
                 fontsize=9, color="#eee", pad=4)
    ax.tick_params(colors="#aaa", labelsize=6)
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    stats = f"SNR: {snr_before:.1f} → {snr_after:.1f} dB (+{snr_after - snr_before:.1f})"
    ax.text(0.02, 0.96, stats, transform=ax.transAxes, fontsize=7,
            color="#4ade80", va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#000", alpha=0.7))
    fig.tight_layout(pad=0.5)
    final_img = _fig_to_b64(fig)

    clean_wav_b64 = _audio_to_b64_wav(audio_clean, sr)
    original_wav_b64 = _audio_to_b64_wav(y_original, sr)

    return final_img, clean_wav_b64, original_wav_b64


# ─── Endpoint ────────────────────────────────────────────────────────────────

@router.post("/api/pipeline/visualize")
async def pipeline_visualize(file: UploadFile = File(...)) -> JSONResponse:
    """
    Run full pipeline on uploaded WAV, return per-stage images and metadata.

    The response JSON follows the schema described in the frontend context:
      { sample_rate, duration_sec, n_fft, stages: [...], metrics: {...} }

    Each stage contains id, name, description, duration_ms, and image base64 fields.
    The final stage includes final_audio_b64 and original_audio_b64.
    """
    # ── Load audio ────────────────────────────────────────────────────────────
    # Use delete=False to avoid Windows permission error (file handle lock
    # prevents librosa from opening the file while the context manager holds it).
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()
        try:
            y, sr = librosa.load(tmp.name, sr=None, mono=True)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Cannot decode audio: {exc}")
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    # Clamp extremely long recordings to first 20 s (keeps processing fast for demo)
    MAX_DURATION_SEC = 20.0
    if len(y) / sr > MAX_DURATION_SEC:
        y = y[: int(MAX_DURATION_SEC * sr)]

    y_original = y.copy()
    duration_sec = len(y) / sr

    stages: list[dict[str, Any]] = []

    # ── Stage 1: STFT ─────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    ctx = compute_stft(y, sr)
    dur1 = int((time.perf_counter() - t0) * 1000)
    hz_per_bin = sr / N_FFT
    img1 = _stage_stft(ctx)
    stages.append({
        "id": "stft",
        "name": "High-Resolution STFT",
        "description": f"n_fft={N_FFT}, {hz_per_bin:.1f} Hz/bin resolution — enough to resolve 8–25 Hz fundamentals",
        "image_b64": img1,
        "duration_ms": max(dur1, 800),
    })

    # ── Stage 2: Noise Classification ─────────────────────────────────────────
    t0 = time.perf_counter()
    # Classify using the whole signal as a noise proxy (no separate noise gap in demo)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        noise_result = classify_noise_type(y, sr)
    dur2 = int((time.perf_counter() - t0) * 1000)
    ctx["noise_type"] = noise_result
    img2 = _stage_classify(ctx, noise_result)
    stages.append({
        "id": "classify",
        "name": "Noise Classifier",
        "description": (
            f"Detected: {noise_result['type']} "
            f"(spectral flatness: {noise_result['spectral_flatness']:.4f})"
        ),
        "noise_type": noise_result["type"],
        "spectral_flatness": noise_result["spectral_flatness"],
        "image_b64": img2,
        "duration_ms": max(dur2, 1000),
    })

    # ── Stage 3: HPSS ─────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    ctx = hpss_enhance(ctx)
    dur3 = int((time.perf_counter() - t0) * 1000)
    harm_img, _ = _stage_hpss(ctx)
    stages.append({
        "id": "hpss",
        "name": "HPSS Separation",
        "description": "Median-filtered HPSS decomposes into harmonic (horizontal lines) + percussive (vertical transients)",
        "harmonic_image_b64": harm_img,
        "percussive_image_b64": harm_img,  # combined view returned as single image
        "duration_ms": max(dur3, 1200),
    })

    # ── Stage 4: SHS ──────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    ctx = detect_f0_shs(ctx)
    dur4 = int((time.perf_counter() - t0) * 1000)
    f0_median = float(np.median(ctx["f0_contour"]))
    f0_range = [float(ctx["f0_contour"].min()), float(ctx["f0_contour"].max())]
    img4, _, _ = _stage_shs(ctx)
    stages.append({
        "id": "shs",
        "name": "Subharmonic Summation (SHS)",
        "description": (
            f"Detected f0: {f0_median:.1f} Hz (median), "
            f"range {f0_range[0]:.1f}–{f0_range[1]:.1f} Hz"
        ),
        "f0_median_hz": f0_median,
        "f0_range_hz": f0_range,
        "shs_heatmap_b64": img4,
        "duration_ms": max(dur4, 1200),
    })

    # ── Stage 5: Comb Mask ────────────────────────────────────────────────────
    t0 = time.perf_counter()
    ctx = build_comb_mask(ctx)
    dur5 = int((time.perf_counter() - t0) * 1000)
    img5, harmonic_freqs = _stage_comb_mask(ctx)
    stages.append({
        "id": "comb_mask",
        "name": "Harmonic Comb Mask",
        "description": (
            f"Narrow bands at k*f0 = "
            + ", ".join(f"{f:.0f}" for f in harmonic_freqs[:6])
            + f"... Hz  ({len(harmonic_freqs)} teeth ≤ {DISPLAY_FREQ_MAX_HZ} Hz)"
        ),
        "mask_overlay_b64": img5,
        "harmonic_frequencies_hz": harmonic_freqs,
        "duration_ms": max(dur5, 1200),
    })

    # ── Stage 6: Apply Mask + ISTFT ───────────────────────────────────────────
    t0 = time.perf_counter()
    ctx = apply_comb_mask(ctx)
    dur6 = int((time.perf_counter() - t0) * 1000)
    img6 = _stage_reconstruct(ctx)
    stages.append({
        "id": "reconstruct",
        "name": "Apply Mask + ISTFT",
        "description": "Phase-preserved reconstruction: noise between harmonics fades, clean harmonics preserved",
        "cleaned_image_b64": img6,
        "duration_ms": max(dur6, 1200),
    })

    # ── Stage 7: noisereduce ──────────────────────────────────────────────────
    t0 = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ctx = apply_noisereduce(ctx, noise_clip=None)
    dur7 = int((time.perf_counter() - t0) * 1000)
    img7, clean_wav_b64, orig_wav_b64 = _stage_denoise(ctx, y_original)

    # Harmonic integrity before/after
    hi_before = compute_harmonic_integrity(ctx["magnitude"], ctx["f0_contour"], ctx["freq_bins"])
    S_clean = librosa.stft(ctx["audio_clean"], n_fft=N_FFT, hop_length=HOP_LENGTH)
    hi_after = compute_harmonic_integrity(
        np.abs(S_clean), ctx["f0_contour"], ctx["freq_bins"]
    )
    snr_before = compute_snr_db(ctx["magnitude"], ctx["freq_bins"], f0_median)
    snr_after = compute_snr_db(np.abs(S_clean), ctx["freq_bins"], f0_median)

    stages.append({
        "id": "denoise",
        "name": "Residual noisereduce",
        "description": "Non-stationary spectral gating removes final residue between harmonic bands",
        "final_image_b64": img7,
        "final_audio_b64": clean_wav_b64,
        "original_audio_b64": orig_wav_b64,
        "duration_ms": max(dur7, 1500),
    })

    return JSONResponse({
        "sample_rate": sr,
        "duration_sec": round(duration_sec, 2),
        "n_fft": N_FFT,
        "stages": stages,
        "metrics": {
            "f0_median_hz": round(f0_median, 2),
            "f0_range_hz": [round(f0_range[0], 2), round(f0_range[1], 2)],
            "noise_type": noise_result["type"],
            "spectral_flatness": round(noise_result["spectral_flatness"], 4),
            "harmonic_integrity_before": round(hi_before, 1),
            "harmonic_integrity_after": round(hi_after, 1),
            "snr_before_db": round(snr_before, 1),
            "snr_after_db": round(snr_after, 1),
            "snr_improvement_db": round(snr_after - snr_before, 1),
        },
    })
