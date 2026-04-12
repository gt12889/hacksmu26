"""
Phase 2: Harmonic detection and denoising chain.
Covers HARM-01 through HARM-06 and CLEAN-01 through CLEAN-03.

Processing order (must be maintained):
  1. hpss_enhance    — HPSS pre-separation (HARM-01, HARM-02)
  2. detect_f0_shs   — Subharmonic summation f0 detection (HARM-03, HARM-04)
  3. build_comb_mask — Time-varying harmonic comb mask (HARM-05)
  4. apply_comb_mask — Mask application + ISTFT reconstruction (HARM-06)
  5. apply_noisereduce — Adaptive spectral gating (CLEAN-01, CLEAN-02, CLEAN-03)

Anti-patterns avoided (see 02-RESEARCH.md for rationale):
  - HPSS magnitude NOT used for reconstruction (original magnitude used instead)
  - Hard binary mask NOT used (soft triangular window prevents musical noise)
  - SHS run on magnitude_harmonic (HPSS output), NOT raw magnitude
  - noisereduce applied AFTER comb mask, never before HPSS
"""
from __future__ import annotations

import warnings

import librosa
import noisereduce as nr
import numpy as np
from scipy.ndimage import median_filter

from pipeline.spectrogram import compute_stft, reconstruct_audio


def hpss_enhance(ctx: dict) -> dict:
    """
    HARM-01, HARM-02: HPSS with kernel calibrated for infrasonic harmonics.

    kernel_size is specified in spectrogram frames (not Hz).
    harmonic kernel = narrow frequency span (catches horizontal lines at 10-25 Hz spacing)
    percussive kernel = narrow time span (catches transient noise spikes)
    margin > 1.0 creates a residual bucket — content that is neither clearly harmonic
    nor clearly percussive lands in the residual and is discarded.

    Adds to ctx:
        magnitude_harmonic: HPSS harmonic component, same shape as magnitude
        hz_per_bin: Hz per frequency bin (sr / n_fft)
    """
    sr = ctx["sr"]
    n_fft = ctx["n_fft"]
    magnitude = ctx["magnitude"]  # shape: (n_freq_bins, n_frames)

    # Calculate bin width to set kernel in physical Hz terms
    hz_per_bin = sr / n_fft  # e.g. 5.38 Hz/bin at 44100/8192

    # Harmonic kernel: ~27 Hz span — narrow enough to resolve 10-25 Hz harmonic lines
    # without merging adjacent harmonics
    harmonic_kernel_bins = max(5, int(round(27 / hz_per_bin)))

    # Percussive kernel: 31 time frames is librosa default; fine for transients
    percussive_kernel_frames = 31

    # margin=(2.0, 2.0): both components must be 2x stronger than residual to be
    # assigned; reduces false assignment of noise to harmonic channel
    S_harmonic, _ = librosa.decompose.hpss(
        magnitude,
        kernel_size=(harmonic_kernel_bins, percussive_kernel_frames),
        margin=(2.0, 2.0),
    )

    ctx["magnitude_harmonic"] = S_harmonic
    ctx["hz_per_bin"] = hz_per_bin
    return ctx


def detect_f0_shs(ctx: dict) -> dict:
    """
    HARM-03, HARM-04: Subharmonic summation with octave-check heuristic.

    Sweeps f0 candidates in 8-25 Hz. For each candidate, sums power at
    k * f0 for k = 1..N where k*f0 <= 1000 Hz (NSSH: divide by N to normalize).
    Octave-check: if winner > 30 Hz and energy at winner/2 >= 0.7 * energy at winner,
    halve the estimate.

    Uses magnitude_harmonic (HPSS output) — NOT raw magnitude — to avoid engine
    harmonic bias contaminating the SHS vote.

    Adds to ctx:
        f0_contour: median-filtered f0 per frame, shape (n_frames,)
    """
    magnitude = ctx["magnitude_harmonic"]  # use HPSS-enhanced magnitude (NOT ctx["magnitude"])
    hz_per_bin = ctx["hz_per_bin"]

    F0_MIN_HZ = 8.0
    F0_MAX_HZ = 25.0
    MAX_HARMONIC_HZ = 1000.0

    n_freq_bins, n_frames = magnitude.shape

    # Candidate f0 values: step at half a bin for sub-bin resolution
    f0_candidates = np.arange(F0_MIN_HZ, F0_MAX_HZ, hz_per_bin / 2)

    # --- Vectorized SHS (NSSH) across all frames at once ---
    # shs_scores[i, t] = mean power at all harmonics of f0_candidates[i] in frame t
    shs_scores = np.zeros((len(f0_candidates), n_frames))

    for i, f0_cand in enumerate(f0_candidates):
        k_max = int(MAX_HARMONIC_HZ / f0_cand)
        harmonic_bins = np.round(
            np.arange(1, k_max + 1) * f0_cand / hz_per_bin
        ).astype(int)
        # Clamp to valid bin range
        harmonic_bins = harmonic_bins[harmonic_bins < n_freq_bins]
        if len(harmonic_bins) == 0:
            continue
        # magnitude[harmonic_bins, :] → shape (n_harmonics, n_frames)
        shs_scores[i, :] = magnitude[harmonic_bins, :].sum(axis=0) / len(harmonic_bins)

    # Best f0 index per frame
    best_candidate_idx = np.argmax(shs_scores, axis=0)
    f0_contour_raw = f0_candidates[best_candidate_idx].copy()

    # --- HARM-04: Octave-check per frame ---
    # For frames where detected f0 > 30 Hz, compare energy at f0/2 vs f0
    half_bins = np.round(f0_contour_raw / 2 / hz_per_bin).astype(int)
    best_bins = np.round(f0_contour_raw / hz_per_bin).astype(int)
    half_bins = np.clip(half_bins, 0, n_freq_bins - 1)
    best_bins = np.clip(best_bins, 0, n_freq_bins - 1)

    for t in range(n_frames):
        if f0_contour_raw[t] > 30.0:
            half_power = magnitude[half_bins[t], t]
            best_power = magnitude[best_bins[t], t]
            if half_power >= 0.7 * best_power:
                f0_contour_raw[t] = f0_contour_raw[t] / 2

    # Smooth f0 contour: 1D median filter over 9 frames to remove outliers
    # while preserving pitch glides
    f0_contour = median_filter(f0_contour_raw, size=9)

    ctx["f0_contour"] = f0_contour
    return ctx


def build_comb_mask(ctx: dict) -> dict:
    """
    HARM-05: Time-varying soft harmonic comb mask.

    For each time frame, sets mask value to 1.0 at each harmonic of the detected f0,
    tapering to 0.0 at ±bandwidth_bins. Background mask value is 0.0 (reject everything
    that is not a harmonic).

    Soft triangular mask avoids phase reconstruction artifacts (hard binary masks
    create abrupt edges that generate musical noise).

    Adds to ctx:
        comb_mask: float32 array, shape (n_freq_bins, n_frames), values in [0.0, 1.0]
    """
    magnitude = ctx["magnitude"]  # original (not HPSS) magnitude — shape reference
    f0_contour = ctx["f0_contour"]
    hz_per_bin = ctx["hz_per_bin"]

    n_freq_bins, n_frames = magnitude.shape
    BANDWIDTH_HZ = 5.0
    bandwidth_bins = max(1, int(round(BANDWIDTH_HZ / hz_per_bin)))
    MAX_HARMONIC_HZ = 1000.0

    # Initialize mask to zeros (reject by default)
    comb_mask = np.zeros((n_freq_bins, n_frames), dtype=np.float32)

    for t in range(n_frames):
        f0 = f0_contour[t]
        if f0 <= 0:
            continue

        k = 1
        while k * f0 <= MAX_HARMONIC_HZ:
            center_hz = k * f0
            center_bin = int(round(center_hz / hz_per_bin))

            # Triangular soft window over ±bandwidth_bins
            for delta in range(-bandwidth_bins, bandwidth_bins + 1):
                b = center_bin + delta
                if 0 <= b < n_freq_bins:
                    # Triangular taper: 1.0 at center, 0.0 at edges
                    weight = 1.0 - abs(delta) / (bandwidth_bins + 1)
                    # Use max to avoid overwriting a higher weight if teeth overlap
                    comb_mask[b, t] = max(comb_mask[b, t], weight)
            k += 1

    ctx["comb_mask"] = comb_mask
    return ctx


def apply_comb_mask(ctx: dict) -> dict:
    """
    HARM-06: Apply comb mask to original magnitude, reconstruct audio.

    Uses the original magnitude (NOT magnitude_harmonic) — comb mask must be
    applied to the original amplitude relationships, not the HPSS-attenuated version.
    Uses the original phase (not HPSS-filtered) to avoid phase artifacts.

    Adds to ctx:
        masked_magnitude: magnitude * comb_mask, shape (n_freq_bins, n_frames)
        audio_comb_masked: ISTFT reconstruction from masked_magnitude + original phase
    """
    # CRITICAL: use ctx["magnitude"] (original), NOT ctx["magnitude_harmonic"] (HPSS output)
    masked_magnitude = ctx["magnitude"] * ctx["comb_mask"]

    # Reconstruct using original phase (SPEC-02 pattern from Phase 1)
    ctx["audio_comb_masked"] = reconstruct_audio(masked_magnitude, ctx["phase"])
    ctx["masked_magnitude"] = masked_magnitude
    return ctx


def apply_noisereduce(ctx: dict, noise_clip: np.ndarray | None = None) -> dict:
    """
    CLEAN-01, CLEAN-02, CLEAN-03: Adaptive spectral gating based on noise type.

    Generator (stationary): use noise clip from extract_noise_gaps() as profile.
    Car / plane / mixed (non-stationary): no profile needed, stationary=False.

    If generator recording has no noise_clip available, falls back to non-stationary
    mode with a RuntimeWarning rather than raising an error (CLEAN-03 fallback).

    Args:
        ctx: Context dict; must contain audio_comb_masked, sr, noise_type
        noise_clip: numpy array of noise-only audio (from ingestor.extract_noise_gaps).
                    Required for best quality with generator noise_type. Pass None for
                    non-stationary mode or as fallback when no noise segment is available.

    Adds to ctx:
        audio_clean: spectrally-gated output audio
    """
    audio = ctx["audio_comb_masked"]
    sr = ctx["sr"]
    noise_type = ctx["noise_type"]["type"]  # from classify_noise_type()

    if noise_type == "generator":
        if noise_clip is None:
            warnings.warn(
                "[harmonic_processor] Generator recording but no noise_clip provided. "
                "Falling back to non-stationary mode. "
                "For best results, provide a noise clip from extract_noise_gaps().",
                RuntimeWarning,
                stacklevel=2,
            )
            audio_clean = nr.reduce_noise(y=audio, sr=sr, stationary=False)
        else:
            # CLEAN-02: stationary mode with noise profile
            audio_clean = nr.reduce_noise(
                y=audio,
                sr=sr,
                y_noise=noise_clip,
                stationary=True,
                prop_decrease=0.8,  # 80% reduction; tunable without re-running full pipeline
            )
    else:
        # CLEAN-01: non-stationary mode for car / plane / mixed
        audio_clean = nr.reduce_noise(y=audio, sr=sr, stationary=False)

    ctx["audio_clean"] = audio_clean
    return ctx


def process_call(
    y: np.ndarray,
    sr: int,
    noise_type: dict,
    noise_clip: np.ndarray | None = None,
) -> dict:
    """
    Runs full Phase 2 chain on a single call segment.

    Processing order: compute_stft → hpss_enhance → detect_f0_shs →
    build_comb_mask → apply_comb_mask → apply_noisereduce

    Args:
        y:          Audio array from load_call_segment()
        sr:         Native sample rate
        noise_type: Dict from classify_noise_type() — uses ["type"] field
        noise_clip: Audio array of noise-only segment (for generator stationary mode).
                    Pass None to use non-stationary fallback.

    Returns:
        Context dict with keys: audio_clean, masked_magnitude, f0_contour, comb_mask,
        and all intermediate Phase 1 outputs (magnitude, phase, freq_bins, etc.)
    """
    ctx = compute_stft(y, sr)
    ctx["noise_type"] = noise_type

    ctx = hpss_enhance(ctx)
    ctx = detect_f0_shs(ctx)
    ctx = build_comb_mask(ctx)
    ctx = apply_comb_mask(ctx)
    ctx = apply_noisereduce(ctx, noise_clip=noise_clip)
    return ctx
