"""
Tests for pipeline/spectrogram.py — STFT phase preservation round-trip.
Covers SPEC-01 (infrasonic resolution) and SPEC-02 (phase preservation).
"""

import numpy as np
import pytest

from pipeline.spectrogram import compute_stft, reconstruct_audio
from pipeline.config import N_FFT, HOP_LENGTH


SR = 44100


@pytest.fixture
def sine_20hz():
    """1-second 20 Hz sine wave at 44100 Hz — infrasonic test signal."""
    t = np.linspace(0, 1.0, SR, dtype=np.float32)
    return np.sin(2 * np.pi * 20 * t), SR


def test_compute_stft_returns_all_keys(sine_20hz):
    y, sr = sine_20hz
    result = compute_stft(y, sr)
    assert set(result.keys()) == {"S", "magnitude", "phase", "freq_bins", "sr", "n_fft", "hop_length"}


def test_compute_stft_uses_n_fft_constant(sine_20hz):
    y, sr = sine_20hz
    result = compute_stft(y, sr)
    assert result["n_fft"] == N_FFT
    assert result["hop_length"] == HOP_LENGTH
    assert result["sr"] == sr


def test_compute_stft_freq_bins_length(sine_20hz):
    y, sr = sine_20hz
    result = compute_stft(y, sr)
    expected_bins = N_FFT // 2 + 1  # == 4097 at N_FFT=8192
    assert len(result["freq_bins"]) == expected_bins


def test_compute_stft_magnitude_phase_shape_match(sine_20hz):
    y, sr = sine_20hz
    result = compute_stft(y, sr)
    assert result["magnitude"].shape == result["phase"].shape
    assert result["magnitude"].shape[0] == N_FFT // 2 + 1


def test_reconstruct_audio_length_within_hop(sine_20hz):
    y, sr = sine_20hz
    result = compute_stft(y, sr)
    y_reconstructed = reconstruct_audio(result["magnitude"], result["phase"])
    assert abs(len(y_reconstructed) - len(y)) <= HOP_LENGTH


def test_phase_round_trip_error_below_threshold(sine_20hz):
    """Phase-preserved round-trip must produce near-identical audio (max abs diff < 1e-3)."""
    y, sr = sine_20hz
    result = compute_stft(y, sr)
    y_reconstructed = reconstruct_audio(result["magnitude"], result["phase"])
    n = min(len(y), len(y_reconstructed))
    max_diff = float(np.max(np.abs(y[:n] - y_reconstructed[:n])))
    assert max_diff < 1e-3, f"Round-trip error too large: {max_diff:.6f}"


def test_compute_stft_calls_verify_resolution():
    """compute_stft should raise AssertionError on a sample rate that fails resolution check."""
    sr_bad = 96000  # 96000 / 8192 = 11.72 Hz/bin — exceeds 6 Hz limit
    y = np.zeros(sr_bad, dtype=np.float32)
    with pytest.raises(AssertionError, match="Frequency resolution"):
        compute_stft(y, sr_bad)
