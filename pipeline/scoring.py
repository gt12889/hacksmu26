"""
Acoustic confidence scoring for batch processing (BATCH-02).

Provides:
  - compute_snr_db: SNR in dB (harmonic band vs out-of-band noise power)
  - compute_confidence: 0-100 confidence score combining SNR improvement,
    harmonic integrity, and f0 stability
"""
from __future__ import annotations

import numpy as np


def compute_snr_db(
    magnitude: np.ndarray,  # shape (n_freq_bins, n_frames)
    freq_bins: np.ndarray,  # shape (n_freq_bins,) — Hz per bin
    f0_median: float,       # median f0 in Hz (harmonic spacing)
    bandwidth_hz: float = 5.0,
) -> float:
    """
    Compute SNR in dB: harmonic band power vs out-of-band noise power.

    SNR is computed on linear power (magnitude**2), NOT on dB-scale magnitude.

    Args:
        magnitude:    Magnitude spectrogram, shape (n_freq_bins, n_frames)
        freq_bins:    Frequency value per bin in Hz, shape (n_freq_bins,)
        f0_median:    Median f0 in Hz (used as harmonic spacing)
        bandwidth_hz: Half-bandwidth around each harmonic (±bandwidth_hz)

    Returns:
        SNR in dB as float. Returns -999.0 if no harmonic bins found.
    """
    harmonic_mask = np.zeros(len(freq_bins), dtype=bool)
    for k in range(1, 20):
        center = k * f0_median
        if center > freq_bins[-1]:
            break
        harmonic_mask |= (
            (freq_bins >= center - bandwidth_hz) & (freq_bins <= center + bandwidth_hz)
        )

    if not harmonic_mask.any():
        return -999.0

    signal_power = float(np.mean(magnitude[harmonic_mask, :] ** 2))
    noise_power = float(np.mean(magnitude[~harmonic_mask, :] ** 2)) if (~harmonic_mask).any() else 1e-10
    return float(10 * np.log10(signal_power / (noise_power + 1e-10)))


def compute_confidence(
    f0_contour: np.ndarray,   # shape (n_frames,) — per-frame f0 in Hz
    snr_before: float,
    snr_after: float,
    harmonic_bins_total: int,
    harmonic_bins_masked: int,
) -> float:
    """
    Compute 0–100 confidence score for a denoised call.

    Components:
      - SNR improvement (0–40 pts): delta_snr capped at 20 dB -> 40 pts
      - Harmonic integrity (0–40 pts): harmonic_bins_masked / harmonic_bins_total
      - f0 stability (0–20 pts): 1 - (f0_std / f0_mean), capped at [0, 1]

    Args:
        f0_contour:           Per-frame f0 estimates in Hz, shape (n_frames,)
        snr_before:           SNR before denoising (dB)
        snr_after:            SNR after denoising (dB)
        harmonic_bins_total:  Total number of harmonic frequency bins
        harmonic_bins_masked: Number of harmonic bins covered by comb mask

    Returns:
        Confidence score as float in [0.0, 100.0]
    """
    # SNR improvement component (0–40 pts)
    snr_delta = max(0.0, snr_after - snr_before)
    snr_score = min(snr_delta / 20.0, 1.0) * 40.0

    # Harmonic integrity component (0–40 pts)
    if harmonic_bins_total > 0:
        integrity_score = (harmonic_bins_masked / harmonic_bins_total) * 40.0
    else:
        integrity_score = 0.0

    # f0 stability component (0–20 pts)
    f0_mean = float(np.mean(f0_contour))
    f0_std = float(np.std(f0_contour))
    stability = max(0.0, 1.0 - (f0_std / (f0_mean + 1e-6)))
    stability_score = stability * 20.0

    return float(min(100.0, max(0.0, snr_score + integrity_score + stability_score)))
