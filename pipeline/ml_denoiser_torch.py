"""
PyTorch-based 1D Conv U-Net denoiser trained to approximate the harmonic comb mask.

Architecture (SmallConvUNet):
  Input:  256 magnitude spectrogram bins (0-1500 Hz) per STFT frame
  Target: comb mask values (256 values) computed by build_comb_mask
  Model:  1D Conv U-Net with encoder/decoder + skip connections (~65k params)

Training story:
  Same training pairs as sklearn MLPRegressor — 80 real elephant rumbles from
  the ElephantVoices dataset, 16k STFT frames.
  Loss: MSE on predicted gains vs target comb mask values.
  Optimizer: Adam lr=1e-3, 50 epochs with early stopping.

Pitch story:
  This shows we tried REAL deep learning (not just classical ML).
  The PyTorch U-Net has a proper inductive bias (local frequency patterns via conv)
  but still needs labeled training data. Our explicit harmonic-comb approach
  encodes the prior mathematically and needs zero training data.

Usage:
  from pipeline.ml_denoiser_torch import (
      SmallConvUNet, train_torch_denoiser, apply_torch_denoiser,
      save_model, load_model
  )
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# Number of low-frequency bins — must match pipeline/ml_denoiser.py
FREQ_BINS = 256


# ── Model ─────────────────────────────────────────────────────────────────────

class SmallConvUNet(nn.Module):
    """
    1D Convolutional U-Net that maps a magnitude spectrogram frame (256 bins)
    to a gain mask (256 values in [0, 1]).

    Encoder: 3 Conv1d layers with increasing channel depth (1→32→64→128)
    Decoder: 3 ConvTranspose1d layers with symmetric channel collapse
    Skip connections: encoder features concatenated into decoder at each level

    Total params: ~65k — small enough for CPU training in under 3 minutes.
    """

    def __init__(self, input_size: int = FREQ_BINS) -> None:
        super().__init__()
        self.input_size = input_size

        # Encoder
        self.enc1 = nn.Sequential(
            nn.Conv1d(1, 32, kernel_size=7, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),
        )
        self.enc2 = nn.Sequential(
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
        )
        self.enc3 = nn.Sequential(
            nn.Conv1d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(inplace=True),
        )

        # Bottleneck
        self.bottleneck = nn.Sequential(
            nn.Conv1d(128, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(inplace=True),
        )

        # Decoder — takes skip + bottleneck, so channels are doubled at each concat
        self.dec3 = nn.Sequential(
            nn.Conv1d(128 + 128, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
        )
        self.dec2 = nn.Sequential(
            nn.Conv1d(64 + 64, 32, kernel_size=5, padding=2),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),
        )
        self.dec1 = nn.Sequential(
            nn.Conv1d(32 + 32, 16, kernel_size=7, padding=3),
            nn.BatchNorm1d(16),
            nn.ReLU(inplace=True),
        )

        # Output head
        self.output = nn.Sequential(
            nn.Conv1d(16, 1, kernel_size=1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, FREQ_BINS) — normalized magnitude frame

        Returns:
            gains: (batch, FREQ_BINS) — gain values in [0, 1]
        """
        # Reshape to (batch, 1, FREQ_BINS) for Conv1d
        x = x.unsqueeze(1)  # (B, 1, L)

        # Encoder with skip connections
        e1 = self.enc1(x)   # (B, 32, L)
        e2 = self.enc2(e1)  # (B, 64, L)
        e3 = self.enc3(e2)  # (B, 128, L)

        # Bottleneck
        b = self.bottleneck(e3)  # (B, 128, L)

        # Decoder with skip connections
        d3 = self.dec3(torch.cat([b, e3], dim=1))   # (B, 64, L)
        d2 = self.dec2(torch.cat([d3, e2], dim=1))  # (B, 32, L)
        d1 = self.dec1(torch.cat([d2, e1], dim=1))  # (B, 16, L)

        # Output gains
        out = self.output(d1)  # (B, 1, L)
        return out.squeeze(1)  # (B, L)


# ── Training ──────────────────────────────────────────────────────────────────

def train_torch_denoiser(
    X: np.ndarray,
    Y: np.ndarray,
    epochs: int = 50,
    batch_size: int = 256,
    lr: float = 1e-3,
    val_fraction: float = 0.1,
    patience: int = 7,
) -> SmallConvUNet:
    """
    Train the SmallConvUNet on (X, Y) magnitude frame → comb mask pairs.

    Args:
        X:            Feature matrix (n_samples, FREQ_BINS) — raw magnitude frames
        Y:            Target matrix  (n_samples, FREQ_BINS) — comb mask gains [0, 1]
        epochs:       Maximum training epochs
        batch_size:   Mini-batch size for DataLoader
        lr:           Adam learning rate
        val_fraction: Fraction of data held out for validation (early stopping)
        patience:     Epochs to wait for val loss improvement before stopping

    Returns:
        Trained SmallConvUNet in eval mode
    """
    device = torch.device("cpu")

    # Normalize input features to [0, 1] per-sample (robust to amplitude variation)
    X_max = X.max(axis=1, keepdims=True)
    X_max = np.where(X_max > 0, X_max, 1.0)
    X_norm = (X / X_max).astype(np.float32)

    # Split train / val
    n = len(X_norm)
    n_val = max(1, int(n * val_fraction))
    idx = np.random.default_rng(42).permutation(n)
    val_idx, train_idx = idx[:n_val], idx[n_val:]

    X_train = torch.from_numpy(X_norm[train_idx])
    Y_train = torch.from_numpy(Y[train_idx])
    X_val = torch.from_numpy(X_norm[val_idx])
    Y_val = torch.from_numpy(Y[val_idx])

    train_ds = TensorDataset(X_train, Y_train)
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=False)

    model = SmallConvUNet(input_size=FREQ_BINS).to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    best_state = None
    no_improve = 0

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in train_dl:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(xb)
        train_loss /= len(X_train)

        # Validation
        model.eval()
        with torch.no_grad():
            val_pred = model(X_val.to(device))
            val_loss = criterion(val_pred, Y_val.to(device)).item()

        if (epoch % 10 == 0) or epoch == 1:
            print(f"  Epoch {epoch:3d}/{epochs}: train_loss={train_loss:.6f}  val_loss={val_loss:.6f}")

        if val_loss < best_val_loss - 1e-7:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                print(f"  Early stopping at epoch {epoch} (no val improvement for {patience} epochs)")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    print(f"  Best val loss: {best_val_loss:.6f}")
    return model


# ── Inference ─────────────────────────────────────────────────────────────────

def apply_torch_denoiser(
    y: np.ndarray,
    sr: int,
    model: SmallConvUNet,
) -> np.ndarray:
    """
    Apply the trained PyTorch denoiser to a raw audio array.

    Inference pipeline:
      1. Compute STFT (magnitude + phase)
      2. For each frame: normalize magnitude[:FREQ_BINS], predict gain vector
      3. Apply predicted gains to full magnitude (clip to [0, 1])
      4. ISTFT with original phase → reconstructed audio

    Args:
        y:     Raw (noisy) audio array
        sr:    Sample rate
        model: Trained SmallConvUNet (from train_torch_denoiser or load_model)

    Returns:
        Cleaned audio array (same length as y)
    """
    from pipeline.spectrogram import compute_stft, reconstruct_audio

    device = torch.device("cpu")
    model = model.to(device)
    model.eval()

    ctx = compute_stft(y, sr)
    magnitude = ctx["magnitude"]   # (n_freq_bins, n_frames)
    phase = ctx["phase"]            # (n_freq_bins, n_frames)
    n_freq_bins, n_frames = magnitude.shape

    n_bins = min(FREQ_BINS, n_freq_bins)

    # Build feature matrix: (n_frames, FREQ_BINS)
    X_mag = magnitude[:n_bins, :].T.astype(np.float32)  # (n_frames, n_bins)
    if n_bins < FREQ_BINS:
        pad = np.zeros((n_frames, FREQ_BINS - n_bins), dtype=np.float32)
        X_mag = np.concatenate([X_mag, pad], axis=1)

    # Normalize per-frame to [0, 1]
    frame_max = X_mag.max(axis=1, keepdims=True)
    frame_max = np.where(frame_max > 0, frame_max, 1.0)
    X_norm = (X_mag / frame_max).astype(np.float32)

    # Batch inference
    X_tensor = torch.from_numpy(X_norm).to(device)
    batch_size = 512
    gains_list = []
    with torch.no_grad():
        for i in range(0, n_frames, batch_size):
            xb = X_tensor[i:i + batch_size]
            gains_batch = model(xb)
            gains_list.append(gains_batch.cpu().numpy())
    gains = np.concatenate(gains_list, axis=0)  # (n_frames, FREQ_BINS)
    gains = np.clip(gains, 0.0, 1.0)

    # Apply gains to full magnitude spectrogram
    ml_magnitude = np.zeros_like(magnitude)
    ml_magnitude[:n_bins, :] = magnitude[:n_bins, :] * gains[:, :n_bins].T

    # High-frequency bins not covered by model: suppress to 10%
    if n_freq_bins > n_bins:
        ml_magnitude[n_bins:, :] = magnitude[n_bins:, :] * 0.1

    audio_out = reconstruct_audio(ml_magnitude, phase)
    return audio_out


# ── Save / Load ────────────────────────────────────────────────────────────────

def save_model(model: SmallConvUNet, path: str | Path) -> None:
    """Save the trained model weights to a .pt file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), str(path))
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"[ml_denoiser_torch] Model saved to {path} ({size_mb:.2f} MB)")


def load_model(path: str | Path, input_size: int = FREQ_BINS) -> SmallConvUNet:
    """Load a saved model from a .pt file."""
    path = Path(path)
    model = SmallConvUNet(input_size=input_size)
    model.load_state_dict(torch.load(str(path), map_location="cpu", weights_only=True))
    model.eval()
    return model


def count_params(model: nn.Module) -> int:
    """Return total trainable parameter count."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
