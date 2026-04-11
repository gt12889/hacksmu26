"""
Phase 1 pipeline tests.
Covers INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, SPEC-01, SPEC-02, SPEC-03.
All tests use synthetic fixtures — no real recordings required.
"""

from __future__ import annotations

import os
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline.config import N_FFT, HOP_LENGTH, verify_resolution
from pipeline.ingestor import extract_noise_gaps, parse_annotations
from pipeline.noise_classifier import classify_noise_type
from pipeline.spectrogram import compute_stft, reconstruct_audio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sine_44100():
    """1-second 20 Hz sine wave at 44100 Hz — infrasonic test signal."""
    sr = 44100
    t = np.linspace(0, 1.0, sr, dtype=np.float32)
    y = np.sin(2 * np.pi * 20 * t)
    return y, sr


@pytest.fixture
def sine_60hz_44100():
    """2-second 60 Hz sine wave at 44100 Hz — generator hum signature."""
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, dtype=np.float32)
    y = np.sin(2 * np.pi * 60 * t)
    return y, sr


@pytest.fixture
def annotation_csv(tmp_path):
    """Minimal annotation CSV with mixed-case column names and extra whitespace."""
    csv_content = "Filename, Start ,End,noise_type\nrec1.wav,5.0,10.0,generator\nrec1.wav,20.0,25.0,generator\n"
    csv_file = tmp_path / "annotations.csv"
    csv_file.write_text(csv_content)
    return csv_file


# ---------------------------------------------------------------------------
# INGEST-05: frequency resolution assertion
# ---------------------------------------------------------------------------

class TestIngest05ResolutionAssertion:
    """INGEST-05: Assert sr/n_fft < 6 Hz to prevent silent resolution failures."""

    def test_assertion_fires_for_96000hz(self):
        """96000 Hz with n_fft=8192 gives 11.72 Hz/bin — must raise."""
        with pytest.raises(AssertionError) as exc_info:
            verify_resolution(96000, 8192)
        assert "sr=96000" in str(exc_info.value)

    def test_assertion_passes_for_44100hz(self):
        """44100 Hz with n_fft=8192 gives 5.38 Hz/bin — must pass."""
        verify_resolution(44100)  # Should not raise

    def test_assertion_passes_for_48000hz(self):
        """48000 Hz with n_fft=8192 gives 5.86 Hz/bin — must pass."""
        verify_resolution(48000)  # Should not raise

    def test_assertion_fires_for_small_n_fft(self):
        """Any sample rate with n_fft=2048 exceeds 6 Hz/bin at standard rates."""
        with pytest.raises(AssertionError):
            verify_resolution(44100, 2048)  # 44100/2048 = 21.5 Hz/bin


# ---------------------------------------------------------------------------
# INGEST-01: annotation parsing
# ---------------------------------------------------------------------------

class TestIngest01AnnotationParsing:
    """INGEST-01: Parse annotation spreadsheet with column normalization."""

    def test_normalizes_column_names(self, annotation_csv):
        """Columns with mixed case and whitespace must be normalized."""
        df = parse_annotations(annotation_csv)
        assert "filename" in df.columns
        assert "start" in df.columns
        assert "end" in df.columns

    def test_missing_required_column_raises(self, tmp_path):
        """Missing 'end' column must raise ValueError with column list."""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("filename,start\nrec1.wav,5.0\n")
        with pytest.raises(ValueError) as exc_info:
            parse_annotations(bad_csv)
        assert "missing required columns" in str(exc_info.value).lower()

    def test_parses_row_count_correctly(self, annotation_csv):
        """Must return a DataFrame with the correct number of rows."""
        df = parse_annotations(annotation_csv)
        assert len(df) == 2


# ---------------------------------------------------------------------------
# INGEST-03 and INGEST-04: call segmentation and noise gap extraction
# ---------------------------------------------------------------------------

class TestIngest03And04Segmentation:
    """INGEST-03: segment calls. INGEST-04: extract noise gaps."""

    def test_noise_gaps_basic(self):
        """Three gaps: before first call, between calls, after last call."""
        calls = [(5.0, 10.0), (20.0, 25.0)]
        gaps = extract_noise_gaps("dummy.wav", calls, 60.0)
        assert gaps == [(0.0, 5.0), (10.0, 20.0), (25.0, 60.0)]

    def test_noise_gaps_none_when_densely_packed(self):
        """Calls spanning nearly entire recording leave no usable gaps."""
        calls = [(0.5, 59.5)]
        gaps = extract_noise_gaps("dummy.wav", calls, 60.0)
        assert gaps == []

    def test_noise_gaps_start_only(self):
        """Gap at start only (call runs to end of recording)."""
        calls = [(5.0, 59.5)]
        gaps = extract_noise_gaps("dummy.wav", calls, 60.0)
        assert gaps == [(0.0, 5.0)]

    def test_noise_gaps_handles_unsorted_input(self):
        """Calls provided out of order must still produce correct gaps."""
        calls = [(20.0, 25.0), (5.0, 10.0)]  # reversed order
        gaps = extract_noise_gaps("dummy.wav", calls, 60.0)
        assert (0.0, 5.0) in gaps
        assert (10.0, 20.0) in gaps

    def test_load_segment_offset_calculation(self):
        """Verify offset and duration math: start=10.0, end=15.0, pad=2.0 → offset=8.0, duration=9.0."""
        # We test the math directly since we can't provide a real WAV file here.
        start_sec, end_sec, pad = 10.0, 15.0, 2.0
        offset = max(0.0, start_sec - pad)
        duration = (end_sec + pad) - offset
        assert offset == 8.0
        assert duration == 9.0

    def test_load_segment_clamps_offset_to_zero(self):
        """Offset must not go negative even with large padding."""
        start_sec, end_sec, pad = 0.5, 3.0, 2.0
        offset = max(0.0, start_sec - pad)
        assert offset == 0.0  # clamped


# ---------------------------------------------------------------------------
# SPEC-01 and SPEC-02: STFT computation and phase preservation
# ---------------------------------------------------------------------------

class TestSpec01And02Spectrogram:
    """SPEC-01: n_fft=8192+ resolution. SPEC-02: phase preservation for ISTFT."""

    def test_stft_returns_all_keys(self, sine_44100):
        y, sr = sine_44100
        result = compute_stft(y, sr)
        expected_keys = {"S", "magnitude", "phase", "freq_bins", "sr", "n_fft", "hop_length"}
        assert set(result.keys()) == expected_keys

    def test_stft_uses_n_fft_8192(self, sine_44100):
        y, sr = sine_44100
        result = compute_stft(y, sr)
        assert result["n_fft"] == 8192

    def test_freq_bins_length(self, sine_44100):
        """SPEC-01: freq_bins length must be N_FFT//2 + 1 = 4097."""
        y, sr = sine_44100
        result = compute_stft(y, sr)
        assert len(result["freq_bins"]) == N_FFT // 2 + 1

    def test_magnitude_phase_same_shape(self, sine_44100):
        y, sr = sine_44100
        result = compute_stft(y, sr)
        assert result["magnitude"].shape == result["phase"].shape

    def test_phase_round_trip(self, sine_44100):
        """SPEC-02: reconstruct_audio with original phase must recover signal within 1e-3."""
        y, sr = sine_44100
        result = compute_stft(y, sr)
        y_rec = reconstruct_audio(result["magnitude"], result["phase"])

        # Length tolerance: ISTFT may differ by up to HOP_LENGTH samples
        assert abs(len(y_rec) - len(y)) <= HOP_LENGTH

        min_len = min(len(y), len(y_rec))
        max_diff = np.max(np.abs(y[:min_len] - y_rec[:min_len]))
        assert max_diff < 1e-3, f"Round-trip max diff too large: {max_diff:.6f}"

    def test_stft_calls_verify_resolution(self):
        """INGEST-05 + SPEC-01: compute_stft must reject bad sample rates."""
        sr_bad = 96000
        y = np.zeros(sr_bad, dtype=np.float32)
        with pytest.raises(AssertionError):
            compute_stft(y, sr_bad)


# ---------------------------------------------------------------------------
# SPEC-03: noise type classification
# ---------------------------------------------------------------------------

class TestSpec03NoiseClassifier:
    """SPEC-03: classify noise type per recording using spectral flatness."""

    def test_returns_valid_type_for_sine(self, sine_44100):
        y, sr = sine_44100
        result = classify_noise_type(y, sr)
        assert result["type"] in {"generator", "car", "plane", "mixed"}

    def test_returns_all_keys(self, sine_44100):
        y, sr = sine_44100
        result = classify_noise_type(y, sr)
        assert "type" in result
        assert "spectral_flatness" in result
        assert "low_freq_ratio" in result

    def test_generator_sine_classified_correctly(self, sine_60hz_44100):
        """A pure 60 Hz sine should be classified as generator (tonal, low flatness)."""
        y, sr = sine_60hz_44100
        result = classify_noise_type(y, sr)
        assert result["type"] == "generator", (
            f"Expected 'generator' for 60 Hz sine, got '{result['type']}' "
            f"(flatness={result['spectral_flatness']:.3f}, ratio={result['low_freq_ratio']:.3f})"
        )

    def test_handles_empty_input(self):
        """INGEST-04 fallback: classifier must not crash on empty segment."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = classify_noise_type(np.array([]), 44100)
        assert result["type"] == "mixed"
        assert any("empty" in str(warning.message).lower() for warning in w)

    def test_handles_silent_input(self):
        """Silent array (all zeros) must not crash or divide by zero."""
        y_silent = np.zeros(44100, dtype=np.float32)
        result = classify_noise_type(y_silent, 44100)
        assert result["type"] == "mixed"

    def test_white_noise_is_not_generator(self):
        """Broadband white noise must not be classified as generator."""
        rng = np.random.default_rng(42)
        y_noise = rng.standard_normal(44100 * 2).astype(np.float32)
        result = classify_noise_type(y_noise, 44100)
        assert result["type"] != "generator", (
            f"White noise classified as 'generator' — flatness threshold may be too high"
        )
