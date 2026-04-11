"""
Tests for pipeline.config — DSP constants and resolution assertion.
TDD: These tests are written before the implementation.
"""

import pytest


def test_n_fft_equals_8192():
    from pipeline.config import N_FFT
    assert N_FFT == 8192


def test_hop_length_equals_512():
    from pipeline.config import HOP_LENGTH
    assert HOP_LENGTH == 512


def test_pad_seconds_equals_2():
    from pipeline.config import PAD_SECONDS
    assert PAD_SECONDS == 2.0


def test_verify_resolution_passes_44100():
    """44100 / 8192 = 5.38 Hz/bin — should pass silently."""
    from pipeline.config import verify_resolution
    verify_resolution(44100)  # should not raise


def test_verify_resolution_passes_48000():
    """48000 / 8192 = 5.86 Hz/bin — should pass silently."""
    from pipeline.config import verify_resolution
    verify_resolution(48000)  # should not raise


def test_verify_resolution_fails_96000():
    """96000 / 8192 = 11.72 Hz/bin — should raise AssertionError."""
    from pipeline.config import verify_resolution
    with pytest.raises(AssertionError) as exc_info:
        verify_resolution(96000)
    assert "sr=96000" in str(exc_info.value)


def test_verify_resolution_error_contains_resolution_value():
    """Error message should include the computed resolution value."""
    from pipeline.config import verify_resolution
    with pytest.raises(AssertionError) as exc_info:
        verify_resolution(96000)
    # 96000 / 8192 = 11.72 Hz/bin
    assert "11.72" in str(exc_info.value)
