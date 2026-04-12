#!/usr/bin/env python3
"""
Multi-speaker separation demo using REAL overlapping elephant rumbles.

Searches the ElephantVoices dataset annotations (data/annotations.xlsx) for
pairs of rumble calls in the same recording that overlap in time. The pair
with the longest overlap is selected and the full overlapping window is loaded.

Strategy:
  1. Parse annotations.xlsx → find overlapping [start, end] windows within the same WAV file.
  2. Select the pair with the longest overlap duration where the WAV file exists.
  3. Load the combined window (both callers present simultaneously) at native sample rate.
  4. Run: compute_stft → hpss_enhance → detect_f0_shs_topk → link_f0_tracks → separate_speakers.
  5. Produce figure + per-caller WAV files.

Fallback (if no natural overlaps with existing WAV files are found):
  Mix two single-caller calls from different recordings at the same sample rate,
  sum them, and run the multi-speaker pipeline on the synthetic mixture.
  This fallback is documented clearly in the output.

Usage:
    python scripts/demo_multi_speaker_real.py --output-dir data/outputs/demo

Output:
    {output_dir}/multi_speaker_real_demo.png   — spectrogram + 2 colored f0 tracks
    {output_dir}/multi_speaker_real.png        — alias copy for frontend
    {output_dir}/real_caller_1.wav             — separated caller A audio
    {output_dir}/real_caller_2.wav             — separated caller B audio
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import librosa
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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

DISPLAY_FREQ_MAX_HZ = 500
TRACK_COLORS = ["#FF4444", "#4488FF"]   # red=caller A, blue=caller B
ANNOTATIONS_PATH = _repo_root / "data" / "annotations.xlsx"
RECORDINGS_DIR = _repo_root / "data" / "recordings" / "real"
CONTEXT_PAD_SEC = 1.0  # seconds of audio before/after the overlap window


# ─── Annotation helpers ────────────────────────────────────────────────────────

def load_annotations() -> pd.DataFrame:
    """Load and normalize annotations.xlsx."""
    df = pd.read_excel(ANNOTATIONS_PATH, engine="openpyxl")
    df.columns = df.columns.str.lower().str.strip()
    aliases = {"sound_file": "filename", "start_time": "start", "end_time": "end"}
    df = df.rename(columns={k: v for k, v in aliases.items() if k in df.columns})
    return df


def find_best_overlap(df: pd.DataFrame) -> dict | None:
    """
    Find the overlapping call pair with the longest overlap in time where the
    source WAV file exists on disk.

    Returns a dict with keys: filename, call_a_start, call_a_end, call_b_start,
    call_b_end, overlap_duration, window_start, window_end.
    Returns None if no valid overlapping pair is found.
    """
    best: dict | None = None

    for fname, group in df.groupby("filename"):
        wav_path = RECORDINGS_DIR / fname
        if not wav_path.exists():
            continue

        rows = group.sort_values("start").reset_index(drop=True)
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a = rows.iloc[i]
                b = rows.iloc[j]
                overlap_start = max(float(a.start), float(b.start))
                overlap_end = min(float(a.end), float(b.end))
                if overlap_end <= overlap_start:
                    continue
                overlap_duration = overlap_end - overlap_start
                if best is None or overlap_duration > best["overlap_duration"]:
                    best = {
                        "filename": str(fname),
                        "call_a_start": float(a.start),
                        "call_a_end": float(a.end),
                        "call_b_start": float(b.start),
                        "call_b_end": float(b.end),
                        "overlap_duration": overlap_duration,
                        "window_start": max(0.0, min(float(a.start), float(b.start)) - CONTEXT_PAD_SEC),
                        "window_end": max(float(a.end), float(b.end)) + CONTEXT_PAD_SEC,
                    }

    return best


def load_fallback_mix(df: pd.DataFrame) -> tuple[np.ndarray, int, str]:
    """
    Fallback: mix two independent single-caller calls from different recordings.

    Finds two calls from different WAV files, loads each at native sample rate,
    resamples the second to match the first if needed, pads/trims to same length,
    and sums them.

    Returns (y_mix, sr, description_string).
    """
    calls = []
    for fname, group in df.groupby("filename"):
        wav_path = RECORDINGS_DIR / fname
        if not wav_path.exists():
            continue
        row = group.sort_values("start").iloc[0]
        calls.append({
            "filename": str(fname),
            "start": float(row.start),
            "end": float(row.end),
            "wav_path": wav_path,
        })
        if len(calls) >= 2:
            break

    if len(calls) < 2:
        raise RuntimeError("Cannot find two calls with existing WAV files for fallback mixing.")

    a_info, b_info = calls[0], calls[1]

    y_a, sr_a = librosa.load(
        str(a_info["wav_path"]),
        sr=None,
        offset=a_info["start"],
        duration=a_info["end"] - a_info["start"],
    )
    y_b, sr_b = librosa.load(
        str(b_info["wav_path"]),
        sr=None,
        offset=b_info["start"],
        duration=b_info["end"] - b_info["start"],
    )

    # Resample b to match a's sample rate if needed
    if sr_b != sr_a:
        y_b = librosa.resample(y_b, orig_sr=sr_b, target_sr=sr_a)

    # Pad / trim so both are the same length
    n = min(len(y_a), len(y_b))
    y_a = y_a[:n]
    y_b = y_b[:n]

    y_mix = (0.5 * y_a + 0.5 * y_b).astype(np.float32)
    desc = (
        f"FALLBACK MIX: {a_info['filename']} t={a_info['start']:.1f}s "
        f"+ {b_info['filename']} t={b_info['start']:.1f}s"
    )
    return y_mix, sr_a, desc


# ─── Demo runner ──────────────────────────────────────────────────────────────

def run_demo(output_dir: Path) -> None:
    """
    End-to-end multi-speaker demo using real overlapping elephant rumbles.

    Pipeline:
        1. Parse annotations.xlsx → find best overlapping call window
        2. Load audio window at native sample rate (sr=None)
        3. compute_stft → STFT context
        4. hpss_enhance → adds magnitude_harmonic + hz_per_bin
        5. detect_f0_shs_topk → top-2 f0 candidates per frame
        6. is_multi_speaker → score-ratio gate result (informational)
        7. link_f0_tracks → two stable f0 contours
        8. separate_speakers → per-caller comb-mask WAV files
        9. Plot figure: log-magnitude spectrogram + two colored f0 tracks
    """
    print("[demo] Loading annotations ...")
    df = load_annotations()
    print(f"[demo] {len(df)} annotated calls across {df['filename'].nunique()} recordings")

    # ── Step 1: Find or build the overlapping audio ───────────────────────────
    overlap = find_best_overlap(df)
    used_fallback = False
    fallback_desc = ""

    if overlap is not None:
        wav_path = RECORDINGS_DIR / overlap["filename"]
        print(
            f"[demo] Found natural overlap in {overlap['filename']}: "
            f"{overlap['overlap_duration']:.2f}s overlap"
        )
        print(f"       Call A: [{overlap['call_a_start']:.2f}s – {overlap['call_a_end']:.2f}s]")
        print(f"       Call B: [{overlap['call_b_start']:.2f}s – {overlap['call_b_end']:.2f}s]")
        print(
            f"       Loading window [{overlap['window_start']:.2f}s – "
            f"{overlap['window_end']:.2f}s] (with ±{CONTEXT_PAD_SEC:.1f}s padding)"
        )

        y, sr = librosa.load(
            str(wav_path),
            sr=None,
            offset=overlap["window_start"],
            duration=overlap["window_end"] - overlap["window_start"],
        )
        y = y.astype(np.float32)
        source_description = (
            f"{overlap['filename']} "
            f"[{overlap['window_start']:.2f}s – {overlap['window_end']:.2f}s]"
        )
        call_a_rel_start = overlap["call_a_start"] - overlap["window_start"]
        call_b_rel_start = overlap["call_b_start"] - overlap["window_start"]
    else:
        print("[demo] No natural overlaps found with existing WAV files — using fallback mix ...")
        y, sr, fallback_desc = load_fallback_mix(df)
        used_fallback = True
        source_description = fallback_desc
        call_a_rel_start = None
        call_b_rel_start = None

    print(f"[demo] Loaded audio: {len(y)/sr:.2f}s at {sr} Hz")

    # ── Step 2–4: STFT + HPSS ────────────────────────────────────────────────
    print("[demo] Computing STFT ...")
    ctx = compute_stft(y, sr)

    print("[demo] Running HPSS enhancement ...")
    ctx = hpss_enhance(ctx)

    # ── Step 5: Top-2 f0 detection ────────────────────────────────────────────
    print("[demo] Detecting top-2 f0 candidates per frame ...")
    top_k_f0s, top_k_scores = detect_f0_shs_topk(ctx, k=2)

    multi_detected = is_multi_speaker(top_k_scores)
    if multi_detected:
        print("[demo] is_multi_speaker: True — two callers detected by score-ratio gate")
    else:
        print(
            "[demo] is_multi_speaker: False "
            "(score-ratio gate below threshold; proceeding with separation regardless)"
        )

    # ── Step 6: Link + separate ───────────────────────────────────────────────
    print("[demo] Linking f0 tracks ...")
    f0_tracks = link_f0_tracks(top_k_f0s, top_k_scores)

    print("[demo] Separating speakers → real_caller_1.wav / real_caller_2.wav ...")
    caller_ctxs = separate_speakers(ctx, f0_tracks, str(output_dir), "real")

    # ── Step 7: Figure ────────────────────────────────────────────────────────
    print("[demo] Rendering figure ...")

    magnitude = ctx["magnitude"]
    n_frames = magnitude.shape[1]

    freq_bins = ctx["freq_bins"]
    display_mask = freq_bins <= DISPLAY_FREQ_MAX_HZ
    mag_display = magnitude[display_mask, :]
    mag_db = 20 * np.log10(mag_display + 1e-9)

    time_axis = np.arange(n_frames) * HOP_LENGTH / sr

    fig, ax = plt.subplots(figsize=(14, 5), constrained_layout=True)

    im = ax.imshow(
        mag_db,
        origin="lower",
        aspect="auto",
        cmap="magma",
        vmin=-80,
        vmax=0,
        extent=[0, n_frames * HOP_LENGTH / sr, 0, DISPLAY_FREQ_MAX_HZ],
    )

    for i, (f0_contour, color) in enumerate(zip(f0_tracks, TRACK_COLORS)):
        mean_f0 = float(f0_contour[f0_contour > 0].mean()) if f0_contour.max() > 0 else 0.0
        ax.plot(
            time_axis,
            f0_contour,
            color=color,
            linewidth=2.5,
            label=f"Caller {i + 1}: {mean_f0:.1f} Hz mean f0",
        )

    # Mark overlap region on figure if we have natural overlap
    if not used_fallback and call_a_rel_start is not None:
        overlap_t_start = max(call_a_rel_start, call_b_rel_start)
        overlap_t_end = (
            min(overlap["call_a_end"], overlap["call_b_end"]) - overlap["window_start"]
        )
        ax.axvspan(overlap_t_start, overlap_t_end, alpha=0.15, color="white",
                   label=f"Overlap region ({overlap['overlap_duration']:.2f}s)")

    ax.set_ylim(0, DISPLAY_FREQ_MAX_HZ)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    title_suffix = "(fallback mix)" if used_fallback else "(real simultaneous callers)"
    ax.set_title(f"Multi-Speaker Separation — ElephantVoices Real Recording {title_suffix}")
    ax.legend(loc="upper right")
    fig.colorbar(im, ax=ax, label="Power (dB)")

    out_png = output_dir / "multi_speaker_real_demo.png"
    fig.savefig(str(out_png), dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Copy alias for frontend
    alias_png = output_dir / "multi_speaker_real.png"
    shutil.copy2(str(out_png), str(alias_png))

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("SUCCESS SUMMARY")
    print("=" * 60)
    print(f"Source:       {source_description}")
    if used_fallback:
        print("Mode:         FALLBACK MIX (no natural overlap found with existing WAVs)")
    else:
        print(f"Mode:         REAL natural overlap ({overlap['overlap_duration']:.2f}s overlap)")
    print(f"Duration:     {len(y)/sr:.2f}s at {sr} Hz")
    print(f"Multi-speaker gate: {'True' if multi_detected else 'False'}")
    print()
    for i, f0_contour in enumerate(f0_tracks):
        valid = f0_contour[f0_contour > 0]
        mean_f0 = float(valid.mean()) if len(valid) > 0 else 0.0
        min_f0 = float(valid.min()) if len(valid) > 0 else 0.0
        max_f0 = float(valid.max()) if len(valid) > 0 else 0.0
        wav_name = f"real_caller_{i + 1}.wav"
        print(f"  Caller {i + 1}: mean={mean_f0:.1f} Hz  min={min_f0:.1f}  max={max_f0:.1f}  → {wav_name}")
    print()
    print(f"  Figure:  {out_png}")
    print(f"  Alias:   {alias_png}")
    print("=" * 60)
    print(f"[demo] Complete. Outputs in {output_dir}")


# ─── Main entrypoint ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Multi-speaker separation demo on real overlapping elephant rumbles "
            "from the ElephantVoices dataset. Finds naturally overlapping call pairs "
            "in annotations.xlsx; falls back to mixing two independent calls if none exist."
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
