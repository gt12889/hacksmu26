"""
Tests for pipeline/noise_classifier.py — spectral flatness noise type classification.
Covers SPEC-03: classify noise as generator / car / plane / mixed.
"""

import warnings

import numpy as np
import pytest

from pipeline.noise_classifier import classify_noise_type


SR = 44100
VALID_TYPES = {"generator", "car", "plane", "mixed"}


@pytest.fixture
def sine_60hz():
    """2-second 60 Hz tonal sine wave (generator-like: low flatness, concentrated energy)."""
    t = np.linspace(0, 2.0, SR * 2, dtype=np.float32)
    return np.sin(2 * np.pi * 60 * t)


@pytest.fixture
def white_noise():
    """2-second white noise (broadband: high flatness)."""
    rng = np.random.default_rng(42)
    return rng.standard_normal(SR * 2).astype(np.float32)


def test_classify_returns_valid_type(sine_60hz):
    result = classify_noise_type(sine_60hz, SR)
    assert result["type"] in VALID_TYPES


def test_classify_returns_all_keys(sine_60hz):
    result = classify_noise_type(sine_60hz, SR)
    assert set(result.keys()) == {"type", "spectral_flatness", "low_freq_ratio"}


def test_classify_tonal_60hz_returns_generator(sine_60hz):
    """A pure 60 Hz sine wave has very low spectral flatness and is in the generator hum band."""
    result = classify_noise_type(sine_60hz, SR)
    assert result["type"] == "generator", (
        f"Expected 'generator' for tonal 60 Hz sine, got '{result['type']}'. "
        f"flatness={result['spectral_flatness']:.4f}, low_freq_ratio={result['low_freq_ratio']:.4f}"
    )


def test_classify_white_noise_not_generator(white_noise):
    """White noise has high spectral flatness — must NOT be classified as generator."""
    result = classify_noise_type(white_noise, SR)
    assert result["type"] != "generator", (
        f"White noise should not be classified as generator, got '{result['type']}'"
    )
    assert result["type"] in VALID_TYPES


def test_classify_empty_array_returns_mixed_with_warning():
    """Empty noise segment must return type='mixed' and emit a RuntimeWarning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = classify_noise_type(np.array([], dtype=np.float32), SR)
    assert result["type"] == "mixed"
    assert result["spectral_flatness"] == 0.0
    assert result["low_freq_ratio"] == 0.0
    assert len(w) == 1
    assert issubclass(w[0].category, RuntimeWarning)


def test_classify_silent_array_returns_mixed_with_warning():
    """All-zeros segment (silent) must return type='mixed' and emit a RuntimeWarning."""
    silent = np.zeros(SR, dtype=np.float32)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = classify_noise_type(silent, SR)
    assert result["type"] == "mixed"
    assert len(w) == 1
    assert issubclass(w[0].category, RuntimeWarning)


def test_classify_spectral_flatness_in_range(sine_60hz, white_noise):
    """spectral_flatness must be a float in [0, 1]."""
    r1 = classify_noise_type(sine_60hz, SR)
    r2 = classify_noise_type(white_noise, SR)
    for r, label in [(r1, "tonal"), (r2, "noise")]:
        v = r["spectral_flatness"]
        assert isinstance(v, float), f"{label}: spectral_flatness must be float"
        assert 0.0 <= v <= 1.0, f"{label}: spectral_flatness out of range: {v}"


def test_classify_low_freq_ratio_nonnegative(sine_60hz):
    result = classify_noise_type(sine_60hz, SR)
    assert result["low_freq_ratio"] >= 0.0
