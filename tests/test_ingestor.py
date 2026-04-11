"""
Tests for pipeline.ingestor — annotation parser, segment loader, noise gap extractor.
TDD: These tests are written before the implementation.
"""

import os
import tempfile

import pytest


def test_parse_annotations_normalizes_columns():
    """Columns with mixed case and spaces should be normalized to lowercase-stripped."""
    from pipeline.ingestor import parse_annotations
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("Filename, Start , End\nrec1.wav,5.0,10.0\n")
        fname = f.name
    try:
        df = parse_annotations(fname)
        assert "filename" in df.columns
        assert "start" in df.columns
        assert "end" in df.columns
    finally:
        os.unlink(fname)


def test_parse_annotations_missing_end_column_raises_valueerror():
    """Missing required column 'end' should raise ValueError mentioning 'missing required columns'."""
    from pipeline.ingestor import parse_annotations
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("filename,start\nrec1.wav,5.0\n")
        fname = f.name
    try:
        with pytest.raises(ValueError) as exc_info:
            parse_annotations(fname)
        assert "missing required columns" in str(exc_info.value).lower()
    finally:
        os.unlink(fname)


def test_parse_annotations_missing_column_error_includes_actual_columns():
    """ValueError must include the actual column list found in the file."""
    from pipeline.ingestor import parse_annotations
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("filename,begin_time\nrec1.wav,5.0\n")
        fname = f.name
    try:
        with pytest.raises(ValueError) as exc_info:
            parse_annotations(fname)
        error_msg = str(exc_info.value)
        # Should include the columns that were actually found
        assert "begin_time" in error_msg or "filename" in error_msg
    finally:
        os.unlink(fname)


def test_extract_noise_gaps_standard_case():
    """Standard case: gaps between calls and at start/end."""
    from pipeline.ingestor import extract_noise_gaps
    gaps = extract_noise_gaps("dummy.wav", [(5.0, 10.0), (20.0, 25.0)], 60.0)
    assert gaps == [(0.0, 5.0), (10.0, 20.0), (25.0, 60.0)]


def test_extract_noise_gaps_no_gaps():
    """Dense calls: no gaps >= 1.0s should return empty list."""
    from pipeline.ingestor import extract_noise_gaps
    gaps = extract_noise_gaps("dummy.wav", [(0.5, 59.5)], 60.0)
    assert gaps == []


def test_extract_noise_gaps_start_gap_only():
    """Call at 5s to end: only start gap returned."""
    from pipeline.ingestor import extract_noise_gaps
    gaps = extract_noise_gaps("dummy.wav", [(5.0, 59.5)], 60.0)
    assert gaps == [(0.0, 5.0)]


def test_extract_noise_gaps_empty_calls_returns_full_recording():
    """No calls at all — entire recording is a noise gap."""
    from pipeline.ingestor import extract_noise_gaps
    gaps = extract_noise_gaps("dummy.wav", [], 60.0)
    assert gaps == [(0.0, 60.0)]


def test_extract_noise_gaps_short_recording_no_calls():
    """Recording shorter than MIN_NOISE_DURATION_SEC with no calls returns empty."""
    from pipeline.ingestor import extract_noise_gaps
    # MIN_NOISE_DURATION_SEC = 1.0, recording is 0.5s
    gaps = extract_noise_gaps("dummy.wav", [], 0.5)
    assert gaps == []


def test_load_call_segment_uses_sr_none():
    """Verify the source code uses sr=None in librosa.load call."""
    import inspect
    from pipeline import ingestor
    source = inspect.getsource(ingestor.load_call_segment)
    assert "sr=None" in source, "load_call_segment must use sr=None to prevent silent resampling"
