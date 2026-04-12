"""
ML denoiser: sklearn MLPRegressor trained to approximate the harmonic comb mask.

Architecture:
  Input:  256 magnitude spectrogram bins (0-1500 Hz) per STFT frame
  Target: comb mask values (256 values) computed by build_comb_mask
  Model:  MLPRegressor(128, 64) — ~50k parameters

Training story:
  We fine-tune on 212 real elephant rumbles from the ElephantVoices dataset.
  The model learns a spectral gain function that approximates our comb mask.
  It performs BETTER than generic noisereduce but WORSE than our explicit
  harmonic-comb approach, because 212 examples is too few to generalize the
  harmonic-structure prior that our algorithm encodes directly.

Usage:
  from pipeline.ml_denoiser import build_training_pairs, train_ml_denoiser, apply_ml_denoiser
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

# Number of low-frequency bins to use as features/targets.
# At sr=48000, n_fft=8192: hz_per_bin = 5.86 Hz, so bin 256 ≈ 1500 Hz.
# At sr=44100, n_fft=8192: hz_per_bin = 5.38 Hz, so bin 256 ≈ 1377 Hz.
# Both cases cover all meaningful elephant harmonics (k*f0, f0 8-25 Hz, up to ~1000 Hz).
FREQ_BINS = 256


def build_training_pairs(
    annotations_path: str | Path,
    recordings_dir: str | Path,
    max_calls: int = 80,
    max_frames_per_call: int = 200,
    noise_types: list[str] | None = None,
    rng_seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build (X, Y) training arrays from annotated rumble recordings.

    For each call:
      1. Load the noisy audio segment.
      2. Compute STFT magnitude (n_fft=8192).
      3. Run hpss_enhance -> detect_f0_shs -> build_comb_mask on the segment.
      4. Sample up to max_frames_per_call frames from the middle of the call
         (skipping the padded silence at edges).

    X: magnitude frames, shape (n_samples, FREQ_BINS)
    Y: comb mask frames, shape (n_samples, FREQ_BINS)

    Args:
        annotations_path: Path to annotations.xlsx
        recordings_dir:   Directory containing recording WAV files
        max_calls:        Maximum calls to process (subsample evenly across noise types)
        max_frames_per_call: Maximum STFT frames to take from each call
        noise_types:      Noise type keywords to include (None = all)
        rng_seed:         Random seed for frame subsampling

    Returns:
        (X, Y) arrays suitable for sklearn fit()
    """
    import pandas as pd
    import librosa

    from pipeline.config import HOP_LENGTH, N_FFT
    from pipeline.harmonic_processor import hpss_enhance, detect_f0_shs, build_comb_mask
    from pipeline.spectrogram import compute_stft

    annotations_path = Path(annotations_path)
    recordings_dir = Path(recordings_dir)
    rng = np.random.default_rng(rng_seed)

    # Load annotations
    df = pd.read_excel(annotations_path, engine="openpyxl")

    # Filter to noise types if specified
    if noise_types:
        mask = pd.Series([False] * len(df))
        for nt in noise_types:
            mask |= df["Sound_file"].str.contains(nt, case=False, na=False)
        df = df[mask].copy()

    # Exclude background/mixed noise files
    df = df[~df["Sound_file"].str.contains("background", case=False, na=False)].copy()
    df = df.reset_index(drop=True)

    # Cap total calls — sample evenly
    if len(df) > max_calls:
        step = len(df) / max_calls
        indices = [int(i * step) for i in range(max_calls)]
        df = df.iloc[indices].copy()

    print(f"[ml_denoiser] Building training pairs from {len(df)} calls...")

    X_list: list[np.ndarray] = []
    Y_list: list[np.ndarray] = []
    skipped = 0

    for _, row in df.iterrows():
        filename = row["Sound_file"]
        start_sec = float(row["Start_time"])
        end_sec = float(row["End_time"])

        wav_path = recordings_dir / filename
        if not wav_path.exists():
            skipped += 1
            continue

        try:
            # Load with 1s padding (less than demo's 2s — faster, still provides context)
            pad = 1.0
            offset = max(0.0, start_sec - pad)
            duration = (end_sec + pad) - offset

            y, sr = librosa.load(str(wav_path), sr=None, offset=offset, duration=duration)

            # STFT
            ctx = compute_stft(y, sr)
            n_total_bins = ctx["magnitude"].shape[0]

            # Clamp FREQ_BINS to available bins
            n_bins = min(FREQ_BINS, n_total_bins)

            # Build comb mask
            ctx = hpss_enhance(ctx)
            ctx = detect_f0_shs(ctx)
            ctx = build_comb_mask(ctx)

            magnitude = ctx["magnitude"]  # (n_freq_bins, n_frames)
            comb_mask = ctx["comb_mask"]  # (n_freq_bins, n_frames)
            n_frames = magnitude.shape[1]

            if n_frames < 10:
                skipped += 1
                continue

            # Skip edge frames (first/last 10 frames = padded silence region)
            edge = min(10, n_frames // 4)
            frame_indices = np.arange(edge, n_frames - edge)

            # Subsample if too many frames
            if len(frame_indices) > max_frames_per_call:
                chosen = rng.choice(frame_indices, size=max_frames_per_call, replace=False)
            else:
                chosen = frame_indices

            # Extract feature/target vectors — only first n_bins frequency bins
            X_call = magnitude[:n_bins, chosen].T.astype(np.float32)  # (chosen, n_bins)
            Y_call = comb_mask[:n_bins, chosen].T.astype(np.float32)   # (chosen, n_bins)

            # Pad to FREQ_BINS if sr causes fewer bins
            if n_bins < FREQ_BINS:
                pad_x = np.zeros((X_call.shape[0], FREQ_BINS - n_bins), dtype=np.float32)
                pad_y = np.zeros((Y_call.shape[0], FREQ_BINS - n_bins), dtype=np.float32)
                X_call = np.concatenate([X_call, pad_x], axis=1)
                Y_call = np.concatenate([Y_call, pad_y], axis=1)

            X_list.append(X_call)
            Y_list.append(Y_call)

        except Exception as e:
            warnings.warn(f"[ml_denoiser] Skipped {filename}: {e}", RuntimeWarning)
            skipped += 1
            continue

    if skipped > 0:
        print(f"[ml_denoiser] Skipped {skipped} calls (file not found or processing error)")

    if not X_list:
        raise ValueError("No training pairs built — check recordings_dir and annotations_path.")

    X = np.vstack(X_list)
    Y = np.vstack(Y_list)
    print(f"[ml_denoiser] Training pairs: X={X.shape}, Y={Y.shape}")
    return X, Y


def train_ml_denoiser(
    X: np.ndarray,
    Y: np.ndarray,
    max_iter: int = 100,
    hidden_layer_sizes: tuple[int, ...] = (128, 64),
) -> object:
    """
    Train an MLPRegressor to predict harmonic comb mask values from spectrogram frames.

    The model approximates the gain function computed by build_comb_mask.
    It is NOT a signal-level predictor — it predicts per-bin gains in [0, 1].

    Args:
        X:                Training features (n_samples, FREQ_BINS) — magnitude frames
        Y:                Training targets  (n_samples, FREQ_BINS) — comb mask values
        max_iter:         Training iterations (early stopping often halts before this)
        hidden_layer_sizes: MLP hidden layer architecture

    Returns:
        Fitted MLPRegressor
    """
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    # Normalize magnitude features — important for MLP convergence
    # Mask targets are already in [0, 1], no need to scale
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPRegressor(
            hidden_layer_sizes=hidden_layer_sizes,
            activation="relu",
            solver="adam",
            max_iter=max_iter,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=10,
            verbose=True,
            random_state=42,
        )),
    ])

    model.fit(X, Y)
    return model


def apply_ml_denoiser(
    y: np.ndarray,
    sr: int,
    model: object,
) -> np.ndarray:
    """
    Apply the trained ML denoiser to a raw audio array.

    Inference pipeline:
      1. Compute STFT (magnitude + phase)
      2. For each frame: predict gain vector from magnitude[:FREQ_BINS]
      3. Apply predicted gains to full magnitude (clip to [0, 1])
      4. ISTFT with original phase → reconstructed audio

    Args:
        y:     Raw (noisy) audio array, same sr as training data
        sr:    Sample rate
        model: Fitted model from train_ml_denoiser()

    Returns:
        Cleaned audio array (same length as y)
    """
    from pipeline.spectrogram import compute_stft, reconstruct_audio

    ctx = compute_stft(y, sr)
    magnitude = ctx["magnitude"]   # (n_freq_bins, n_frames)
    phase = ctx["phase"]            # (n_freq_bins, n_frames)
    n_freq_bins, n_frames = magnitude.shape

    # Crop to FREQ_BINS for model input
    n_bins = min(FREQ_BINS, n_freq_bins)

    # Build feature matrix: (n_frames, FREQ_BINS)
    X_infer = magnitude[:n_bins, :].T.astype(np.float32)  # (n_frames, n_bins)

    # Pad if needed
    if n_bins < FREQ_BINS:
        pad = np.zeros((n_frames, FREQ_BINS - n_bins), dtype=np.float32)
        X_infer = np.concatenate([X_infer, pad], axis=1)

    # Predict gains: (n_frames, FREQ_BINS)
    gains = model.predict(X_infer).astype(np.float32)

    # Clip to valid gain range [0, 1]
    gains = np.clip(gains, 0.0, 1.0)

    # Apply gains to full magnitude spectrogram
    # For bins above FREQ_BINS, apply a mild default gain (0.1 — suppress high-freq noise)
    ml_magnitude = np.zeros_like(magnitude)
    ml_magnitude[:n_bins, :] = magnitude[:n_bins, :] * gains[:, :n_bins].T

    # High-frequency bins not covered by model: suppress to 10% (safe default)
    if n_freq_bins > n_bins:
        ml_magnitude[n_bins:, :] = magnitude[n_bins:, :] * 0.1

    # Reconstruct audio with original phase
    audio_out = reconstruct_audio(ml_magnitude, phase)
    return audio_out


def save_model(model: object, path: str | Path) -> None:
    """Save fitted model to disk using joblib compression."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, str(path), compress=3)
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"[ml_denoiser] Model saved to {path} ({size_mb:.2f} MB)")


def load_model(path: str | Path) -> object:
    """Load a saved model from disk."""
    return joblib.load(str(path))
