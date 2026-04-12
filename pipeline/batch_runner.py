"""
Batch orchestration: drives all 212 calls through the full pipeline.
Covers BATCH-01, BATCH-03, BATCH-04, BATCH-05.

Provides:
  - run_batch: iterate annotation rows, process each call, return result dicts
  - write_summary_csv: write CSV summary of all results
  - write_raven_selection_table: write Raven Pro compatible TSV selection table
"""
from __future__ import annotations

import csv
import warnings
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import soundfile as sf
from tqdm import tqdm

from pipeline.harmonic_processor import process_call
from pipeline.ingestor import extract_noise_gaps, load_call_segment
from pipeline.noise_classifier import classify_noise_type
from pipeline.scoring import compute_confidence, compute_harmonic_integrity, compute_snr_db
from pipeline.spectrogram import compute_stft

# Import make_demo_figure for spectrogram PNG generation (API-05).
# If this import causes issues at load time (e.g. matplotlib not installed),
# run_batch catches the exception and sets png_path="" gracefully.
try:
    from scripts.demo_spectrograms import make_demo_figure as _make_demo_figure
except Exception:  # pragma: no cover
    _make_demo_figure = None  # type: ignore[assignment]


def run_batch(
    annotations: pd.DataFrame,
    recordings_dir: Path,
    output_dir: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """
    Process all rows in the annotations DataFrame through the full pipeline.

    Per-row processing:
      1. Load call segment audio + noise clip
      2. Classify noise type (or use annotation column if present)
      3. Run process_call() — HPSS, f0 detection, comb mask, noisereduce
      4. Compute SNR before (original) and after (re-STFT on audio_clean)
      5. Compute harmonic coverage bins
      6. Compute confidence score
      7. Normalize and export cleaned WAV (no clipping)
      8. Append result dict with suffixed keys: f0_median_hz, snr_before_db, snr_after_db

    Missing WAV files are skipped gracefully (status='skipped', no exception).

    Args:
        annotations:       DataFrame from parse_annotations() — must have filename, start, end
        recordings_dir:    Directory containing source WAV files
        output_dir:        Directory to write cleaned WAVs
        progress_callback: Optional fn(completed, total) called after each row

    Returns:
        List of per-call result dicts, one per annotation row
    """
    recordings_dir = Path(recordings_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    total = len(annotations)
    completed = 0

    for i, row in enumerate(tqdm(annotations.itertuples(), total=total, desc="Batch")):
        wav_path = recordings_dir / row.filename

        # --- Missing WAV: skip gracefully ---
        if not wav_path.exists():
            results.append(
                {
                    "filename": row.filename,
                    "start": row.start,
                    "end": row.end,
                    "f0_median_hz": 0.0,
                    "snr_before_db": 0.0,
                    "snr_after_db": 0.0,
                    "harmonic_integrity": 0.0,
                    "confidence": 0.0,
                    "noise_type": "unknown",
                    "status": "skipped",
                    "clean_wav_path": "",
                    "png_path": "",
                }
            )
            completed += 1
            if progress_callback is not None:
                progress_callback(completed, total)
            continue

        # --- Load call audio ---
        y, sr = load_call_segment(wav_path, row.start, row.end)

        # --- Load noise clip from gap before/after call ---
        gaps = extract_noise_gaps(wav_path, [(row.start, row.end)], row.end + 30.0)
        if gaps:
            noise_clip, _ = load_call_segment(
                wav_path, gaps[0][0], gaps[0][1], pad_seconds=0.0
            )
        else:
            noise_clip = None

        # --- Classify noise type ---
        if hasattr(row, "noise_type") and pd.notna(getattr(row, "noise_type", None)):
            noise_type_dict = {
                "type": str(row.noise_type).lower(),
                "spectral_flatness": 0.0,
                "low_freq_ratio": 0.0,
            }
        else:
            # Use noise clip or first 1.5s of call audio as fallback
            classify_audio = noise_clip if noise_clip is not None else y[: int(1.5 * sr)]
            noise_type_dict = classify_noise_type(classify_audio, sr)

        # --- Run full processing chain ---
        ctx = process_call(y, sr, noise_type_dict, noise_clip=noise_clip)

        # --- SNR before (on original magnitude) ---
        f0_median = float(np.median(ctx["f0_contour"]))
        snr_before = compute_snr_db(ctx["magnitude"], ctx["freq_bins"], f0_median)

        # --- SNR after (re-STFT on audio_clean) ---
        ctx_clean = compute_stft(ctx["audio_clean"], sr)
        snr_after = compute_snr_db(
            ctx_clean["magnitude"], ctx_clean["freq_bins"], f0_median
        )

        # --- Harmonic coverage ---
        # harmonic_bins_total: bins with any comb mask weight > 0 (before masking)
        harmonic_bins_total = int(np.sum(ctx["comb_mask"] > 0))
        # harmonic_bins_masked: harmonic bins that have non-zero masked magnitude
        harmonic_bins_masked = int(
            np.sum((ctx["comb_mask"] > 0) & (ctx["masked_magnitude"] > 0))
        )

        # --- Harmonic integrity score (0-100%) ---
        # Before: how much of the harmonic band is occupied by sharp harmonic peaks
        harmonic_integrity_before = compute_harmonic_integrity(
            ctx["magnitude"], ctx["f0_contour"], ctx["freq_bins"]
        )
        # After: same metric on the cleaned audio (re-STFT)
        harmonic_integrity_after = compute_harmonic_integrity(
            ctx_clean["magnitude"], ctx["f0_contour"], ctx_clean["freq_bins"]
        )

        # --- Confidence score ---
        conf = compute_confidence(
            ctx["f0_contour"],
            snr_before,
            snr_after,
            harmonic_bins_total,
            harmonic_bins_masked,
        )

        # --- Export normalized WAV ---
        call_id = f"{Path(row.filename).stem}_{i:04d}"
        audio_out = ctx["audio_clean"].copy()
        peak = float(np.max(np.abs(audio_out)))
        if peak > 1e-10:
            audio_out = audio_out / peak  # normalize to [-1, 1]
        clean_wav_path = output_dir / f"{call_id}_clean.wav"
        sf.write(str(clean_wav_path), audio_out, sr, subtype="PCM_16")

        # --- Generate spectrogram PNG for API endpoint (API-05) ---
        # Uses a unique noise_type prefix per call so multiple calls with the same
        # noise_type don't overwrite each other: {noise_type}_{call_id}_demo.png
        png_path_obj = None
        if _make_demo_figure is not None:
            try:
                import warnings as _warnings
                with _warnings.catch_warnings():
                    _warnings.simplefilter("ignore")
                    unique_noise_label = f"{noise_type_dict['type']}_{call_id}"
                    png_out, _, _ = _make_demo_figure(
                        unique_noise_label,
                        ctx,
                        y,
                        output_dir / "spectrograms",
                    )
                png_path_obj = png_out
            except Exception:
                pass  # PNG generation is best-effort; never crash the batch

        # --- Build result dict (use _hz and _db suffixed keys) ---
        result = {
            "filename": row.filename,
            "start": row.start,
            "end": row.end,
            "f0_median_hz": f0_median,
            "snr_before_db": snr_before,
            "snr_after_db": snr_after,
            "harmonic_integrity": harmonic_integrity_after,
            "harmonic_integrity_before": harmonic_integrity_before,
            "confidence": conf,
            "noise_type": noise_type_dict["type"],
            "status": "ok",
            "clean_wav_path": str(clean_wav_path),
            "png_path": str(png_path_obj) if png_path_obj is not None else "",
        }
        results.append(result)

        completed += 1
        if progress_callback is not None:
            progress_callback(completed, total)

    return results


def write_summary_csv(results: list[dict], output_path: Path) -> None:
    """
    Write a CSV summary of all batch results.

    Columns: filename, f0_median_hz, snr_before_db, snr_after_db, confidence, noise_type, status

    Note: accesses result dicts using the _hz/_db suffixed keys — NOT f0_median, snr_before, etc.

    Args:
        results:     List of result dicts from run_batch()
        output_path: Path to write the CSV file
    """
    output_path = Path(output_path)
    rows = [
        {
            "filename": r["filename"],
            "f0_median_hz": r["f0_median_hz"],
            "snr_before_db": r["snr_before_db"],
            "snr_after_db": r["snr_after_db"],
            "confidence": r["confidence"],
            "noise_type": r["noise_type"],
            "status": r["status"],
        }
        for r in results
    ]
    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"[batch] Summary CSV: {output_path} ({len(rows)} rows)")


def write_raven_selection_table(results: list[dict], output_path: Path) -> None:
    """
    Write a Raven Pro compatible selection table as a TSV file.

    Header: Selection\\tView\\tChannel\\tBegin Time (s)\\tEnd Time (s)\\tLow Freq (Hz)\\tHigh Freq (Hz)
    Skipped rows are excluded.
    All float fields are formatted as f"{value:.6f}" (locale-safe, no commas).
    Low Freq = f0_median_hz * 0.5, High Freq = f0_median_hz * 10.

    Args:
        results:     List of result dicts from run_batch()
        output_path: Path to write the TSV file
    """
    output_path = Path(output_path)
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(
            [
                "Selection",
                "View",
                "Channel",
                "Begin Time (s)",
                "End Time (s)",
                "Low Freq (Hz)",
                "High Freq (Hz)",
            ]
        )
        selection_idx = 1
        for result in results:
            if result.get("status") == "skipped":
                continue
            f0 = result["f0_median_hz"]
            writer.writerow(
                [
                    selection_idx,
                    "Spectrogram 1",
                    1,
                    f"{result['start']:.6f}",
                    f"{result['end']:.6f}",
                    f"{f0 * 0.5:.6f}",
                    f"{f0 * 10:.6f}",
                ]
            )
            selection_idx += 1
    print(f"[batch] Raven selection table: {output_path} ({selection_idx - 1} rows)")
