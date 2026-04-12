"""
Noise type classification from noise-only audio segments.
Covers SPEC-03: classify noise as generator / car / plane / mixed.

Strategy:
  - Generator: tonal (low flatness) with concentrated energy at 25-100 Hz (harmonic hum)
  - Car: broadband (high flatness) + high temporal variance (engine revving, transients)
  - Plane: broadband (high flatness) + low temporal variance (steady drone/sweep)
  - Mixed: neither extreme — use non-stationary noisereduce in Phase 2
"""

from __future__ import annotations

import warnings

import librosa
import numpy as np

from pipeline.config import (
    FLATNESS_BROADBAND_THRESHOLD,
    FLATNESS_TONAL_THRESHOLD,
    HOP_LENGTH,
    N_FFT,
)

# Frequency range used to check for generator harmonic hum signature (Hz)
GENERATOR_LOW_FREQ_MIN_HZ = 25.0
GENERATOR_LOW_FREQ_MAX_HZ = 100.0
GENERATOR_LOW_FREQ_RATIO_THRESHOLD = 0.3

# Temporal variance threshold separating car (high) from plane (low)
CAR_TEMPORAL_VARIANCE_THRESHOLD = 0.05


def classify_noise_type(y_noise: np.ndarray, sr: int) -> dict:
    """
    Classify noise type from a noise-only audio segment. (SPEC-03)

    This classification drives Phase 2 denoising strategy selection:
      - generator → stationary noisereduce (CLEAN-02)
      - car / plane / mixed → non-stationary noisereduce (CLEAN-01)

    Args:
        y_noise: Audio array for a noise-only segment (float32 or float64)
        sr: Sample rate of the audio

    Returns:
        dict with keys:
          type             - "generator" | "car" | "plane" | "mixed"
          spectral_flatness - mean spectral flatness in [0, 1]
          low_freq_ratio   - fraction of energy in 25-100 Hz band
    """
    # Guard: empty or silent segment — cannot classify, default to mixed
    if len(y_noise) == 0 or np.max(np.abs(y_noise)) < 1e-10:
        warnings.warn(
            "[noise_classifier] Empty or silent noise segment — defaulting to 'mixed'. "
            "Check that noise gaps exist in the recording.",
            RuntimeWarning,
            stacklevel=2,
        )
        return {
            "type": "mixed",
            "spectral_flatness": 0.0,
            "low_freq_ratio": 0.0,
        }

    # Spectral flatness: ratio of geometric mean to arithmetic mean of power spectrum.
    # Generator noise (tonal) → low flatness (~0.01-0.05)
    # Broadband noise (car/plane) → high flatness (~0.5-0.9)
    flatness_frames = librosa.feature.spectral_flatness(y=y_noise)
    mean_flatness = float(np.mean(flatness_frames))

    # Check for concentrated energy in the generator hum frequency band (25-100 Hz)
    S = np.abs(librosa.stft(y_noise, n_fft=N_FFT, hop_length=HOP_LENGTH))
    freq_bins = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    low_freq_mask = (freq_bins >= GENERATOR_LOW_FREQ_MIN_HZ) & (
        freq_bins <= GENERATOR_LOW_FREQ_MAX_HZ
    )
    low_freq_power = float(np.mean(S[low_freq_mask, :])) if np.any(low_freq_mask) else 0.0
    total_power = float(np.mean(S))
    low_freq_ratio = low_freq_power / (total_power + 1e-10)

    # Classification decision tree
    if (
        mean_flatness < FLATNESS_TONAL_THRESHOLD
        and low_freq_ratio > GENERATOR_LOW_FREQ_RATIO_THRESHOLD
    ):
        noise_type = "generator"
    elif mean_flatness > FLATNESS_BROADBAND_THRESHOLD:
        # Distinguish car (transient, high temporal variance) vs plane (steady, low variance)
        # Column-wise mean power over time
        temporal_power = np.mean(S, axis=0)  # shape: (time_frames,)
        temporal_variance = float(np.var(temporal_power))
        noise_type = "car" if temporal_variance > CAR_TEMPORAL_VARIANCE_THRESHOLD else "plane"
    else:
        noise_type = "mixed"

    print(
        f"[noise_classifier] type={noise_type}, "
        f"flatness={mean_flatness:.3f}, "
        f"low_freq_ratio={low_freq_ratio:.3f}"
    )

    return {
        "type": noise_type,
        "spectral_flatness": mean_flatness,
        "low_freq_ratio": low_freq_ratio,
    }
