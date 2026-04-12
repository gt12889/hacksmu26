#!/usr/bin/env python
"""
Demo script for REAL ElephantVoices recordings.

Picks one annotated call per noise type from data/annotations.xlsx,
runs the full pipeline, and generates publication-quality figures +
cleaned WAVs to data/outputs/real_demo/.

Usage:
    python scripts/demo_real.py
    python scripts/demo_real.py --output-dir custom/path
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import librosa
import soundfile as sf

_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from pipeline.config import HOP_LENGTH
from pipeline.noise_classifier import classify_noise_type
from pipeline.harmonic_processor import process_call
from pipeline.ingestor import extract_noise_gaps
from pipeline.scoring import compute_harmonic_integrity
from pipeline.spectrogram import compute_stft
from scripts.demo_spectrograms import make_demo_figure


ANNOTATIONS = _repo_root / "data" / "annotations.xlsx"
RECORDINGS_DIR = _repo_root / "data" / "recordings" / "real"


def find_best_calls(df: pd.DataFrame) -> dict[str, dict]:
    """Pick one call per noise type (generator, vehicle, airplane).

    Strategy: Pick calls with duration 2-5s that are clearly in one noise category.
    """
    picks: dict[str, dict] = {}
    for noise_type, keyword in [
        ("generator", "generator"),
        ("vehicle", "vehicle_1"),
        ("airplane", "airplane"),
    ]:
        mask = df["Sound_file"].str.contains(keyword, case=False, na=False)
        # Exclude mixed noise files
        mask &= ~df["Sound_file"].str.contains("background", case=False, na=False)
        candidates = df[mask].copy()
        if len(candidates) == 0:
            continue
        candidates["duration"] = candidates["End_time"] - candidates["Start_time"]
        # Pick 2-5s calls, fallback to any
        clean = candidates[(candidates["duration"] >= 2.0) & (candidates["duration"] <= 5.0)]
        if len(clean) == 0:
            clean = candidates
        row = clean.iloc[0]
        picks[noise_type] = {
            "filename": row["Sound_file"],
            "start": float(row["Start_time"]),
            "end": float(row["End_time"]),
            "duration": float(row["End_time"] - row["Start_time"]),
        }
    return picks


def process_real_call(
    noise_type: str, filename: str, start: float, end: float, output_dir: Path
) -> dict:
    """Load a real call segment, run pipeline, generate figure + WAV."""
    path = RECORDINGS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Recording not found: {path}")

    # Load with 2s padding
    pad = 2.0
    offset = max(0.0, start - pad)
    duration = (end - start) + 2 * pad
    y, sr = librosa.load(str(path), sr=None, offset=offset, duration=duration)

    # Classify noise type (keep label even if wrong — informative)
    detected_noise = classify_noise_type(y, sr)

    # Try to get a noise clip from before the call for stationary mode
    noise_clip = None
    try:
        # Load a chunk before the call for noise profile
        noise_offset = max(0.0, start - 10.0)
        noise_dur = min(5.0, start - noise_offset)
        if noise_dur > 0.5:
            noise_y, _ = librosa.load(str(path), sr=None, offset=noise_offset, duration=noise_dur)
            noise_clip = noise_y
    except Exception:
        pass

    # Override noise_type with folder label (ground truth from filename)
    truth = {"type": noise_type, "spectral_flatness": detected_noise.get("spectral_flatness", 0.0)}

    # Run full pipeline
    ctx = process_call(y, sr, truth, noise_clip=noise_clip)

    # Generate figure using existing make_demo_figure (expects y + ctx)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_paths = make_demo_figure(
        y=y, ctx=ctx, noise_type=noise_type, output_dir=output_dir
    )

    f0 = ctx["f0_contour"]
    valid = f0[f0 > 0]

    # Harmonic integrity: before (raw) and after (cleaned)
    integrity_before = compute_harmonic_integrity(
        ctx["magnitude"], ctx["f0_contour"], ctx["freq_bins"]
    )
    ctx_clean = compute_stft(ctx["audio_clean"], sr)
    integrity_after = compute_harmonic_integrity(
        ctx_clean["magnitude"], ctx["f0_contour"], ctx_clean["freq_bins"]
    )

    return {
        "noise_type": noise_type,
        "filename": filename,
        "call_start": start,
        "call_end": end,
        "duration": float(end - start),
        "detected_as": detected_noise["type"],
        "f0_median_hz": float(np.median(valid)) if len(valid) > 0 else 0.0,
        "f0_min_hz": float(valid.min()) if len(valid) > 0 else 0.0,
        "f0_max_hz": float(valid.max()) if len(valid) > 0 else 0.0,
        "valid_frames": int(len(valid)),
        "total_frames": int(len(f0)),
        "harmonic_integrity_before": integrity_before,
        "harmonic_integrity_after": integrity_after,
        "figure_paths": [str(p) for p in figure_paths],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pipeline on real ElephantVoices recordings")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_repo_root / "data" / "outputs" / "real_demo",
        help="Output directory for figures and WAVs",
    )
    args = parser.parse_args()

    if not ANNOTATIONS.exists():
        print(f"ERROR: annotations not found at {ANNOTATIONS}")
        return 1
    if not RECORDINGS_DIR.exists():
        print(f"ERROR: recordings not found at {RECORDINGS_DIR}")
        return 1

    print(f"Loading annotations from {ANNOTATIONS}")
    df = pd.read_excel(ANNOTATIONS)
    print(f"Total calls in spreadsheet: {len(df)}")

    picks = find_best_calls(df)
    print(f"\nPicked {len(picks)} representative calls:")
    for nt, info in picks.items():
        print(f"  {nt}: {info['filename']}  {info['start']:.1f}s-{info['end']:.1f}s  ({info['duration']:.1f}s)")

    results = []
    for nt, info in picks.items():
        print(f"\n[{nt}] Processing...")
        try:
            r = process_real_call(nt, info["filename"], info["start"], info["end"], args.output_dir)
            results.append(r)
            print(f"  f0 median={r['f0_median_hz']:.1f}Hz range=[{r['f0_min_hz']:.1f}, {r['f0_max_hz']:.1f}]  "
                  f"detected_as={r['detected_as']}  valid_frames={r['valid_frames']}/{r['total_frames']}")
            print(f"  harmonic_integrity: {r['harmonic_integrity_before']:.1f}% -> {r['harmonic_integrity_after']:.1f}%"
                  f"  (delta: {r['harmonic_integrity_after'] - r['harmonic_integrity_before']:+.1f}%)")
            print(f"  Files: {', '.join(Path(p).name for p in r['figure_paths'])}")
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"Output directory: {args.output_dir}")
    print(f"Results: {len(results)}/{len(picks)} succeeded")
    return 0 if len(results) == len(picks) else 1


if __name__ == "__main__":
    sys.exit(main())
