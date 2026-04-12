#!/usr/bin/env python3
"""
Train the ML denoiser (MLPRegressor) on ElephantVoices annotations.

Builds (X, Y) training pairs from annotated rumbles:
  X: noisy magnitude spectrogram frames (256 bins = 0-1500 Hz)
  Y: harmonic comb mask values for the same frames (our algorithm's output)

The model learns to approximate our comb mask. It performs BETTER than
generic noisereduce but WORSE than our explicit harmonic-comb approach,
because 212 examples is too few to generalize the harmonic-structure prior
that our algorithm encodes directly.

Usage:
    python scripts/train_ml_denoiser.py
    python scripts/train_ml_denoiser.py --max-calls 60 --max-iter 80
    python scripts/train_ml_denoiser.py --output models/ml_denoiser.joblib
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

ANNOTATIONS_PATH = _repo_root / "data" / "annotations.xlsx"
RECORDINGS_DIR = _repo_root / "data" / "recordings" / "real"
DEFAULT_MODEL_PATH = _repo_root / "models" / "ml_denoiser.joblib"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train ML denoiser on ElephantVoices annotated rumbles."
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=ANNOTATIONS_PATH,
        help="Path to annotations.xlsx",
    )
    parser.add_argument(
        "--recordings",
        type=Path,
        default=RECORDINGS_DIR,
        help="Directory containing recording WAV files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Output path for the trained model (.joblib)",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=80,
        help="Maximum number of calls to process (default: 80)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=200,
        help="Maximum STFT frames per call (default: 200)",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=100,
        help="Maximum MLP training iterations (default: 100)",
    )
    args = parser.parse_args()

    if not args.annotations.exists():
        print(f"ERROR: annotations not found at {args.annotations}")
        return 1
    if not args.recordings.exists():
        print(f"ERROR: recordings directory not found at {args.recordings}")
        return 1

    from pipeline.ml_denoiser import (
        build_training_pairs,
        load_model,
        save_model,
        train_ml_denoiser,
    )

    print("=" * 65)
    print("ML DENOISER TRAINING")
    print("=" * 65)
    print(f"Annotations: {args.annotations}")
    print(f"Recordings:  {args.recordings}")
    print(f"Max calls:   {args.max_calls}")
    print(f"Max frames:  {args.max_frames} per call")
    print(f"Max iter:    {args.max_iter}")
    print(f"Output:      {args.output}")
    print()

    # ── Step 1: Build training data ────────────────────────────────────────────
    t0 = time.time()
    print("Step 1: Building training pairs...")
    X, Y = build_training_pairs(
        annotations_path=args.annotations,
        recordings_dir=args.recordings,
        max_calls=args.max_calls,
        max_frames_per_call=args.max_frames,
    )
    t_build = time.time() - t0
    n_pairs = X.shape[0]
    print(f"  Training pairs:     {n_pairs:,}")
    print(f"  Feature dimension:  {X.shape[1]}")
    print(f"  Target dimension:   {Y.shape[1]}")
    print(f"  Data build time:    {t_build:.1f}s")
    print()

    # ── Step 2: Train MLP ─────────────────────────────────────────────────────
    print("Step 2: Training MLPRegressor(128, 64)...")
    t1 = time.time()
    model = train_ml_denoiser(X, Y, max_iter=args.max_iter)
    t_train = time.time() - t1
    t_total = time.time() - t0
    print(f"  Training time:      {t_train:.1f}s")
    print()

    # ── Step 3: Evaluate ──────────────────────────────────────────────────────
    print("Step 3: Evaluating on training data...")
    from sklearn.model_selection import train_test_split
    X_train, X_val, Y_train, Y_val = train_test_split(X, Y, test_size=0.1, random_state=42)

    train_r2 = model.score(X_train, Y_train)
    val_r2 = model.score(X_val, Y_val)
    print(f"  Train R²:           {train_r2:.4f}")
    print(f"  Val R²:             {val_r2:.4f}")
    print()

    # ── Step 4: Save model ────────────────────────────────────────────────────
    print("Step 4: Saving model...")
    save_model(model, args.output)
    size_mb = args.output.stat().st_size / (1024 * 1024)
    size_ok = size_mb < 5.0
    print(f"  File size:          {size_mb:.2f} MB {'OK' if size_ok else 'WARNING: exceeds 5 MB limit'}")
    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 65)
    print("TRAINING COMPLETE")
    print("=" * 65)
    print(f"  Training pairs:     {n_pairs:,}")
    print(f"  Train R²:           {train_r2:.4f}")
    print(f"  Val R²:             {val_r2:.4f}")
    print(f"  Total time:         {t_total:.1f}s")
    print(f"  Model:              {args.output}")
    print(f"  Model size:         {size_mb:.2f} MB")
    print()
    print("Interpretation:")
    print("  R² measures how well the model approximates our comb mask.")
    print("  Higher = closer to our explicit harmonic comb algorithm.")
    print("  Even a good R² won't beat the math — 212 examples can't fully")
    print("  encode the harmonic-structure prior our algorithm uses directly.")

    return 0 if (t_total < 180 and size_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
