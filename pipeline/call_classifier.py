"""
Heuristic call-type classifier for elephant vocalizations.

Classifies a call segment into one of four types based on acoustic features
derived from the existing pipeline outputs:

  rumble  — infrasonic (f0 10-25 Hz), long duration, harmonic, low f0 modulation
  trumpet — broadband transient, f0 > 100 Hz, short-medium duration
  roar    — broadband sustained, high spectral flatness, no clear low f0
  unknown — everything else that does not cleanly fit above categories

Features used:
  - f0_contour:      per-frame fundamental frequency from detect_f0_shs (HARM-03)
  - duration:        call length in seconds (len(y) / sr)
  - spectral_flatness: mean flatness via librosa.feature.spectral_flatness
  - harmonic_dominance: fraction of spectral energy at integer multiples of f0

Thresholds are grounded in elephant bioacoustics literature:
  Li et al. 2021 "Elephant rumble" — f0 8-25 Hz, strong harmonic series
  Soltis 2010 "Trumpet" — broadband burst, usually >200 Hz apparent pitch
  Poole 1996 "Roar" — aperiodic burst, broadband, high spectral flatness
"""
from __future__ import annotations

import librosa
import numpy as np

from pipeline.config import HOP_LENGTH, N_FFT

# --- Rumble thresholds ---
RUMBLE_F0_MIN_HZ: float = 8.0          # Hz — SHS sweeps from 8 Hz
RUMBLE_F0_MAX_HZ: float = 35.0         # Hz — allow a small margin above 25 Hz
RUMBLE_MIN_DURATION_SEC: float = 0.4   # seconds — rumbles are sustained
RUMBLE_FLATNESS_MAX: float = 0.30      # flat spectrum is NOT tonal rumble
RUMBLE_HARMONIC_DOMINANCE_MIN: float = 0.15  # at least 15 % of energy at harmonics

# --- Trumpet thresholds ---
# NOTE: the SHS f0 detector is calibrated only for 8-25 Hz infrasound; for non-rumble
# calls it returns values near the edge of that range or 0 (unvoiced). Trumpet
# identification must NOT rely on f0 being above infrasound — it uses broadband flatness,
# duration, and the ABSENCE of harmonic dominance at infrasonic harmonics.
TRUMPET_MAX_DURATION_SEC: float = 2.0  # seconds — transient burst
TRUMPET_MIN_DURATION_SEC: float = 0.15  # seconds — not an impulse noise
TRUMPET_FLATNESS_MIN: float = 0.25     # trumpets are broadband
TRUMPET_HARM_DOM_MAX: float = 0.25     # low harmonic dominance in 8-25 Hz range

# --- Roar thresholds ---
ROAR_MIN_DURATION_SEC: float = 0.5     # seconds — sustained aperiodic noise
ROAR_FLATNESS_MIN: float = 0.35        # must be broadband
ROAR_F0_MAX_HZ: float = 50.0          # Hz — no strong low-frequency pitch

# Harmonic search: sum energy at k*f0 up to this ceiling
HARMONIC_CEILING_HZ: float = 1000.0


def _median_f0(f0_contour: np.ndarray) -> float:
    """Return the median of the f0 contour, ignoring zero/unvoiced frames."""
    voiced = f0_contour[f0_contour > 0]
    if len(voiced) == 0:
        return 0.0
    return float(np.median(voiced))


def _f0_modulation(f0_contour: np.ndarray) -> float:
    """
    Fractional variation of f0 over time.

    Returns std(f0_voiced) / mean(f0_voiced), or 0.0 if no voiced frames.
    High modulation (~> 0.5) suggests sweep/trumpet rather than stable rumble.
    """
    voiced = f0_contour[f0_contour > 0]
    if len(voiced) < 2:
        return 0.0
    mean_f0 = float(np.mean(voiced))
    if mean_f0 < 1e-6:
        return 0.0
    return float(np.std(voiced) / mean_f0)


def _compute_harmonic_dominance(
    y: np.ndarray,
    sr: int,
    f0: float,
) -> float:
    """
    Fraction of total spectral energy at integer harmonic bins of f0.

    Sums the magnitude at k*f0 for k = 1, 2, ... up to HARMONIC_CEILING_HZ,
    using a ±1-bin window at each harmonic to account for bin rounding.

    Returns a value in [0, 1].  Returns 0.0 when f0 <= 0.
    """
    if f0 <= 0:
        return 0.0

    S = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH))
    hz_per_bin = sr / N_FFT
    n_bins = S.shape[0]

    total_energy = float(np.sum(S))
    if total_energy < 1e-10:
        return 0.0

    harmonic_energy = 0.0
    k = 1
    while k * f0 <= HARMONIC_CEILING_HZ:
        center_bin = int(round(k * f0 / hz_per_bin))
        lo = max(0, center_bin - 1)
        hi = min(n_bins - 1, center_bin + 1)
        harmonic_energy += float(np.sum(S[lo : hi + 1, :]))
        k += 1

    return harmonic_energy / total_energy


def _compute_spectral_flatness(y: np.ndarray) -> float:
    """Mean spectral flatness over all frames (wrapper matching noise_classifier pattern)."""
    flatness_frames = librosa.feature.spectral_flatness(y=y)
    return float(np.mean(flatness_frames))


def classify_call_type(
    y: np.ndarray,
    sr: int,
    f0_contour: np.ndarray,
) -> dict:
    """
    Heuristic call-type classifier.

    Args:
        y:           Audio array for the call segment (float32 or float64).
                     Should be the raw/padded segment, NOT the denoised output,
                     so that broadband features are preserved.
        sr:          Native sample rate.
        f0_contour:  Per-frame f0 array from detect_f0_shs(), shape (n_frames,).
                     Values of 0 mean unvoiced / no detected pitch.

    Returns:
        dict with keys:
          type            - "rumble" | "trumpet" | "roar" | "unknown"
          confidence      - float in [0.0, 1.0]
          f0_median_hz    - median voiced f0 (diagnostic)
          duration_sec    - call duration in seconds (diagnostic)
          spectral_flatness - mean spectral flatness (diagnostic)
          harmonic_dominance - fraction of energy at harmonic series (diagnostic)
    """
    # Guard: silent / empty
    if len(y) == 0 or np.max(np.abs(y)) < 1e-10:
        return {
            "type": "unknown",
            "confidence": 0.0,
            "f0_median_hz": 0.0,
            "duration_sec": 0.0,
            "spectral_flatness": 0.0,
            "harmonic_dominance": 0.0,
        }

    duration_sec = len(y) / sr
    f0_med = _median_f0(f0_contour)
    flatness = _compute_spectral_flatness(y)
    harm_dom = _compute_harmonic_dominance(y, sr, f0_med)

    call_type, confidence = _apply_rules(
        f0_med=f0_med,
        duration_sec=duration_sec,
        flatness=flatness,
        harm_dom=harm_dom,
    )

    return {
        "type": call_type,
        "confidence": confidence,
        "f0_median_hz": f0_med,
        "duration_sec": duration_sec,
        "spectral_flatness": flatness,
        "harmonic_dominance": harm_dom,
    }


def _apply_rules(
    f0_med: float,
    duration_sec: float,
    flatness: float,
    harm_dom: float,
) -> tuple[str, float]:
    """
    Core rule-based decision logic.  Separated for testability.

    Returns:
        (call_type, confidence) tuple.

    Decision logic:
      1. Rumble: low f0, long duration, low flatness, harmonic structure.
      2. Trumpet: apparent pitch above infrasound range, transient.
      3. Roar: broadband sustained, high flatness, no strong low f0.
      4. Unknown: everything else.

    Confidence is computed from how many sub-criteria are satisfied, normalized
    to [0, 1] per type.  This produces a graded signal even for borderline cases.
    """
    # --- RUMBLE ---
    # All four criteria contribute to confidence.
    rumble_votes = 0
    rumble_max = 4
    if RUMBLE_F0_MIN_HZ <= f0_med <= RUMBLE_F0_MAX_HZ:
        rumble_votes += 1
    if duration_sec >= RUMBLE_MIN_DURATION_SEC:
        rumble_votes += 1
    if flatness < RUMBLE_FLATNESS_MAX:
        rumble_votes += 1
    if harm_dom >= RUMBLE_HARMONIC_DOMINANCE_MIN:
        rumble_votes += 1

    # --- TRUMPET ---
    # Broadband transient: no infrasonic harmonic structure, short-medium duration,
    # higher spectral flatness than rumble.
    # NOTE: The SHS f0 detector returns values in 8-25 Hz for all inputs; we cannot
    # use f0_med > threshold as a reliable trumpet marker. Instead, use low harmonic
    # dominance (energy is NOT concentrated at 8-25 Hz harmonics) + duration.
    trumpet_votes = 0
    trumpet_max = 3
    if harm_dom < TRUMPET_HARM_DOM_MAX:
        # Little energy at infrasonic harmonic series → not a rumble-like call
        trumpet_votes += 1
    if TRUMPET_MIN_DURATION_SEC <= duration_sec <= TRUMPET_MAX_DURATION_SEC:
        trumpet_votes += 1
    if flatness >= TRUMPET_FLATNESS_MIN:
        # Trumpets are broadband (more noise-like than a clean rumble)
        trumpet_votes += 1

    # --- ROAR ---
    # Broadband sustained noise, no strong low pitch
    roar_votes = 0
    roar_max = 3
    if flatness >= ROAR_FLATNESS_MIN:
        roar_votes += 1
    if duration_sec >= ROAR_MIN_DURATION_SEC:
        roar_votes += 1
    if f0_med == 0 or f0_med > ROAR_F0_MAX_HZ or harm_dom < 0.10:
        # roar: no coherent infrasonic f0 or harmonic structure is weak
        roar_votes += 1

    rumble_conf = rumble_votes / rumble_max
    trumpet_conf = trumpet_votes / trumpet_max
    roar_conf = roar_votes / roar_max

    # Arbitrate: pick the highest confidence, break ties toward "unknown"
    best_conf = max(rumble_conf, trumpet_conf, roar_conf)

    # Require at least 50 % of criteria to make a positive call
    THRESHOLD = 0.5
    if best_conf < THRESHOLD:
        return "unknown", round(1.0 - best_conf, 3)

    if rumble_conf == best_conf:
        return "rumble", round(rumble_conf, 3)
    if trumpet_conf == best_conf:
        return "trumpet", round(trumpet_conf, 3)
    if roar_conf == best_conf:
        return "roar", round(roar_conf, 3)

    return "unknown", round(1.0 - best_conf, 3)
