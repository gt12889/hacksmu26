#!/usr/bin/env python3
"""
Multi-speaker separation demo for ElephantVoices Denoiser.

Mixes two synthetic elephant callers (14 Hz and 18 Hz fundamentals), runs the
multi-speaker separation pipeline, and produces the MULTI-04 figure plus per-caller
WAV exports.

Usage:
    python scripts/demo_multi_speaker.py --output-dir data/outputs/demo

Output:
    {output_dir}/multi_speaker_demo.png  — figure at 300 dpi
    {output_dir}/demo_caller_1.wav       — caller A reconstructed audio
    {output_dir}/demo_caller_2.wav       — caller B reconstructed audio
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Allow running from repo root without installing as package
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from pipeline.config import HOP_LENGTH  # noqa: E402
from pipeline.harmonic_processor import hpss_enhance  # noqa: E402
from pipeline.multi_speaker import (  # noqa: E402
    detect_f0_shs_topk,
    is_multi_speaker,
    link_f0_tracks,
    separate_speakers,
)
from pipeline.spectrogram import compute_stft  # noqa: E402

# ─── Constants ─────────────────────────────────────────────────────────────────

DISPLAY_FREQ_MAX_HZ = 500       # Hz — covers infrasonic + first ~35 harmonics
TRACK_COLORS = ["#FF4444", "#4488FF"]   # red=caller A, blue=caller B
DEFAULT_SR = 44100
DEFAULT_DURATION = 5.0
F0_A = 14.0   # Hz, caller A fundamental
F0_B = 18.0   # Hz, caller B fundamental


# ─── Synthetic call generator ──────────────────────────────────────────────────

def synth_harmonic(
    f0: float,
    n_harmonics: int = 10,
    sr: int = DEFAULT_SR,
    duration: float = DEFAULT_DURATION,
) -> np.ndarray:
    """
    Generate a synthetic elephant-like harmonic signal.

    Returns a normalized sum of sines at k*f0 for k=1..n_harmonics with
    amplitude 1/k (harmonic rolloff). Matches the test fixture used in
    tests/test_multi_speaker.py exactly.

    Args:
        f0:          Fundamental frequency in Hz
        n_harmonics: Number of harmonics to include (default 10)
        sr:          Sample rate (default 44100)
        duration:    Signal duration in seconds (default 5.0)

    Returns:
        Float64 audio array normalized to peak amplitude 1.0
    """
    n_samples = int(sr * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    signal = np.zeros(n_samples, dtype=np.float64)
    for k in range(1, n_harmonics + 1):
        signal += (1.0 / k) * np.sin(2 * np.pi * k * f0 * t)
    # Normalize to peak amplitude 1.0
    peak = np.abs(signal).max()
    if peak > 0:
        signal /= peak
    return signal


# ─── Demo runner ──────────────────────────────────────────────────────────────

def run_demo(output_dir: Path) -> None:
    """
    End-to-end multi-speaker demo: synthetic mixture → separate → figure + WAVs.

    Pipeline:
        1. Build y_mix = 0.5 * caller_A + 0.5 * caller_B
        2. compute_stft → STFT context
        3. hpss_enhance → adds magnitude_harmonic and hz_per_bin to ctx
        4. detect_f0_shs_topk → top-2 f0 candidates per frame
        5. is_multi_speaker → report result (note: gate unreliable on pure synthetics)
        6. link_f0_tracks → two stable f0 contours
        7. separate_speakers → per-caller comb-mask WAV files
        8. Plot MULTI-04 figure: log-magnitude spectrogram + two colored f0 tracks
    """
    print("[demo] Building synthetic two-caller mixture ...")
    y_a = synth_harmonic(F0_A)
    y_b = synth_harmonic(F0_B)
    y_mix = (0.5 * y_a + 0.5 * y_b).astype(np.float32)

    print("[demo] Computing STFT ...")
    ctx = compute_stft(y_mix, DEFAULT_SR)

    print("[demo] Running HPSS enhancement ...")
    ctx = hpss_enhance(ctx)

    print("[demo] Detecting top-2 f0 candidates per frame ...")
    top_k_f0s, top_k_scores = detect_f0_shs_topk(ctx, k=2)

    # Report is_multi_speaker gate result for informational purposes.
    # NOTE: The score-ratio gate is designed for real recordings with a genuine noise
    # floor. On pure synthetic harmonic signals, SHS aliases score near-equally
    # regardless of caller count, so the gate is unreliable. We proceed with
    # multi-speaker separation regardless to demonstrate the capability.
    multi_detected = is_multi_speaker(top_k_scores)
    if multi_detected:
        print("[demo] is_multi_speaker: True — two callers detected by score-ratio gate")
    else:
        print(
            "[demo] is_multi_speaker: False (expected for pure synthetic — "
            "SHS sub-harmonic aliases score near-equally; proceeding with separation)"
        )

    print("[demo] Linking f0 tracks ...")
    f0_tracks = link_f0_tracks(top_k_f0s, top_k_scores)

    print("[demo] Separating speakers ...")
    caller_ctxs = separate_speakers(ctx, f0_tracks, str(output_dir), "demo")

    # ── Build MULTI-04 figure ─────────────────────────────────────────────────
    print("[demo] Rendering figure ...")

    magnitude = ctx["magnitude"]
    n_freq_bins, n_frames = magnitude.shape

    # Frequency bins for slicing
    freq_bins = ctx["freq_bins"]
    display_mask = freq_bins <= DISPLAY_FREQ_MAX_HZ
    mag_display = magnitude[display_mask, :]

    # Log-magnitude for display
    mag_db = 20 * np.log10(mag_display + 1e-9)

    # Time axis
    time_axis = np.arange(n_frames) * HOP_LENGTH / DEFAULT_SR

    fig, ax = plt.subplots(figsize=(14, 5), constrained_layout=True)

    im = ax.imshow(
        mag_db,
        origin="lower",
        aspect="auto",
        cmap="magma",
        vmin=-80,
        vmax=0,
        extent=[0, n_frames * HOP_LENGTH / DEFAULT_SR, 0, DISPLAY_FREQ_MAX_HZ],
    )

    for i, (f0_contour, color) in enumerate(zip(f0_tracks, TRACK_COLORS)):
        mean_f0 = float(f0_contour.mean())
        ax.plot(
            time_axis,
            f0_contour,
            color=color,
            linewidth=2.5,
            label=f"Caller {i + 1}: {mean_f0:.1f} Hz mean f0",
        )

    ax.set_ylim(0, DISPLAY_FREQ_MAX_HZ)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("Multi-Speaker Separation — Two Simultaneous Elephant Callers")
    ax.legend(loc="upper right")
    fig.colorbar(im, ax=ax, label="Power (dB)")

    out_png = output_dir / "multi_speaker_demo.png"
    fig.savefig(str(out_png), dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ── Print summary ─────────────────────────────────────────────────────────
    for i, f0_contour in enumerate(f0_tracks):
        print(
            f"Caller {i + 1}: mean f0 = {float(f0_contour.mean()):.1f} Hz "
            f"→ demo_caller_{i + 1}.wav"
        )
    print(f"Figure: {out_png.name}")
    print(f"[demo] Complete. Outputs in {output_dir}")


# ─── Main entrypoint ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Multi-speaker separation demo: mixes two synthetic elephant callers "
            "and produces a figure + per-caller WAV files."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/outputs/demo"),
        help="Directory to write outputs (default: data/outputs/demo)",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    run_demo(output_dir)


if __name__ == "__main__":
    main()
