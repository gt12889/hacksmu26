"""
STFT computation with phase preservation for artifact-free reconstruction.
Covers SPEC-01 (infrasonic resolution) and SPEC-02 (phase preservation).
"""

from __future__ import annotations

import librosa
import numpy as np

from pipeline.config import HOP_LENGTH, N_FFT, verify_resolution


def compute_stft(y: np.ndarray, sr: int) -> dict:
    """
    Compute STFT with infrasonic frequency resolution. (SPEC-01, SPEC-02)

    Uses n_fft=N_FFT (8192) for ~5.4 Hz/bin at 44100 Hz — sufficient to resolve
    elephant fundamentals at 8-25 Hz.

    Phase is separated and returned alongside magnitude so that Phase 2 can apply
    a comb mask to magnitude and reconstruct via ISTFT using the original phase
    (artifact-free, no phase estimation needed).

    Args:
        y: Audio array (float32 or float64)
        sr: Native sample rate from librosa.load(sr=None)

    Returns:
        dict with keys:
          S          - complex spectrogram (n_fft/2+1, time_frames)
          magnitude  - |S|, shape (n_fft/2+1, time_frames)
          phase      - angle(S) in radians, shape (n_fft/2+1, time_frames)
          freq_bins  - frequency value per bin in Hz, shape (n_fft/2+1,)
          sr         - sample rate (passed through)
          n_fft      - FFT size used
          hop_length - hop length used
    """
    # INGEST-05: verify resolution before computing (catches wrong sr at runtime)
    verify_resolution(sr)

    # SPEC-01: n_fft=N_FFT for infrasonic resolution
    S = librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH)

    # SPEC-02: separate magnitude and phase for artifact-free reconstruction
    magnitude = np.abs(S)
    phase = np.angle(S)

    freq_bins = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)

    return {
        "S": S,
        "magnitude": magnitude,
        "phase": phase,
        "freq_bins": freq_bins,
        "sr": sr,
        "n_fft": N_FFT,
        "hop_length": HOP_LENGTH,
    }


def reconstruct_audio(magnitude: np.ndarray, phase: np.ndarray) -> np.ndarray:
    """
    Reconstruct audio from a (possibly masked) magnitude using the original phase.

    Phase 2 applies the harmonic comb mask to magnitude, then calls this function
    to reconstruct. Using the original phase (rather than estimating it) eliminates
    phase artifacts in the reconstructed audio.

    Args:
        magnitude: Magnitude spectrogram, shape (n_fft/2+1, time_frames)
        phase: Original phase from compute_stft(), same shape as magnitude

    Returns:
        Reconstructed audio array (float32)
    """
    # Recombine masked magnitude with original phase
    S_reconstructed = magnitude * np.exp(1j * phase)
    return librosa.istft(S_reconstructed, hop_length=HOP_LENGTH)
