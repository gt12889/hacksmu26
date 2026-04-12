#!/usr/bin/env python3
"""
CLI: process a single annotated call through the full Phase 2 pipeline.

Usage:
    python scripts/process_call.py \\
        --wav data/recordings/rec1.wav \\
        --start 5.0 \\
        --end 10.0 \\
        --output data/outputs/rec1_5s_clean.wav

    # With noise type override (skip classifier, useful for testing):
    python scripts/process_call.py \\
        --wav data/recordings/rec1.wav \\
        --start 5.0 \\
        --end 10.0 \\
        --noise-type generator \\
        --output data/outputs/rec1_clean.wav

Output:
    - Cleaned WAV file at --output path
    - f0 contour statistics printed to stdout
    - Noise type classification printed to stdout
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

# Allow running from repo root without installing as package
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from pipeline.harmonic_processor import process_call
from pipeline.ingestor import extract_noise_gaps, load_call_segment
from pipeline.noise_classifier import classify_noise_type


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process a single elephant call through Phase 2 pipeline (HPSS + SHS + comb mask + noisereduce)"
    )
    parser.add_argument("--wav", required=True, help="Path to source recording WAV file")
    parser.add_argument("--start", type=float, required=True, help="Call start time in seconds")
    parser.add_argument("--end", type=float, required=True, help="Call end time in seconds")
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for cleaned WAV (e.g. data/outputs/clean.wav)",
    )
    parser.add_argument(
        "--noise-type",
        choices=["generator", "car", "plane", "mixed"],
        default=None,
        help="Override noise type classification (optional — auto-detects if not given)",
    )
    parser.add_argument(
        "--pad",
        type=float,
        default=2.0,
        help="Padding seconds around call (default: 2.0)",
    )
    args = parser.parse_args()

    wav_path = Path(args.wav)
    if not wav_path.exists():
        print(f"[error] WAV file not found: {wav_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ---- Step 1: Load call segment ----
    print(f"[process_call] Loading call {args.start:.1f}s – {args.end:.1f}s from {wav_path.name}")
    y, sr = load_call_segment(wav_path, args.start, args.end, pad_seconds=args.pad)
    print(f"[process_call] Loaded {len(y)} samples at sr={sr} ({len(y)/sr:.2f}s)")

    # ---- Step 2: Noise type (auto-detect or use override) ----
    if args.noise_type is not None:
        noise_type = {"type": args.noise_type, "spectral_flatness": 0.0, "low_freq_ratio": 0.0}
        print(f"[process_call] Noise type: {args.noise_type} (user override)")
    else:
        # Try to get a noise gap from before/after the call
        # Use ±30s window as a rough recording estimate
        approx_duration = args.end + 30.0
        gaps = extract_noise_gaps(wav_path, [(args.start, args.end)], approx_duration)
        if gaps:
            gap_start, gap_end = gaps[0]
            y_noise, _ = load_call_segment(wav_path, gap_start, gap_end, pad_seconds=0.0)
            noise_type = classify_noise_type(y_noise, sr)
        else:
            # No gap found — use first 1.5s of the loaded clip as noise estimate
            noise_samples = int(1.5 * sr)
            y_noise = y[:noise_samples] if len(y) > noise_samples else y
            noise_type = classify_noise_type(y_noise, sr)
        print(f"[process_call] Auto-classified noise type: {noise_type['type']}")

    # ---- Step 3: Load noise clip for generator mode ----
    noise_clip: np.ndarray | None = None
    if noise_type["type"] == "generator":
        approx_duration = args.end + 30.0
        gaps = extract_noise_gaps(wav_path, [(args.start, args.end)], approx_duration)
        if gaps:
            gap_start, gap_end = gaps[0]
            noise_clip, _ = load_call_segment(wav_path, gap_start, gap_end, pad_seconds=0.0)
            print(f"[process_call] Noise clip loaded: {len(noise_clip)/sr:.2f}s gap at {gap_start:.1f}s")
        else:
            print("[process_call] Warning: generator type but no noise gap found — falling back to non-stationary")

    # ---- Step 4: Run Phase 2 pipeline ----
    print("[process_call] Running HPSS -> SHS -> comb mask -> noisereduce...")
    ctx = process_call(y, sr, noise_type, noise_clip=noise_clip)

    # ---- Step 5: Report f0 statistics ----
    f0 = ctx["f0_contour"]
    print(f"[process_call] f0 contour — median: {np.median(f0):.1f} Hz, "
          f"min: {f0.min():.1f} Hz, max: {f0.max():.1f} Hz")

    # ---- Step 6: Save cleaned audio ----
    sf.write(str(output_path), ctx["audio_clean"], sr)
    print(f"[process_call] Saved cleaned audio -> {output_path}")
    print(f"[process_call] Done. Input: {len(y)/sr:.2f}s  Output: {len(ctx['audio_clean'])/sr:.2f}s")


if __name__ == "__main__":
    main()
