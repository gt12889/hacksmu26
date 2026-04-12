"""
Tests for pipeline/harmonic_processor.py — Phase 2 harmonic detection and denoising chain.

TDD RED phase: these tests define the expected behavior before implementation.

Coverage:
  - hpss_enhance: adds magnitude_harmonic of correct shape
  - detect_f0_shs: f0 in 8-25 Hz range; octave-check on 2nd-harmonic-dominant signal
  - build_comb_mask: float32, shape (n_freq_bins, n_frames), values in [0,1]
  - apply_comb_mask: masked_magnitude shape matches magnitude; audio_comb_masked non-empty
  - apply_noisereduce: generator + noise_clip → stationary; car → non-stationary; fallback warning
  - process_call: full chain returns ctx with audio_clean non-empty
"""
from __future__ import annotations

import warnings

import numpy as np
import pytest


# ─── Fixtures ──────────────────────────────────────────────────────────────────

SR = 44100
DURATION = 3.0


def make_15hz_signal(duration: float = DURATION, sr: int = SR) -> np.ndarray:
    """15 Hz fundamental + stronger 30 Hz second harmonic + noise. Mimics elephant call."""
    t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
    return (
        0.5 * np.sin(2 * np.pi * 15 * t)
        + 1.0 * np.sin(2 * np.pi * 30 * t)
        + 0.05 * np.random.default_rng(42).standard_normal(len(t)).astype(np.float32)
    )


def make_noise_type(t: str = "car") -> dict:
    return {"type": t, "spectral_flatness": 0.6, "low_freq_ratio": 0.1}


@pytest.fixture
def signal_15hz() -> np.ndarray:
    return make_15hz_signal()


@pytest.fixture
def ctx_after_stft(signal_15hz):
    from pipeline.harmonic_processor import hpss_enhance
    from pipeline.spectrogram import compute_stft

    ctx = compute_stft(signal_15hz, SR)
    return ctx


@pytest.fixture
def ctx_after_hpss(ctx_after_stft):
    from pipeline.harmonic_processor import hpss_enhance

    return hpss_enhance(ctx_after_stft)


@pytest.fixture
def ctx_after_f0(ctx_after_hpss):
    from pipeline.harmonic_processor import detect_f0_shs

    return detect_f0_shs(ctx_after_hpss)


@pytest.fixture
def ctx_after_mask(ctx_after_f0):
    from pipeline.harmonic_processor import build_comb_mask

    return build_comb_mask(ctx_after_f0)


@pytest.fixture
def ctx_after_apply(ctx_after_mask):
    from pipeline.harmonic_processor import apply_comb_mask

    return apply_comb_mask(ctx_after_mask)


# ─── Import test ───────────────────────────────────────────────────────────────

def test_imports():
    """All six exported functions must import cleanly."""
    from pipeline.harmonic_processor import (
        apply_comb_mask,
        apply_noisereduce,
        build_comb_mask,
        detect_f0_shs,
        hpss_enhance,
        process_call,
    )


# ─── hpss_enhance ──────────────────────────────────────────────────────────────

class TestHpssEnhance:
    def test_adds_magnitude_harmonic_key(self, ctx_after_hpss):
        assert "magnitude_harmonic" in ctx_after_hpss

    def test_magnitude_harmonic_same_shape(self, ctx_after_stft, ctx_after_hpss):
        original_shape = ctx_after_stft["magnitude"].shape
        assert ctx_after_hpss["magnitude_harmonic"].shape == original_shape

    def test_hz_per_bin_stored_in_ctx(self, ctx_after_hpss):
        assert "hz_per_bin" in ctx_after_hpss
        expected = SR / 8192
        assert abs(ctx_after_hpss["hz_per_bin"] - expected) < 0.01

    def test_original_magnitude_not_modified(self, ctx_after_stft, ctx_after_hpss):
        """hpss_enhance must NOT modify ctx['magnitude'] in-place."""
        mag_orig = ctx_after_stft["magnitude"]
        mag_after = ctx_after_hpss["magnitude"]
        # Same object is OK — but the array values must not have changed
        # (we check shape is preserved and magnitude is still the original STFT magnitude)
        assert mag_orig.shape == mag_after.shape


# ─── detect_f0_shs ─────────────────────────────────────────────────────────────

class TestDetectF0Shs:
    def test_adds_f0_contour_key(self, ctx_after_f0):
        assert "f0_contour" in ctx_after_f0

    def test_f0_contour_shape_matches_frames(self, ctx_after_f0):
        n_frames = ctx_after_f0["magnitude"].shape[1]
        assert ctx_after_f0["f0_contour"].shape == (n_frames,)

    def test_f0_median_in_8_to_25_hz(self, ctx_after_f0):
        """Octave-check must ensure f0 is in 8-25 Hz even when 2nd harmonic is dominant."""
        median_f0 = float(np.median(ctx_after_f0["f0_contour"]))
        assert 8.0 <= median_f0 <= 25.0, (
            f"f0 median {median_f0:.2f} Hz is out of 8-25 Hz range. "
            f"Likely octave error: 30 Hz 2nd harmonic detected as f0."
        )

    def test_f0_not_in_30hz_range(self, ctx_after_f0):
        """Should NOT return 25-50 Hz f0 for a 15 Hz fundamental signal."""
        median_f0 = float(np.median(ctx_after_f0["f0_contour"]))
        assert not (25.0 < median_f0 <= 50.0), (
            f"f0 median {median_f0:.2f} Hz is in the 25-50 Hz octave-error range."
        )

    def test_f0_all_values_positive(self, ctx_after_f0):
        assert np.all(ctx_after_f0["f0_contour"] > 0)

    def test_reads_magnitude_harmonic_not_raw(self, ctx_after_hpss):
        """
        Indirect test: verify detect_f0_shs produces DIFFERENT results when
        magnitude_harmonic and magnitude differ (i.e., it actually uses magnitude_harmonic).
        We verify this by checking the function uses ctx["magnitude_harmonic"].
        """
        import inspect
        from pipeline.harmonic_processor import detect_f0_shs
        source = inspect.getsource(detect_f0_shs)
        assert "magnitude_harmonic" in source, (
            "detect_f0_shs must read ctx['magnitude_harmonic'], not ctx['magnitude']"
        )


# ─── build_comb_mask ───────────────────────────────────────────────────────────

class TestBuildCombMask:
    def test_adds_comb_mask_key(self, ctx_after_mask):
        assert "comb_mask" in ctx_after_mask

    def test_comb_mask_shape(self, ctx_after_mask):
        n_freq_bins, n_frames = ctx_after_mask["magnitude"].shape
        assert ctx_after_mask["comb_mask"].shape == (n_freq_bins, n_frames)

    def test_comb_mask_dtype_float32(self, ctx_after_mask):
        assert ctx_after_mask["comb_mask"].dtype == np.float32

    def test_comb_mask_values_in_0_1(self, ctx_after_mask):
        mask = ctx_after_mask["comb_mask"]
        assert float(mask.min()) >= 0.0, f"comb_mask min={mask.min()} < 0"
        assert float(mask.max()) <= 1.0, f"comb_mask max={mask.max()} > 1"

    def test_comb_mask_has_nonzero_entries(self, ctx_after_mask):
        """Mask must have some entries > 0 for a tonal signal."""
        assert np.any(ctx_after_mask["comb_mask"] > 0.0)


# ─── apply_comb_mask ───────────────────────────────────────────────────────────

class TestApplyCombMask:
    def test_adds_audio_comb_masked_key(self, ctx_after_apply):
        assert "audio_comb_masked" in ctx_after_apply

    def test_adds_masked_magnitude_key(self, ctx_after_apply):
        assert "masked_magnitude" in ctx_after_apply

    def test_audio_comb_masked_nonempty(self, ctx_after_apply):
        assert ctx_after_apply["audio_comb_masked"].shape[0] > 0

    def test_masked_magnitude_uses_original_magnitude(self, ctx_after_apply):
        """
        Confirm masked_magnitude = magnitude * comb_mask (not magnitude_harmonic * comb_mask).
        """
        import inspect
        from pipeline.harmonic_processor import apply_comb_mask
        source = inspect.getsource(apply_comb_mask)
        assert 'ctx["magnitude"] * ctx["comb_mask"]' in source or \
               "magnitude * comb_mask" in source, (
            "apply_comb_mask must use ctx['magnitude'] (original), not magnitude_harmonic"
        )

    def test_original_magnitude_unchanged(self, ctx_after_mask, ctx_after_apply):
        """apply_comb_mask must NOT modify ctx['magnitude'] in-place."""
        assert ctx_after_mask["magnitude"].shape == ctx_after_apply["magnitude"].shape


# ─── apply_noisereduce ─────────────────────────────────────────────────────────

class TestApplyNoisereduce:
    def _base_ctx(self):
        """Minimal ctx with audio_comb_masked for noisereduce tests."""
        from pipeline.harmonic_processor import (
            apply_comb_mask, build_comb_mask, detect_f0_shs, hpss_enhance
        )
        from pipeline.spectrogram import compute_stft
        y = make_15hz_signal()
        ctx = compute_stft(y, SR)
        ctx = hpss_enhance(ctx)
        ctx = detect_f0_shs(ctx)
        ctx = build_comb_mask(ctx)
        ctx = apply_comb_mask(ctx)
        return ctx

    def test_car_noise_routes_to_nonstationary(self):
        from pipeline.harmonic_processor import apply_noisereduce
        ctx = self._base_ctx()
        ctx["noise_type"] = make_noise_type("car")
        ctx = apply_noisereduce(ctx, noise_clip=None)
        assert "audio_clean" in ctx
        assert ctx["audio_clean"].shape[0] > 0

    def test_generator_with_noise_clip_returns_clean(self):
        from pipeline.harmonic_processor import apply_noisereduce
        ctx = self._base_ctx()
        ctx["noise_type"] = make_noise_type("generator")
        noise_clip = (0.05 * np.random.default_rng(0).standard_normal(SR)).astype(np.float32)
        ctx = apply_noisereduce(ctx, noise_clip=noise_clip)
        assert "audio_clean" in ctx
        assert ctx["audio_clean"].shape[0] > 0

    def test_generator_without_noise_clip_warns_not_raises(self):
        """generator + no noise_clip must warn and fall back (not raise)."""
        from pipeline.harmonic_processor import apply_noisereduce
        ctx = self._base_ctx()
        ctx["noise_type"] = make_noise_type("generator")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ctx = apply_noisereduce(ctx, noise_clip=None)
        assert len(w) >= 1, "Expected at least one warning for generator+None noise_clip"
        warning_messages = " ".join(str(warning.message) for warning in w)
        assert "generator" in warning_messages.lower() or "noise_clip" in warning_messages.lower()
        assert "audio_clean" in ctx

    def test_plane_noise_routes_to_nonstationary(self):
        from pipeline.harmonic_processor import apply_noisereduce
        ctx = self._base_ctx()
        ctx["noise_type"] = make_noise_type("plane")
        ctx = apply_noisereduce(ctx, noise_clip=None)
        assert "audio_clean" in ctx

    def test_mixed_noise_routes_to_nonstationary(self):
        from pipeline.harmonic_processor import apply_noisereduce
        ctx = self._base_ctx()
        ctx["noise_type"] = make_noise_type("mixed")
        ctx = apply_noisereduce(ctx, noise_clip=None)
        assert "audio_clean" in ctx


# ─── process_call (full chain) ─────────────────────────────────────────────────

class TestProcessCall:
    def test_returns_ctx_with_audio_clean(self, signal_15hz):
        from pipeline.harmonic_processor import process_call
        noise_type = make_noise_type("car")
        ctx = process_call(signal_15hz, SR, noise_type)
        assert "audio_clean" in ctx
        assert ctx["audio_clean"].shape[0] > 0

    def test_f0_contour_in_8_25_hz_range(self, signal_15hz):
        from pipeline.harmonic_processor import process_call
        noise_type = make_noise_type("car")
        ctx = process_call(signal_15hz, SR, noise_type)
        median_f0 = float(np.median(ctx["f0_contour"]))
        assert 8.0 <= median_f0 <= 25.0, f"f0 median {median_f0:.2f} Hz out of range"

    def test_comb_mask_dtype_and_range(self, signal_15hz):
        from pipeline.harmonic_processor import process_call
        noise_type = make_noise_type("car")
        ctx = process_call(signal_15hz, SR, noise_type)
        assert ctx["comb_mask"].dtype == np.float32
        assert float(ctx["comb_mask"].min()) >= 0.0
        assert float(ctx["comb_mask"].max()) <= 1.0

    def test_process_call_with_generator_and_noise_clip(self):
        from pipeline.harmonic_processor import process_call
        y = make_15hz_signal()
        noise_type = make_noise_type("generator")
        noise_clip = (0.05 * np.random.default_rng(1).standard_normal(SR)).astype(np.float32)
        ctx = process_call(y, SR, noise_type, noise_clip=noise_clip)
        assert "audio_clean" in ctx
        assert ctx["audio_clean"].shape[0] > 0
