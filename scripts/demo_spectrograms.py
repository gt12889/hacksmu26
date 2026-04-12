#!/usr/bin/env python3
"""
Demo spectrogram generator for ElephantVoices Denoiser.

Generates publication-quality before/after spectrogram figures and cleaned WAV
exports for one representative call per noise type (generator, car, plane).

Usage:
    # Synthetic mode (no real recordings required):
    python scripts/demo_spectrograms.py --synthetic --output-dir data/outputs/demo

    # Real recordings mode:
    python scripts/demo_spectrograms.py \\
        --annotations data/annotations.csv \\
        --recordings-dir data/recordings/ \\
        --output-dir data/outputs/demo

Output per noise type:
    {output_dir}/{noise_type}_demo.png   — 3-panel figure at 300 dpi
    {output_dir}/{noise_type}_clean.wav  — cleaned audio (PCM_16)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import librosa
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

# Allow running from repo root without installing as package
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from pipeline.config import HOP_LENGTH  # noqa: E402
from pipeline.harmonic_processor import process_call  # noqa: E402
from pipeline.ingestor import extract_noise_gaps, load_call_segment  # noqa: E402
from pipeline.noise_classifier import classify_noise_type  # noqa: E402
from pipeline.scoring import compute_snr_db  # noqa: E402
from pipeline.spectrogram import compute_stft  # noqa: E402

# ─── Constants ─────────────────────────────────────────────────────────────────

DISPLAY_FREQ_MAX_HZ = 500  # Hz — covers 35+ harmonics at 14 Hz f0
NOISE_TYPES = ["generator", "car", "plane"]
DEFAULT_SR = 44100


# ─── Synthetic call generator ──────────────────────────────────────────────────

def build_synthetic_call(
    noise_type: str,
    sr: int = DEFAULT_SR,
    duration: float = 6.0,
) -> tuple[np.ndarray, int, np.ndarray, dict]:
    """
    Generate a synthetic elephant-like harmonic signal for testing.

    Produces a signal at f0=14 Hz with harmonics up to 500 Hz, plus additive
    white noise at ~0 dB SNR. Includes a 1-second noise-only clip.

    Args:
        noise_type: One of "generator", "car", "plane"
        sr:         Sample rate (default 44100)
        duration:   Signal duration in seconds (default 6.0)

    Returns:
        (y, sr, noise_clip, noise_type_dict)
        - y:               float32 audio array of length int(duration * sr)
        - sr:              sample rate
        - noise_clip:      float32 white noise array of length int(1.0 * sr)
        - noise_type_dict: dict compatible with classify_noise_type() output
    """
    rng = np.random.default_rng(42)
    n_samples = int(duration * sr)
    t = np.linspace(0, duration, n_samples, dtype=np.float32)

    # Build harmonic signal: f0=14 Hz + harmonics up to 500 Hz
    f0 = 14.0
    harmonic_freqs = np.arange(f0, DISPLAY_FREQ_MAX_HZ + f0, f0)
    signal = np.zeros(n_samples, dtype=np.float64)
    for k, freq in enumerate(harmonic_freqs, start=1):
        # Taper higher harmonics (roll off amplitude with harmonic number)
        amplitude = 1.0 / k
        # Slight amplitude modulation for realism
        amplitude_mod = amplitude * (1.0 + 0.1 * np.sin(2 * np.pi * 0.5 * t))
        signal += amplitude_mod * np.sin(2 * np.pi * freq * t)

    # Add white noise at ~0 dB SNR relative to harmonic signal
    noise_level = np.std(signal)
    white_noise = rng.standard_normal(n_samples) * noise_level
    y = (signal + white_noise).astype(np.float32)

    # 1-second noise-only clip
    noise_clip = (rng.standard_normal(int(1.0 * sr)) * noise_level).astype(np.float32)

    noise_type_dict = {
        "type": noise_type,
        "spectral_flatness": 0.1,
        "low_freq_ratio": 0.4,
    }

    return y, sr, noise_clip, noise_type_dict


# ─── Figure and WAV export ─────────────────────────────────────────────────────

def make_demo_figure(
    noise_type: str,
    ctx: dict,
    y: np.ndarray,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    """
    Render 3-panel spectrogram figure and export cleaned WAV.

    Panels:
        1. Original — raw magnitude spectrogram
        2. Comb Mask — original + cyan RGBA overlay showing the comb mask
        3. Cleaned — clean magnitude + lime f0 contour + cyan dashed harmonic markers
                     + SNR/duration/f0-range text box

    All panels are clipped to 0-500 Hz (DISPLAY_FREQ_MAX_HZ).

    Args:
        noise_type:  Noise type label (for filenames and titles)
        ctx:         Context dict from process_call()
        y:           Original audio (for duration annotation and original WAV export)
        output_dir:  Directory to write PNG and WAV files

    Returns:
        (png_path, wav_path, wav_original_path) as Path objects
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sr = ctx["sr"]
    freq_bins = ctx["freq_bins"]
    f0_contour = ctx["f0_contour"]
    f0_median = float(np.median(f0_contour))

    # Frequency slice: keep only 0-500 Hz
    display_mask = freq_bins <= DISPLAY_FREQ_MAX_HZ
    freq_display = freq_bins[display_mask]

    # Time axis
    n_frames = ctx["magnitude"].shape[1]
    times = librosa.frames_to_time(
        np.arange(n_frames), sr=sr, hop_length=ctx["hop_length"]
    )

    # dB-scale magnitude slices (sliced to display freq range)
    def to_db(mag: np.ndarray) -> np.ndarray:
        return librosa.power_to_db(mag[display_mask, :] ** 2, ref=np.max)

    mag_orig_db = to_db(ctx["magnitude"])

    # Re-STFT on cleaned audio for the "Cleaned" panel
    ctx_clean = compute_stft(ctx["audio_clean"], sr)
    mag_clean_db = to_db(ctx_clean["magnitude"])

    # SNR before / after
    snr_before = compute_snr_db(ctx["magnitude"], freq_bins, f0_median)
    snr_after = compute_snr_db(ctx_clean["magnitude"], freq_bins, f0_median)

    # ── Figure layout ──────────────────────────────────────────────────────────
    # constrained_layout=True avoids tight_layout() warnings with colorbars
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)
    fig.suptitle(
        f"Noise type: {noise_type.upper()} — Elephant Call Denoising", fontsize=13
    )

    extent = [times[0], times[-1], float(freq_display[0]), float(freq_display[-1])]
    vmin, vmax = -80, 0

    def render_panel(ax: plt.Axes, mag_db: np.ndarray, title: str) -> plt.cm.ScalarMappable:
        im = ax.imshow(
            mag_db,
            aspect="auto",
            origin="lower",
            extent=extent,
            cmap="inferno",
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_xlabel("Time (s)", fontsize=10)
        ax.set_ylabel("Frequency (Hz)", fontsize=10)
        ax.set_title(title, fontsize=11)
        return im

    # Panel 1: Original
    render_panel(axes[0], mag_orig_db, "Original")

    # Panel 2: Comb Mask Overlay
    render_panel(axes[1], mag_orig_db, "Comb Mask Overlay")
    comb_display = ctx["comb_mask"][display_mask, :]
    overlay = np.zeros((*comb_display.shape, 4), dtype=np.float32)
    overlay[..., 0] = 0.0  # R
    overlay[..., 1] = 1.0  # G (cyan)
    overlay[..., 2] = 1.0  # B (cyan)
    overlay[..., 3] = comb_display * 0.6  # alpha
    axes[1].imshow(
        overlay,
        aspect="auto",
        origin="lower",
        extent=extent,
    )

    # Panel 3: Cleaned + f0 contour + harmonic markers + stats box
    im = render_panel(axes[2], mag_clean_db, "Cleaned")

    # f0 contour (lime line)
    axes[2].plot(times, f0_contour, color="lime", linewidth=1.5, alpha=0.9, label="f0")

    # Harmonic spacing markers (cyan dashed axhlines with kf0 labels)
    for k in range(1, 30):
        freq = k * f0_median
        if freq > DISPLAY_FREQ_MAX_HZ:
            break
        axes[2].axhline(
            y=freq, color="cyan", linewidth=0.5, alpha=0.45, linestyle="--"
        )
        axes[2].annotate(
            f"{k}f0",
            xy=(0.01, freq),
            xycoords=("axes fraction", "data"),
            fontsize=6,
            color="cyan",
            va="center",
        )

    # SNR / duration / f0-range text box (top-right corner)
    duration_sec = len(y) / sr
    textstr = (
        f"SNR: {snr_before:.1f} \u2192 {snr_after:.1f} dB (+{snr_after - snr_before:.1f})\n"
        f"Duration: {duration_sec:.1f}s\n"
        f"f0: {f0_contour.min():.1f}\u2013{f0_contour.max():.1f} Hz"
    )
    props = dict(boxstyle="round", facecolor="black", alpha=0.65)
    axes[2].text(
        0.98,
        0.98,
        textstr,
        transform=axes[2].transAxes,
        fontsize=8,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=props,
        color="white",
    )

    # Colorbar on panel 3 only
    fig.colorbar(im, ax=axes[2], label="Power (dB)")

    # ── Save figure ────────────────────────────────────────────────────────────
    out_png = output_dir / f"{noise_type}_demo.png"
    fig.savefig(str(out_png), dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # ── WAV export ─────────────────────────────────────────────────────────────
    audio_norm = ctx["audio_clean"] / (np.abs(ctx["audio_clean"]).max() + 1e-10)
    out_wav = output_dir / f"{noise_type}_clean.wav"
    sf.write(str(out_wav), audio_norm, sr, subtype="PCM_16")

    # ── Original WAV export (needed by frontend A/B toggle) ───────────────────
    y_norm = y / (np.abs(y).max() + 1e-10)
    out_wav_original = output_dir / f"{noise_type}_original.wav"
    sf.write(str(out_wav_original), y_norm, sr, subtype="PCM_16")

    print(
        f"[demo] {noise_type}: saved {out_png.name}, {out_wav.name}, {out_wav_original.name} "
        f"(SNR {snr_before:.1f}\u2192{snr_after:.1f} dB)"
    )

    return out_png, out_wav, out_wav_original


# ─── Call selection from annotations ──────────────────────────────────────────

def select_calls_from_annotations(
    annotations_path: Path,
    recordings_dir: Path,
    noise_type_col: str = "noise_type",
) -> dict[str, tuple[Path, float, float]]:
    """
    Select one representative call per noise type from annotations CSV/XLSX.

    Tries to read the noise_type column from the annotations file. Falls back
    to auto-classification via classify_noise_type() when column is absent.

    Args:
        annotations_path: Path to CSV or XLSX annotations file
        recordings_dir:   Directory containing WAV recordings
        noise_type_col:   Column name for noise type (default: "noise_type")

    Returns:
        dict mapping noise type to (wav_path, start_sec, end_sec)

    Raises:
        ValueError: If a noise type cannot be found in annotations
    """
    import pandas as pd

    # Load annotations
    if annotations_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(annotations_path, engine="openpyxl")
    else:
        df = pd.read_csv(annotations_path)

    # Normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    selected: dict[str, tuple[Path, float, float]] = {}

    if noise_type_col in df.columns:
        # Filter by noise_type column directly
        for nt in NOISE_TYPES:
            rows = df[df[noise_type_col].str.lower() == nt]
            if rows.empty:
                raise ValueError(
                    f"No annotation found for noise_type='{nt}'. "
                    f"Available types: {df[noise_type_col].unique().tolist()}"
                )
            row = rows.iloc[0]
            wav_path = recordings_dir / row["filename"]
            selected[nt] = (wav_path, float(row["start"]), float(row["end"]))
    else:
        # Auto-classify: run classifier on first noise gap per recording
        classified: dict[str, tuple[Path, float, float]] = {}
        for _, row in df.iterrows():
            wav_path = recordings_dir / row["filename"]
            if not wav_path.exists():
                continue
            start_sec, end_sec = float(row["start"]), float(row["end"])
            gaps = extract_noise_gaps(wav_path, [(start_sec, end_sec)], end_sec + 30.0)
            if not gaps:
                continue
            gap_start, gap_end = gaps[0]
            y_noise, sr = load_call_segment(wav_path, gap_start, gap_end, pad_seconds=0.0)
            result = classify_noise_type(y_noise, sr)
            nt = result["type"]
            if nt not in classified and nt in NOISE_TYPES:
                classified[nt] = (wav_path, start_sec, end_sec)
            if len(classified) == len(NOISE_TYPES):
                break
        for nt in NOISE_TYPES:
            if nt not in classified:
                raise ValueError(
                    f"Could not find a recording classified as '{nt}'. "
                    "Try adding --noise-type-col argument or check your annotations file."
                )
            selected[nt] = classified[nt]

    return selected


# ─── Main entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate publication-quality before/after spectrogram figures "
            "and cleaned WAV exports for one call per noise type."
        )
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=None,
        help="Path to annotation CSV or XLSX file (required unless --synthetic)",
    )
    parser.add_argument(
        "--recordings-dir",
        type=Path,
        default=None,
        help="Directory containing WAV recordings (required unless --synthetic)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/outputs/demo"),
        help="Directory to write PNG and WAV files (default: data/outputs/demo)",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use synthetic audio instead of real recordings (for testing)",
    )
    parser.add_argument(
        "--noise-type-col",
        default="noise_type",
        help="Column name for noise type in annotations (default: noise_type)",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.synthetic:
        # Synthetic mode: generate test audio for each noise type
        for nt in NOISE_TYPES:
            y, sr, noise_clip, noise_type_dict = build_synthetic_call(nt)
            ctx = process_call(y, sr, noise_type_dict, noise_clip=noise_clip)
            make_demo_figure(nt, ctx, y, output_dir)
    else:
        # Real recordings mode
        if args.annotations is None or args.recordings_dir is None:
            print(
                "[error] --annotations and --recordings-dir are required when --synthetic is not set.",
                file=sys.stderr,
            )
            sys.exit(1)
        if not args.recordings_dir.exists():
            print(
                f"[error] recordings-dir not found: {args.recordings_dir}",
                file=sys.stderr,
            )
            sys.exit(1)

        calls = select_calls_from_annotations(
            args.annotations, args.recordings_dir, args.noise_type_col
        )
        for nt, (wav_path, start_sec, end_sec) in calls.items():
            y, sr = load_call_segment(wav_path, start_sec, end_sec)
            # Load noise clip for generator stationary mode
            noise_clip: np.ndarray | None = None
            gaps = extract_noise_gaps(wav_path, [(start_sec, end_sec)], end_sec + 30.0)
            if gaps:
                gap_start, gap_end = gaps[0]
                noise_clip, _ = load_call_segment(wav_path, gap_start, gap_end, pad_seconds=0.0)
            # Classify noise type from noise clip or use auto-classify
            if noise_clip is not None:
                noise_type_dict = classify_noise_type(noise_clip, sr)
            else:
                # Fallback: use first 1.5s of call as noise estimate
                y_noise = y[: int(1.5 * sr)] if len(y) > int(1.5 * sr) else y
                noise_type_dict = classify_noise_type(y_noise, sr)
            # Override the classified type with the selection type (we chose this call for nt)
            noise_type_dict = dict(noise_type_dict)
            noise_type_dict["type"] = nt

            ctx = process_call(y, sr, noise_type_dict, noise_clip=noise_clip)
            make_demo_figure(nt, ctx, y, output_dir)

    print(f"[demo] Complete. Outputs in {output_dir}")


if __name__ == "__main__":
    main()
