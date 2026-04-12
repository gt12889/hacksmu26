"""
Single source of truth for all DSP constants.
Every pipeline module imports from here — no magic numbers elsewhere.
"""

N_FFT: int = 8192
HOP_LENGTH: int = 512
PAD_SECONDS: float = 2.0
MAX_FREQ_RESOLUTION_HZ: float = 6.0
MIN_NOISE_DURATION_SEC: float = 1.0
FLATNESS_TONAL_THRESHOLD: float = 0.1
FLATNESS_BROADBAND_THRESHOLD: float = 0.4


# Phase 6: Multi-speaker separation thresholds
F0_JUMP_TOLERANCE_HZ: float = 5.0   # max Hz jump between frames in greedy linker
MIN_TRACK_FRAMES: int = 10           # frames required to treat a track as real
MIN_SCORE_RATIO: float = 0.4         # score[1]/score[0] threshold for 2-caller detection


def verify_resolution(sr: int, n_fft: int = N_FFT) -> None:
    """
    Assert INGEST-05: frequency resolution must be < MAX_FREQ_RESOLUTION_HZ.

    Args:
        sr: Sample rate of the loaded audio file
        n_fft: FFT size (defaults to module constant N_FFT)

    Raises:
        AssertionError: If sr / n_fft >= MAX_FREQ_RESOLUTION_HZ
    """
    resolution = sr / n_fft
    assert resolution < MAX_FREQ_RESOLUTION_HZ, (
        f"Frequency resolution {resolution:.2f} Hz/bin exceeds {MAX_FREQ_RESOLUTION_HZ} Hz limit. "
        f"Increase n_fft or reduce sample rate. "
        f"Current: sr={sr}, n_fft={n_fft}. "
        f"For sr=96000 use n_fft=16384 (5.86 Hz/bin)."
    )
    print(f"[config] Resolution OK: {resolution:.2f} Hz/bin (sr={sr}, n_fft={n_fft})")
