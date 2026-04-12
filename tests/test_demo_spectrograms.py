"""
Tests for scripts/demo_spectrograms.py — Phase 3 demo figure and WAV export.

TDD RED phase: these tests define the expected behavior before implementation.

Coverage:
  - compute_snr_db: returns float, positive for harmonic-boosted magnitude
  - build_synthetic_call: correct dtype, length, noise_type dict
  - make_demo_figure: creates PNG and WAV files, PNG is large (300 dpi)
  - test_all_three_noise_types: generator/car/plane all produce output files
  - test_wav_is_valid_pcm: soundfile can read WAV back, normalized to [-1,1]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from scripts.demo_spectrograms import (  # noqa: E402
    build_synthetic_call,
    compute_snr_db,
    make_demo_figure,
)
from pipeline.harmonic_processor import process_call  # noqa: E402
import librosa  # noqa: E402


# ─── Test 1: compute_snr_db returns float ──────────────────────────────────────

def test_compute_snr_db_returns_float():
    """compute_snr_db must return a plain Python float."""
    magnitude = np.ones((4097, 50), dtype=np.float32)
    freq_bins = librosa.fft_frequencies(sr=44100, n_fft=8192)
    result = compute_snr_db(magnitude, freq_bins, f0_median=14.0)
    assert isinstance(result, float), f"Expected float, got {type(result)}"


# ─── Test 2: SNR positive for harmonic-boosted signal ─────────────────────────

def test_compute_snr_db_positive_for_harmonic_signal():
    """When harmonic bins are 10x louder than background, SNR must be > 0 dB."""
    magnitude = np.ones((4097, 50), dtype=np.float32) * 0.01
    freq_bins = librosa.fft_frequencies(sr=44100, n_fft=8192)
    # Boost harmonics of f0=14 Hz
    for k in range(1, 10):
        bin_idx = round(k * 14.0 / freq_bins[1])
        if 0 <= bin_idx < magnitude.shape[0]:
            magnitude[bin_idx, :] = 10.0
    result = compute_snr_db(magnitude, freq_bins, f0_median=14.0)
    assert result > 0.0, f"Expected positive SNR for harmonic-boosted magnitude, got {result:.2f} dB"


# ─── Test 3: build_synthetic_call shapes and types ────────────────────────────

def test_build_synthetic_call_shapes():
    """build_synthetic_call must return float32 audio of expected length."""
    y, sr, noise_clip, noise_type_dict = build_synthetic_call("generator")
    assert y.dtype == np.float32, f"Expected float32, got {y.dtype}"
    assert len(y) == int(6.0 * 44100), f"Expected {int(6.0*44100)} samples, got {len(y)}"
    assert noise_type_dict["type"] == "generator"
    assert len(noise_clip) > 0, "noise_clip must be non-empty"


# ─── Test 4: make_demo_figure creates PNG and WAV ─────────────────────────────

def test_make_demo_figure_creates_files(tmp_path):
    """make_demo_figure must produce a PNG and WAV file at expected paths."""
    y, sr, noise_clip, noise_type_dict = build_synthetic_call("car")
    ctx = process_call(y, sr, noise_type_dict, noise_clip=noise_clip)
    png_path, wav_path, wav_original_path = make_demo_figure("car", ctx, y, tmp_path)
    assert png_path.exists(), f"PNG file not found: {png_path}"
    assert wav_path.exists(), f"WAV file not found: {wav_path}"
    assert wav_original_path.exists(), f"Original WAV not found: {wav_original_path}"
    # 300 dpi 18x5 figure — should be well above 50KB
    assert png_path.stat().st_size > 50_000, (
        f"PNG is suspiciously small ({png_path.stat().st_size} bytes); "
        "expected 300 dpi figure to be > 50 KB"
    )


# ─── Test 5: All three noise types produce output files ───────────────────────

def test_all_three_noise_types_produce_files(tmp_path):
    """Covers DEMO-01 (one call per type), DEMO-02 (PNG), DEMO-07 (WAV)."""
    for noise_type in ["generator", "car", "plane"]:
        y, sr, noise_clip, noise_type_dict = build_synthetic_call(noise_type)
        ctx = process_call(y, sr, noise_type_dict, noise_clip=noise_clip)
        png_path, wav_path, wav_original_path = make_demo_figure(noise_type, ctx, y, tmp_path)
        assert png_path.exists(), f"PNG missing for noise_type={noise_type}"
        assert wav_path.exists(), f"WAV missing for noise_type={noise_type}"
        assert wav_original_path.exists(), f"Original WAV missing for noise_type={noise_type}"


# ─── Test 6: WAV is valid PCM, normalized to [-1, 1] ─────────────────────────

def test_wav_is_valid_pcm(tmp_path):
    """Cleaned WAV must be readable by soundfile and normalized to [-1, 1]."""
    import soundfile as sf

    y, sr, noise_clip, noise_type_dict = build_synthetic_call("plane")
    ctx = process_call(y, sr, noise_type_dict, noise_clip=noise_clip)
    _, wav_path, _orig = make_demo_figure("plane", ctx, y, tmp_path)

    audio, read_sr = sf.read(str(wav_path))
    assert read_sr == sr, f"Sample rate mismatch: expected {sr}, got {read_sr}"
    assert len(audio) > 0, "WAV file is empty"
    assert np.max(np.abs(audio)) <= 1.0, (
        f"Audio not normalized: max abs = {np.max(np.abs(audio)):.4f}"
    )
