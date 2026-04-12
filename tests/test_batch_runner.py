"""
Tests for pipeline/batch_runner.py.

All tests use synthetic fixtures — no real audio files required.
Uses build_synthetic_call() from scripts/demo_spectrograms.py for valid (y, sr) pairs.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import soundfile as sf

# Allow importing scripts/ without package install
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.demo_spectrograms import build_synthetic_call
from pipeline.batch_runner import (
    run_batch,
    write_summary_csv,
    write_raven_selection_table,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def synthetic_wav(tmp_path_factory) -> Path:
    """Write a synthetic WAV to a temp directory; returns path."""
    tmp = tmp_path_factory.mktemp("wavs")
    y, sr, _noise_clip, _noise_dict = build_synthetic_call("generator")
    wav_path = tmp / "rec_001.wav"
    sf.write(str(wav_path), y, sr, subtype="PCM_16")
    return wav_path


@pytest.fixture(scope="module")
def two_row_annotations(synthetic_wav) -> pd.DataFrame:
    """
    2-row DataFrame pointing to the same WAV (different time windows so both
    load independently).  Includes noise_type column so classify_noise_type()
    is bypassed (faster, deterministic).
    """
    return pd.DataFrame(
        {
            "filename": [synthetic_wav.name, synthetic_wav.name],
            "start": [0.5, 1.5],
            "end": [3.5, 4.5],
            "noise_type": ["generator", "generator"],
        }
    )


# ─── run_batch: result structure ────────────────────────────────────────────


def test_run_batch_returns_two_results(tmp_path, synthetic_wav, two_row_annotations):
    """run_batch on 2-row DataFrame returns exactly 2 result dicts."""
    recordings_dir = synthetic_wav.parent
    results = run_batch(two_row_annotations, recordings_dir, tmp_path / "output")
    assert len(results) == 2


def test_run_batch_result_keys(tmp_path, synthetic_wav, two_row_annotations):
    """Each result dict contains all required keys with correct suffixes."""
    recordings_dir = synthetic_wav.parent
    results = run_batch(two_row_annotations, recordings_dir, tmp_path / "output")
    required_keys = {
        "filename",
        "start",
        "end",
        "f0_median_hz",
        "snr_before_db",
        "snr_after_db",
        "confidence",
        "noise_type",
        "status",
        "clean_wav_path",
    }
    for result in results:
        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )


def test_run_batch_result_status_ok(tmp_path, synthetic_wav, two_row_annotations):
    """All results for existing WAVs have status='ok'."""
    recordings_dir = synthetic_wav.parent
    results = run_batch(two_row_annotations, recordings_dir, tmp_path / "output")
    for result in results:
        assert result["status"] == "ok"


def test_run_batch_float_fields_are_finite(tmp_path, synthetic_wav, two_row_annotations):
    """f0_median_hz, snr_before_db, snr_after_db, confidence are finite floats."""
    recordings_dir = synthetic_wav.parent
    results = run_batch(two_row_annotations, recordings_dir, tmp_path / "output")
    for result in results:
        for key in ("f0_median_hz", "snr_before_db", "snr_after_db", "confidence"):
            val = result[key]
            assert isinstance(val, float), f"{key} should be float, got {type(val)}"
            assert np.isfinite(val), f"{key} should be finite, got {val}"


def test_run_batch_confidence_in_range(tmp_path, synthetic_wav, two_row_annotations):
    """Confidence score is in [0.0, 100.0]."""
    recordings_dir = synthetic_wav.parent
    results = run_batch(two_row_annotations, recordings_dir, tmp_path / "output")
    for result in results:
        assert 0.0 <= result["confidence"] <= 100.0


def test_run_batch_clean_wav_exists(tmp_path, synthetic_wav, two_row_annotations):
    """clean_wav_path points to a file that actually exists after run_batch."""
    recordings_dir = synthetic_wav.parent
    output_dir = tmp_path / "output"
    results = run_batch(two_row_annotations, recordings_dir, output_dir)
    for result in results:
        assert Path(result["clean_wav_path"]).exists(), (
            f"clean_wav_path does not exist: {result['clean_wav_path']}"
        )


def test_run_batch_wav_not_clipped(tmp_path, synthetic_wav, two_row_annotations):
    """Exported WAV has max(abs(audio)) <= 1.0 (normalization applied)."""
    recordings_dir = synthetic_wav.parent
    output_dir = tmp_path / "output"
    results = run_batch(two_row_annotations, recordings_dir, output_dir)
    for result in results:
        y_out, _ = sf.read(result["clean_wav_path"])
        assert np.max(np.abs(y_out)) <= 1.0 + 1e-6, (
            f"WAV exceeds 1.0: max={np.max(np.abs(y_out))}"
        )


# ─── run_batch: missing WAV ──────────────────────────────────────────────────


def test_run_batch_missing_wav_status_skipped(tmp_path):
    """Row with non-existent WAV produces result with status='skipped', no crash."""
    annotations = pd.DataFrame(
        {
            "filename": ["does_not_exist.wav"],
            "start": [0.0],
            "end": [3.0],
        }
    )
    recordings_dir = tmp_path / "empty_dir"
    recordings_dir.mkdir()
    results = run_batch(annotations, recordings_dir, tmp_path / "output")
    assert len(results) == 1
    assert results[0]["status"] == "skipped"


def test_run_batch_missing_wav_no_crash(tmp_path):
    """run_batch with all missing WAVs completes without raising exceptions."""
    annotations = pd.DataFrame(
        {
            "filename": ["a.wav", "b.wav"],
            "start": [0.0, 0.0],
            "end": [3.0, 3.0],
        }
    )
    recordings_dir = tmp_path / "none"
    recordings_dir.mkdir()
    results = run_batch(annotations, recordings_dir, tmp_path / "output")
    assert len(results) == 2
    assert all(r["status"] == "skipped" for r in results)


# ─── run_batch: progress_callback ────────────────────────────────────────────


def test_run_batch_progress_callback_called(tmp_path, synthetic_wav, two_row_annotations):
    """progress_callback is called once per row with (completed, total) signature."""
    recordings_dir = synthetic_wav.parent
    calls: list[tuple[int, int]] = []

    def cb(completed: int, total: int) -> None:
        calls.append((completed, total))

    run_batch(two_row_annotations, recordings_dir, tmp_path / "output", progress_callback=cb)
    assert len(calls) == 2
    assert calls[0] == (1, 2)
    assert calls[1] == (2, 2)


def test_run_batch_progress_callback_none_is_ok(tmp_path, synthetic_wav, two_row_annotations):
    """run_batch with progress_callback=None completes without error."""
    recordings_dir = synthetic_wav.parent
    results = run_batch(
        two_row_annotations, recordings_dir, tmp_path / "output", progress_callback=None
    )
    assert len(results) == 2


# ─── write_summary_csv ───────────────────────────────────────────────────────


def _make_ok_results() -> list[dict]:
    """Minimal result list for CSV/TSV tests (no actual audio processing)."""
    return [
        {
            "filename": "rec_001.wav",
            "start": 0.5,
            "end": 3.5,
            "f0_median_hz": 14.0,
            "snr_before_db": 5.0,
            "snr_after_db": 12.0,
            "confidence": 75.0,
            "noise_type": "generator",
            "status": "ok",
            "clean_wav_path": "/tmp/rec_001_0000_clean.wav",
        },
        {
            "filename": "rec_001.wav",
            "start": 1.5,
            "end": 4.5,
            "f0_median_hz": 15.0,
            "snr_before_db": 4.5,
            "snr_after_db": 11.0,
            "confidence": 70.0,
            "noise_type": "generator",
            "status": "ok",
            "clean_wav_path": "/tmp/rec_001_0001_clean.wav",
        },
    ]


def test_write_summary_csv_creates_file(tmp_path):
    """write_summary_csv creates the output file."""
    results = _make_ok_results()
    csv_path = tmp_path / "summary.csv"
    write_summary_csv(results, csv_path)
    assert csv_path.exists()


def test_write_summary_csv_required_columns(tmp_path):
    """CSV contains all required columns."""
    results = _make_ok_results()
    csv_path = tmp_path / "summary.csv"
    write_summary_csv(results, csv_path)
    df = pd.read_csv(csv_path)
    required = {"filename", "f0_median_hz", "snr_before_db", "snr_after_db", "confidence", "noise_type", "status"}
    assert required.issubset(set(df.columns)), f"Missing columns: {required - set(df.columns)}"


def test_write_summary_csv_row_count(tmp_path):
    """CSV has one row per result."""
    results = _make_ok_results()
    csv_path = tmp_path / "summary.csv"
    write_summary_csv(results, csv_path)
    df = pd.read_csv(csv_path)
    assert len(df) == len(results)


def test_write_summary_csv_values(tmp_path):
    """CSV values match input result dicts."""
    results = _make_ok_results()
    csv_path = tmp_path / "summary.csv"
    write_summary_csv(results, csv_path)
    df = pd.read_csv(csv_path)
    assert float(df.iloc[0]["f0_median_hz"]) == pytest.approx(14.0)
    assert float(df.iloc[0]["snr_before_db"]) == pytest.approx(5.0)
    assert float(df.iloc[0]["snr_after_db"]) == pytest.approx(12.0)


# ─── write_raven_selection_table ─────────────────────────────────────────────


def test_write_raven_selection_table_creates_file(tmp_path):
    """write_raven_selection_table creates the output TSV file."""
    results = _make_ok_results()
    tsv_path = tmp_path / "selections.tsv"
    write_raven_selection_table(results, tsv_path)
    assert tsv_path.exists()


def test_write_raven_selection_table_header(tmp_path):
    """TSV has exact Raven Pro column header row."""
    results = _make_ok_results()
    tsv_path = tmp_path / "selections.tsv"
    write_raven_selection_table(results, tsv_path)
    with open(tsv_path) as f:
        header = f.readline().rstrip("\n")
    expected = "Selection\tView\tChannel\tBegin Time (s)\tEnd Time (s)\tLow Freq (Hz)\tHigh Freq (Hz)"
    assert header == expected, f"Header mismatch:\n  got:      {header!r}\n  expected: {expected!r}"


def test_write_raven_selection_table_row_count(tmp_path):
    """TSV has one data row per non-skipped result."""
    results = _make_ok_results()
    results.append(
        {
            "filename": "missing.wav",
            "start": 0.0,
            "end": 3.0,
            "f0_median_hz": 0.0,
            "snr_before_db": 0.0,
            "snr_after_db": 0.0,
            "confidence": 0.0,
            "noise_type": "unknown",
            "status": "skipped",
            "clean_wav_path": "",
        }
    )
    tsv_path = tmp_path / "selections.tsv"
    write_raven_selection_table(results, tsv_path)
    with open(tsv_path) as f:
        lines = f.readlines()
    # 1 header + 2 ok rows (skipped row excluded)
    assert len(lines) == 3, f"Expected 3 lines (1 header + 2 data), got {len(lines)}"


def test_write_raven_selection_table_float_format(tmp_path):
    """All float fields use 6 decimal places (locale-safe format)."""
    results = _make_ok_results()
    tsv_path = tmp_path / "selections.tsv"
    write_raven_selection_table(results, tsv_path)
    with open(tsv_path, newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)  # skip header
        for row in reader:
            # Columns 3,4,5,6 = Begin Time, End Time, Low Freq, High Freq
            for col_idx in (3, 4, 5, 6):
                val = row[col_idx]
                parts = val.split(".")
                assert len(parts) == 2 and len(parts[1]) == 6, (
                    f"Expected 6 decimal places in column {col_idx}, got {val!r}"
                )


def test_write_raven_selection_table_freq_bounds(tmp_path):
    """Low Freq = f0 * 0.5, High Freq = f0 * 10 per result."""
    results = _make_ok_results()
    tsv_path = tmp_path / "selections.tsv"
    write_raven_selection_table(results, tsv_path)
    with open(tsv_path, newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)  # skip header
        rows = list(reader)
    # Row 0: f0=14.0 → Low=7.0, High=140.0
    assert float(rows[0][5]) == pytest.approx(14.0 * 0.5, abs=1e-4)
    assert float(rows[0][6]) == pytest.approx(14.0 * 10.0, abs=1e-4)


def test_write_raven_selection_table_selection_index(tmp_path):
    """Selection column starts at 1 and increments."""
    results = _make_ok_results()
    tsv_path = tmp_path / "selections.tsv"
    write_raven_selection_table(results, tsv_path)
    with open(tsv_path, newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)  # skip header
        rows = list(reader)
    assert rows[0][0] == "1"
    assert rows[1][0] == "2"
