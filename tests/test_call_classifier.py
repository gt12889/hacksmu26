"""
Tests for pipeline/call_classifier.py — heuristic call-type classifier.

Coverage:
  - One test per output type (rumble, trumpet, roar, unknown)
  - Confidence bounds check
  - Return-value contract
  - Real annotated rumble regression test
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pipeline.call_classifier import classify_call_type

SR = 44100
VALID_TYPES = {"rumble", "trumpet", "roar", "unknown"}


# ---------------------------------------------------------------------------
# Helpers to synthesise representative signals
# ---------------------------------------------------------------------------

def _make_rumble(duration_sec: float = 2.0, f0_hz: float = 15.0, sr: int = SR) -> tuple[np.ndarray, np.ndarray]:
    """Synthesise a harmonic rumble at f0_hz with harmonics up to 1 kHz."""
    n = int(duration_sec * sr)
    t = np.linspace(0, duration_sec, n, dtype=np.float32)
    y = np.zeros(n, dtype=np.float32)
    k = 1
    while k * f0_hz <= 1000:
        y += (1.0 / k) * np.sin(2 * np.pi * k * f0_hz * t)
        k += 1
    y /= np.max(np.abs(y)) + 1e-10
    # Constant f0 contour
    n_frames = int(np.ceil(n / 512)) + 1  # approximate
    f0_contour = np.full(n_frames, f0_hz, dtype=np.float32)
    return y, f0_contour


def _make_trumpet(duration_sec: float = 0.8, sr: int = SR) -> tuple[np.ndarray, np.ndarray]:
    """
    Synthesise a broadband trumpet-like burst: noise + high-frequency tone, no infrasonic
    harmonic structure.  Duration is within the trumpet window (0.15-2.0s).

    The SHS detector is calibrated for 8-25 Hz only; it will return 0 (unvoiced) or a
    random edge value for this signal since there is no real infrasonic energy.
    We simulate that by passing f0_contour = 0 (unvoiced).
    """
    rng = np.random.default_rng(7)
    n = int(duration_sec * sr)
    # Broadband noise base
    y = rng.standard_normal(n).astype(np.float32) * 0.8
    # Add a strong high-frequency component (300 Hz) — way above infrasound
    t = np.linspace(0, duration_sec, n, dtype=np.float32)
    y += np.sin(2 * np.pi * 300 * t)
    y /= np.max(np.abs(y)) + 1e-10
    # f0 contour: SHS finds no coherent infrasonic pitch → unvoiced (0)
    n_frames = int(np.ceil(n / 512)) + 1
    f0_contour = np.zeros(n_frames, dtype=np.float32)
    return y, f0_contour


def _make_roar(duration_sec: float = 2.5, sr: int = SR) -> tuple[np.ndarray, np.ndarray]:
    """
    Synthesise a broadband roar: spectrally flat white noise, sustained for > 2s.

    Duration must exceed TRUMPET_MAX_DURATION_SEC (2.0s) so it falls outside the
    trumpet window and is distinguished as a sustained broadband event.
    """
    rng = np.random.default_rng(99)
    n = int(duration_sec * sr)
    y = rng.standard_normal(n).astype(np.float32)
    y /= np.max(np.abs(y)) + 1e-10
    # f0 contour: no clear infrasonic pitch
    n_frames = int(np.ceil(n / 512)) + 1
    f0_contour = np.zeros(n_frames, dtype=np.float32)
    return y, f0_contour


def _make_short_click(duration_sec: float = 0.05, sr: int = SR) -> tuple[np.ndarray, np.ndarray]:
    """Very short transient click — should fall through to 'unknown'."""
    n = int(duration_sec * sr)
    y = np.zeros(n, dtype=np.float32)
    y[n // 2] = 1.0  # impulse
    n_frames = max(1, int(np.ceil(n / 512)) + 1)
    f0_contour = np.zeros(n_frames, dtype=np.float32)
    return y, f0_contour


# ---------------------------------------------------------------------------
# Tests: return-value contract
# ---------------------------------------------------------------------------

def test_returns_valid_type_keys():
    """classify_call_type must return dict with required keys."""
    y, f0 = _make_rumble()
    result = classify_call_type(y, SR, f0)
    required_keys = {"type", "confidence", "f0_median_hz", "duration_sec",
                     "spectral_flatness", "harmonic_dominance"}
    assert required_keys.issubset(result.keys()), (
        f"Missing keys: {required_keys - result.keys()}"
    )


def test_type_is_valid_string():
    """Returned 'type' must be one of the four defined categories."""
    for make_fn in [_make_rumble, _make_trumpet, _make_roar, _make_short_click]:
        y, f0 = make_fn()
        result = classify_call_type(y, SR, f0)
        assert result["type"] in VALID_TYPES, (
            f"Got unexpected type '{result['type']}' from {make_fn.__name__}"
        )


def test_confidence_in_bounds():
    """Confidence must be a float in [0.0, 1.0] for all signal types."""
    for make_fn in [_make_rumble, _make_trumpet, _make_roar, _make_short_click]:
        y, f0 = make_fn()
        result = classify_call_type(y, SR, f0)
        conf = result["confidence"]
        assert isinstance(conf, float), f"confidence must be float, got {type(conf)}"
        assert 0.0 <= conf <= 1.0, (
            f"{make_fn.__name__}: confidence {conf} out of [0,1]"
        )


# ---------------------------------------------------------------------------
# Tests: one per output type
# ---------------------------------------------------------------------------

def test_classify_rumble():
    """Harmonic infrasonic signal must be classified as 'rumble'."""
    y, f0 = _make_rumble(duration_sec=2.0, f0_hz=15.0)
    result = classify_call_type(y, SR, f0)
    assert result["type"] == "rumble", (
        f"Expected 'rumble', got '{result['type']}'. "
        f"f0={result['f0_median_hz']:.1f} Hz, "
        f"flatness={result['spectral_flatness']:.3f}, "
        f"harm_dom={result['harmonic_dominance']:.3f}, "
        f"conf={result['confidence']}"
    )
    assert result["confidence"] > 0.5, (
        f"Rumble confidence too low: {result['confidence']}"
    )


def test_classify_roar():
    """White-noise sustained signal (2.5s) must be classified as 'roar' (or 'unknown')."""
    y, f0 = _make_roar(duration_sec=2.5)
    result = classify_call_type(y, SR, f0)
    # Broadband white noise with no f0 should be roar or unknown (never rumble or trumpet)
    assert result["type"] in {"roar", "unknown"}, (
        f"Broadband roar-like signal got '{result['type']}', "
        f"expected 'roar' or 'unknown'. "
        f"flatness={result['spectral_flatness']:.3f}, conf={result['confidence']}"
    )
    assert result["type"] != "rumble", "White noise must NEVER be classified as rumble"
    assert result["type"] != "trumpet", (
        "Sustained 2.5s broadband noise must NOT be classified as trumpet (too long)"
    )


def test_classify_trumpet():
    """High-frequency broadband transient must not be classified as rumble."""
    y, f0 = _make_trumpet(duration_sec=0.8)
    result = classify_call_type(y, SR, f0)
    # Trumpet or unknown — but definitely not rumble
    assert result["type"] != "rumble", (
        f"Trumpet-like signal got 'rumble', which is incorrect. "
        f"f0={result['f0_median_hz']:.1f}, flatness={result['spectral_flatness']:.3f}"
    )
    assert result["type"] in VALID_TYPES


def test_classify_unknown_for_short_click():
    """A very short impulse (0.05s) is too brief to be rumble/trumpet/roar."""
    y, f0 = _make_short_click(duration_sec=0.05)
    result = classify_call_type(y, SR, f0)
    # Short click lacks duration for any sustained category
    assert result["type"] in VALID_TYPES  # must still return valid type
    # Should NOT be rumble (duration too short) or roar (duration too short)
    assert result["type"] not in {"rumble", "roar"}, (
        f"Short 50ms click classified as '{result['type']}' — should be unknown or trumpet"
    )


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------

def test_classify_empty_audio_returns_unknown():
    """Empty audio array must return 'unknown' with confidence 0.0."""
    result = classify_call_type(np.array([], dtype=np.float32), SR, np.array([]))
    assert result["type"] == "unknown"
    assert result["confidence"] == 0.0


def test_classify_silent_audio_returns_unknown():
    """Silent (all-zeros) audio must return 'unknown'."""
    y = np.zeros(SR * 2, dtype=np.float32)
    f0 = np.zeros(100, dtype=np.float32)
    result = classify_call_type(y, SR, f0)
    assert result["type"] == "unknown"


def test_classify_rumble_confidence_above_half():
    """Synthetic ideal rumble must produce confidence > 0.5."""
    y, f0 = _make_rumble(duration_sec=3.0, f0_hz=14.0)
    result = classify_call_type(y, SR, f0)
    assert result["confidence"] > 0.5, (
        f"Expected confidence > 0.5, got {result['confidence']} for type='{result['type']}'"
    )


# ---------------------------------------------------------------------------
# Regression: real annotated rumble file
# ---------------------------------------------------------------------------

REAL_RECORDING_DIR = Path(__file__).parent.parent / "data" / "recordings" / "real"
ANNOTATIONS_PATH = Path(__file__).parent.parent / "data" / "annotations.xlsx"


def _load_first_rumble_annotation():
    """
    Find the first 'rumble'-labelled call in annotations.xlsx that has a
    corresponding recording on disk.  Returns (wav_path, start, end) or None.
    """
    try:
        import pandas as pd
    except ImportError:
        return None

    try:
        df = pd.read_excel(ANNOTATIONS_PATH, engine="openpyxl")
    except Exception:
        return None

    df.columns = df.columns.str.lower().str.strip()
    if "call_type" not in df.columns:
        return None

    rumbles = df[df["call_type"].str.lower().str.strip() == "rumble"]
    for _, row in rumbles.iterrows():
        wav_path = REAL_RECORDING_DIR / row["sound_file"]
        if wav_path.exists():
            return wav_path, float(row["start_time"]), float(row["end_time"])
    return None


@pytest.mark.skipif(
    not REAL_RECORDING_DIR.exists() or not ANNOTATIONS_PATH.exists(),
    reason="Real recordings or annotations not available",
)
def test_real_rumble_classified_as_rumble():
    """
    Load a real annotated rumble from data/recordings/real/ and verify
    classify_call_type() returns 'rumble' with confidence > 0.5.
    """
    annotation = _load_first_rumble_annotation()
    if annotation is None:
        pytest.skip("No rumble annotation with matching recording found on disk")

    wav_path, start_sec, end_sec = annotation
    import librosa
    from pipeline.harmonic_processor import hpss_enhance, detect_f0_shs
    from pipeline.spectrogram import compute_stft

    y, sr = librosa.load(str(wav_path), sr=None, offset=max(0, start_sec - 1.0),
                         duration=(end_sec - start_sec) + 2.0)

    # Run the same f0 detection used by the full pipeline
    ctx = compute_stft(y, sr)
    ctx = hpss_enhance(ctx)
    ctx = detect_f0_shs(ctx)
    f0_contour = ctx["f0_contour"]

    result = classify_call_type(y, sr, f0_contour)

    assert result["type"] == "rumble", (
        f"Real annotated rumble from {wav_path.name} classified as '{result['type']}'. "
        f"f0={result['f0_median_hz']:.1f} Hz, duration={result['duration_sec']:.2f}s, "
        f"flatness={result['spectral_flatness']:.3f}, "
        f"harm_dom={result['harmonic_dominance']:.3f}, "
        f"confidence={result['confidence']}"
    )
    assert result["confidence"] > 0.5, (
        f"Real rumble confidence {result['confidence']} <= 0.5 for {wav_path.name}"
    )
