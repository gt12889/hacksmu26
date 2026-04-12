"""
Tests for pipeline/scoring.py — compute_snr_db and compute_confidence.

All tests use synthetic numpy arrays — no audio files required.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Allow running from repo root without installing as package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.scoring import compute_snr_db, compute_confidence


# ─── compute_snr_db tests ──────────────────────────────────────────────────────

class TestComputeSnrDb:
    """Tests for compute_snr_db."""

    def test_all_harmonic_bins_returns_positive_snr(self):
        """All-harmonic-bin signal should yield SNR > 0 dB."""
        sr = 44100
        n_fft = 8192
        n_frames = 20
        freq_bins = np.linspace(0, sr / 2, n_fft // 2 + 1)

        f0_median = 14.0  # Hz — elephant rumble fundamental
        # Build magnitude: strong signal at each harmonic, low noise everywhere else
        magnitude = np.ones((len(freq_bins), n_frames)) * 0.01  # low baseline

        # Add strong energy at harmonic multiples of f0
        for k in range(1, 20):
            center = k * f0_median
            if center > freq_bins[-1]:
                break
            harmonic_idx = np.argmin(np.abs(freq_bins - center))
            magnitude[harmonic_idx, :] = 100.0

        snr = compute_snr_db(magnitude, freq_bins, f0_median)
        assert snr > 0.0, f"Expected positive SNR, got {snr}"

    def test_no_harmonic_bins_returns_sentinel(self):
        """f0_median above Nyquist — even 1st harmonic exceeds max freq bin, returns -999.0."""
        # freq_bins only go up to 100 Hz; f0=200 means 1*f0=200 > 100 → no bins found
        freq_bins = np.linspace(0.0, 100.0, 50)
        magnitude = np.ones((len(freq_bins), 10))
        f0_median = 200.0  # 1st harmonic = 200 Hz > 100 Hz max

        snr = compute_snr_db(magnitude, freq_bins, f0_median)
        assert snr == -999.0, f"Expected -999.0 sentinel, got {snr}"

    def test_returns_float(self):
        """Return type must be float."""
        freq_bins = np.array([0.0, 14.0, 28.0, 42.0, 100.0])
        magnitude = np.ones((len(freq_bins), 5))
        snr = compute_snr_db(magnitude, freq_bins, 14.0)
        assert isinstance(snr, float), f"Expected float, got {type(snr)}"


# ─── compute_confidence tests ──────────────────────────────────────────────────

class TestComputeConfidence:
    """Tests for compute_confidence."""

    def test_perfect_score_returns_100(self):
        """
        Perfect input: large SNR delta (>=20 dB), 100% masked bins, stable f0.
        Expected: 100.0
        """
        f0_contour = np.full(10, 14.0)  # perfectly stable f0
        score = compute_confidence(
            f0_contour=f0_contour,
            snr_before=5.0,
            snr_after=25.0,        # delta = 20 dB → full 40 pts
            harmonic_bins_total=100,
            harmonic_bins_masked=100,  # 100% → full 40 pts
        )
        # stability: f0_std=0, f0_mean=14, stability=1.0 → 20 pts
        assert score == pytest.approx(100.0, abs=1e-6), f"Expected 100.0, got {score}"

    def test_zero_score_returns_zero(self):
        """
        Worst case: no SNR improvement, 0 masked bins, maximally unstable f0.
        Uses f0 values that span a wide range relative to mean so stability → 0.
        Expected: exactly 0.0
        """
        # To get 0 stability pts: need f0_std >> f0_mean + 1e-6
        # Use f0 contour where mean is near 0 but std is large
        # e.g. [0, 0, 0, 0, ..., 1000] → mean ~50, std ~224 → stability = 1 - (224/50) < 0 → clamped to 0
        f0_contour = np.array([0.0] * 19 + [1000.0])
        score = compute_confidence(
            f0_contour=f0_contour,
            snr_before=10.0,
            snr_after=10.0,        # delta = 0 → 0 SNR pts
            harmonic_bins_total=100,
            harmonic_bins_masked=0,  # 0% → 0 integrity pts
        )
        # All three components are 0
        assert score == pytest.approx(0.0, abs=1e-6), f"Expected 0.0, got {score}"

    def test_output_clamped_above_100(self):
        """Even if formula overflows, output must not exceed 100.0."""
        f0_contour = np.full(5, 100.0)
        score = compute_confidence(
            f0_contour=f0_contour,
            snr_before=-50.0,
            snr_after=9999.0,
            harmonic_bins_total=10,
            harmonic_bins_masked=10,
        )
        assert score <= 100.0, f"Score must be <= 100.0, got {score}"

    def test_output_clamped_below_zero(self):
        """Output must not be negative."""
        f0_contour = np.array([1.0, 1000.0])
        score = compute_confidence(
            f0_contour=f0_contour,
            snr_before=100.0,
            snr_after=0.0,        # negative delta → clamped at 0
            harmonic_bins_total=50,
            harmonic_bins_masked=0,
        )
        assert score >= 0.0, f"Score must be >= 0.0, got {score}"

    def test_zero_harmonic_bins_total_no_div_zero(self):
        """harmonic_bins_total=0 must not raise ZeroDivisionError."""
        f0_contour = np.full(5, 14.0)
        score = compute_confidence(
            f0_contour=f0_contour,
            snr_before=0.0,
            snr_after=20.0,
            harmonic_bins_total=0,
            harmonic_bins_masked=0,
        )
        # integrity_score = 0 (guarded); SNR: 40 pts; stability: 20 pts
        assert score == pytest.approx(60.0, abs=1e-6), f"Expected 60.0, got {score}"

    def test_returns_float(self):
        """Return type must be float."""
        score = compute_confidence(
            f0_contour=np.full(5, 14.0),
            snr_before=5.0,
            snr_after=15.0,
            harmonic_bins_total=100,
            harmonic_bins_masked=50,
        )
        assert isinstance(score, float), f"Expected float, got {type(score)}"
