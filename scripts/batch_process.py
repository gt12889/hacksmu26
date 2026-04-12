#!/usr/bin/env python3
"""
Batch processor for ElephantVoices Denoiser.

Processes all calls in an annotation file through the full pipeline,
outputting cleaned WAVs, a summary CSV, and a Raven Pro selection table.

Usage:
    # Synthetic mode (no real recordings required):
    python scripts/batch_process.py --synthetic --output-dir data/outputs/batch

    # Real recordings mode:
    python scripts/batch_process.py \\
        --annotations data/annotations.csv \\
        --recordings-dir data/recordings/ \\
        --output-dir data/outputs/batch

Outputs:
    {output_dir}/cleaned/          — per-call WAV files
    {output_dir}/batch_summary.csv — per-call metrics
    {output_dir}/raven_selection.txt — Raven Pro selection table
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

# Allow running from repo root without installing as package
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from pipeline.batch_runner import run_batch, write_summary_csv, write_raven_selection_table  # noqa: E402
from pipeline.ingestor import parse_annotations  # noqa: E402


def _build_synthetic_annotations(
    output_dir: Path,
) -> tuple[pd.DataFrame, Path]:
    """
    Build 3 synthetic calls (one per noise type) and write temp WAV files.

    Uses build_synthetic_call from demo_spectrograms.py to produce audio.
    Each WAV is written with a 5-second noise-only tail appended after the call
    so that extract_noise_gaps() can find a valid noise profile within the file.
    (Without the tail, the 30-second lookahead in batch_runner would request
    audio past end-of-file, returning an empty clip that crashes noisereduce.)

    Writes each call to output_dir/synthetic_recordings/ as a WAV file,
    then returns a DataFrame with one row per call and the recordings dir.

    Returns:
        (annotations_df, recordings_dir)
    """
    # Import here so missing matplotlib doesn't block --help or real mode
    from scripts.demo_spectrograms import build_synthetic_call, NOISE_TYPES  # noqa: E402

    recordings_dir = output_dir / "synthetic_recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(99)
    NOISE_TAIL_SECONDS = 5.0  # appended after the call so gaps finder has material

    rows = []
    for noise_type in NOISE_TYPES:
        y, sr, noise_clip, _noise_type_dict = build_synthetic_call(noise_type)
        wav_filename = f"synthetic_{noise_type}.wav"
        wav_path = recordings_dir / wav_filename

        call_duration = len(y) / sr  # e.g. 6.0 s

        # Append noise tail (white noise at similar amplitude) so there's a
        # real noise gap for extract_noise_gaps() to return.
        noise_tail_samples = int(NOISE_TAIL_SECONDS * sr)
        noise_level = float(np.std(y)) if np.std(y) > 1e-10 else 0.01
        noise_tail = rng.standard_normal(noise_tail_samples).astype(np.float32) * noise_level

        y_full = np.concatenate([y, noise_tail])

        # Normalize before writing to avoid PCM_16 clipping
        peak = float(np.max(np.abs(y_full)))
        if peak > 1e-10:
            y_full = y_full / peak
        sf.write(str(wav_path), y_full, sr, subtype="PCM_16")

        rows.append(
            {
                "filename": wav_filename,
                "start": 0.0,
                "end": call_duration,  # annotation marks only the call, not the tail
                "noise_type": noise_type,
            }
        )

    annotations_df = pd.DataFrame(rows)
    return annotations_df, recordings_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Batch processor for ElephantVoices Denoiser. "
            "Processes all calls in an annotation file through the full pipeline."
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
        default=Path("data/outputs/batch"),
        help="Directory to write cleaned WAVs, summary CSV, and Raven table (default: data/outputs/batch)",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use synthetic audio instead of real recordings (for testing, no real recordings required)",
    )
    args = parser.parse_args()

    # Validate args
    if not args.synthetic and (args.annotations is None or args.recordings_dir is None):
        print(
            "[error] --annotations and --recordings-dir are required when --synthetic is not set.",
            file=sys.stderr,
        )
        sys.exit(1)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # cleaned WAVs go in a sub-directory to keep outputs organized
    cleaned_dir = output_dir / "cleaned"

    # --- Load or generate annotations ---
    if args.synthetic:
        print("[batch] Synthetic mode: generating test audio for each noise type...")
        annotations_df, recordings_dir = _build_synthetic_annotations(output_dir)
        print(f"[batch] Synthetic recordings written to {recordings_dir}")
    else:
        recordings_dir = args.recordings_dir
        annotations_df = parse_annotations(args.annotations)

    total_calls = len(annotations_df)
    print(f"[batch] Processing {total_calls} calls...")

    # Progress callback: print every 10 calls to reduce terminal noise
    def progress_cb(done: int, total: int) -> None:
        if done % 10 == 0 or done == total:
            print(f"[batch] {done}/{total} calls complete")

    # --- Run the batch ---
    results = run_batch(
        annotations_df,
        recordings_dir,
        cleaned_dir,
        progress_callback=progress_cb,
    )

    # --- Write outputs ---
    summary_csv_path = output_dir / "batch_summary.csv"
    raven_table_path = output_dir / "raven_selection.txt"

    write_summary_csv(results, summary_csv_path)
    write_raven_selection_table(results, raven_table_path)

    # --- Print completion summary ---
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    completed = len(results) - skipped
    print()
    print(f"[batch] Done.")
    print(f"[batch]   Total calls    : {len(results)}")
    print(f"[batch]   Processed      : {completed}")
    print(f"[batch]   Skipped        : {skipped}")
    print(f"[batch]   Output dir     : {output_dir}")
    print(f"[batch]   Summary CSV    : {summary_csv_path}")
    print(f"[batch]   Raven table    : {raven_table_path}")
    print(f"[batch]   Cleaned WAVs   : {cleaned_dir}")


if __name__ == "__main__":
    main()
