"""
Data ingestion: annotation parsing, call segmentation, noise gap extraction.
Covers INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05.
"""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import pandas as pd

from pipeline.config import (
    MIN_NOISE_DURATION_SEC,
    PAD_SECONDS,
    verify_resolution,
)

# Columns that MUST be present after normalization.
# Adjust these once the actual annotation file is opened and column names confirmed.
REQUIRED_COLS: set[str] = {"filename", "start", "end"}


def parse_annotations(csv_path: str | Path) -> pd.DataFrame:
    """
    Parse annotation CSV or XLSX file.

    Column names are normalized (lowercase, stripped) to handle Raven Pro exports
    like "Begin Time (s)" or "Filename" with mixed case.

    Prints first 5 rows for manual verification (INGEST-01).

    Args:
        csv_path: Path to .csv or .xlsx annotation file

    Returns:
        DataFrame with normalized column names

    Raises:
        ValueError: If required columns (filename, start, end) are not present
                    after normalization
    """
    path = Path(csv_path)
    if path.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, engine="openpyxl")
    else:
        df = pd.read_csv(path)

    # Normalize: lowercase and strip whitespace from column names
    df.columns = df.columns.str.lower().str.strip()

    # Accept ElephantVoices master spreadsheet column names as aliases
    column_aliases = {
        "sound_file": "filename",
        "start_time": "start",
        "end_time": "end",
    }
    df = df.rename(columns={k: v for k, v in column_aliases.items() if k in df.columns})

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"Annotation file missing required columns: {missing}\n"
            f"Found columns: {list(df.columns)}\n"
            f"Rename or adjust REQUIRED_COLS in pipeline/ingestor.py."
        )

    # Loud validation: print sample for manual verification
    print(f"[ingestor] Parsed {len(df)} rows from {path.name}")
    print(f"[ingestor] Columns: {list(df.columns)}")
    print("[ingestor] First 5 rows (filename, start, end):")
    print(df[list({"filename", "start", "end"} & set(df.columns))].head().to_string())
    print()

    return df


def load_call_segment(
    wav_path: str | Path,
    start_sec: float,
    end_sec: float,
    pad_seconds: float = PAD_SECONDS,
) -> tuple[np.ndarray, int]:
    """
    Load a single call clip from a recording with padding. (INGEST-02, INGEST-03)

    Uses librosa.load with sr=None to prevent silent resampling.
    Calls verify_resolution(sr) to enforce INGEST-05.

    Args:
        wav_path: Path to the source recording WAV file
        start_sec: Call start time in seconds (from annotation)
        end_sec: Call end time in seconds (from annotation)
        pad_seconds: Seconds of context before/after call (default: PAD_SECONDS=2.0)

    Returns:
        (y, sr) where y is float32 audio array and sr is native sample rate
    """
    offset = max(0.0, start_sec - pad_seconds)
    duration = (end_sec + pad_seconds) - offset

    # CRITICAL: sr=None — never use default sr=22050 which destroys infrasonic content
    y, sr = librosa.load(str(wav_path), sr=None, offset=offset, duration=duration)

    # INGEST-05: assert frequency resolution on first load (sr is now known from file)
    verify_resolution(sr)

    return y, sr


def extract_noise_gaps(
    wav_path: str | Path,
    calls: list[tuple[float, float]],
    recording_duration: float,
) -> list[tuple[float, float]]:
    """
    Extract noise-only segments from gaps between annotated calls. (INGEST-04)

    Finds regions between calls that are >= MIN_NOISE_DURATION_SEC.
    These are used as noise profiles for the denoiser in Phase 2.

    If no gaps are found, callers must handle the empty list gracefully
    (e.g., use first 0.5s of recording as fallback noise profile).

    Args:
        wav_path: Path to source recording (unused currently, reserved for future metadata)
        calls: List of (start_sec, end_sec) tuples from annotation
        recording_duration: Total duration of recording in seconds

    Returns:
        List of (start_sec, end_sec) tuples for noise-only segments
    """
    if not calls:
        # Entire recording is noise
        if recording_duration >= MIN_NOISE_DURATION_SEC:
            return [(0.0, recording_duration)]
        return []

    sorted_calls = sorted(calls, key=lambda x: x[0])
    gaps: list[tuple[float, float]] = []
    prev_end = 0.0

    for start, end in sorted_calls:
        gap_duration = start - prev_end
        if gap_duration >= MIN_NOISE_DURATION_SEC:
            gaps.append((prev_end, start))
        prev_end = end

    # Gap after last call
    trailing_duration = recording_duration - prev_end
    if trailing_duration >= MIN_NOISE_DURATION_SEC:
        gaps.append((prev_end, recording_duration))

    return gaps
