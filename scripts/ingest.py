#!/usr/bin/env python3
"""
CLI entrypoint for Phase 1 data ingestion.

Usage:
    python scripts/ingest.py --annotations data/annotations.csv
    python scripts/ingest.py --annotations data/annotations.csv --dry-run
    python scripts/ingest.py --annotations data/annotations.csv \\
        --recordings-dir data/recordings/ \\
        --output-dir data/segments/ \\
        --noise-dir data/noise_segments/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import librosa
import soundfile as sf
from tqdm import tqdm

# Ensure repo root is on sys.path when run as script
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.config import PAD_SECONDS
from pipeline.ingestor import extract_noise_gaps, load_call_segment, parse_annotations
from pipeline.noise_classifier import classify_noise_type
from pipeline.spectrogram import compute_stft


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest ElephantVoices recordings: parse annotations, segment calls, classify noise."
    )
    parser.add_argument(
        "--annotations",
        required=True,
        metavar="PATH",
        help="Path to annotation CSV or XLSX file",
    )
    parser.add_argument(
        "--recordings-dir",
        default="data/recordings",
        metavar="PATH",
        help="Directory containing source WAV recordings (default: data/recordings)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/segments",
        metavar="PATH",
        help="Output directory for segmented call WAVs (default: data/segments)",
    )
    parser.add_argument(
        "--noise-dir",
        default="data/noise_segments",
        metavar="PATH",
        help="Output directory for noise segment WAVs (default: data/noise_segments)",
    )
    parser.add_argument(
        "--pad-seconds",
        type=float,
        default=PAD_SECONDS,
        metavar="FLOAT",
        help=f"Padding in seconds before/after each call (default: {PAD_SECONDS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without writing any files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    annotations_path = Path(args.annotations)
    recordings_dir = Path(args.recordings_dir)
    output_dir = Path(args.output_dir)
    noise_dir = Path(args.noise_dir)

    if not annotations_path.exists():
        print(f"[ERROR] Annotations file not found: {annotations_path}")
        sys.exit(1)

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        noise_dir.mkdir(parents=True, exist_ok=True)

    print(f"[ingest] Mode: {'DRY RUN (no files written)' if args.dry_run else 'LIVE'}")
    print(f"[ingest] Annotations: {annotations_path}")
    print(f"[ingest] Recordings: {recordings_dir}")
    print(f"[ingest] Output: {output_dir}")
    print(f"[ingest] Pad: {args.pad_seconds}s per side")
    print()

    # Parse annotation spreadsheet (prints columns + 5 rows for manual verification)
    df = parse_annotations(annotations_path)

    summary_rows = []

    for wav_name, group in tqdm(df.groupby("filename"), desc="Ingesting recordings"):
        wav_path = recordings_dir / wav_name
        calls = list(zip(group["start"].astype(float), group["end"].astype(float)))

        if not wav_path.exists():
            print(f"[WARN] Recording not found: {wav_path} — skipping")
            continue

        # Get recording duration for gap extraction
        duration = librosa.get_duration(path=str(wav_path))

        # Extract noise-only gaps for noise profiling
        gaps = extract_noise_gaps(wav_path, calls, duration)
        noise_type = "mixed"

        if gaps:
            gap_start, gap_end = gaps[0]
            y_noise, sr_noise = librosa.load(
                str(wav_path), sr=None, offset=gap_start, duration=gap_end - gap_start
            )
            noise_info = classify_noise_type(y_noise, sr_noise)
            noise_type = noise_info["type"]

            if not args.dry_run:
                noise_out = noise_dir / f"{Path(wav_name).stem}_noise.wav"
                sf.write(str(noise_out), y_noise, sr_noise)
        else:
            print(
                f"[WARN] No noise gap found in {wav_name} — "
                "using recording start as fallback noise profile"
            )

        # Extract each call clip
        for i, (start, end) in enumerate(calls):
            if args.dry_run:
                print(
                    f"  [dry-run] Would segment call {i:03d}: "
                    f"{wav_name}[{start:.2f}s–{end:.2f}s] "
                    f"(+{args.pad_seconds}s pad)"
                )
                continue

            y, sr = load_call_segment(wav_path, start, end, args.pad_seconds)

            # Compute STFT to verify resolution (raises if misconfigured)
            compute_stft(y, sr)

            stem = Path(wav_name).stem
            out_path = output_dir / f"{stem}_call{i:03d}.wav"
            sf.write(str(out_path), y, sr)

        summary_rows.append(
            {
                "filename": wav_name,
                "calls_segmented": len(calls),
                "noise_type": noise_type,
                "gaps_found": len(gaps),
            }
        )

    # Print summary table
    print()
    print("[ingest] Summary:")
    print(f"{'filename':<40} {'calls':>6} {'noise_type':<12} {'gaps':>5}")
    print("-" * 70)
    for row in summary_rows:
        print(
            f"{row['filename']:<40} "
            f"{row['calls_segmented']:>6} "
            f"{row['noise_type']:<12} "
            f"{row['gaps_found']:>5}"
        )
    total_calls = sum(r["calls_segmented"] for r in summary_rows)
    print(f"\n[ingest] Total: {len(summary_rows)} recordings, {total_calls} calls segmented")
    if args.dry_run:
        print("[ingest] DRY RUN complete — no files written")


if __name__ == "__main__":
    main()
