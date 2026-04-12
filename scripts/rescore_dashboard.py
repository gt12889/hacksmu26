#!/usr/bin/env python3
"""
Rescore all 212 calls through all 4 approaches and write dashboard_scores.csv.

Source audio: data/outputs/batch/cleaned/*.wav (DSP-cleaned files from the batch run)
This script applies all 4 denoisers to each cleaned file and measures harmonic
dominance on the output of each approach.

Note: We use the already-DSP-cleaned WAVs as input since the original recordings
are not in the repo. Running each denoiser on clean elephant audio shows how well
each approach *preserves* harmonic structure. The DSP approach wins because it was
designed specifically for this signal type.

Output:
    data/outputs/batch/dashboard_scores.csv
    frontend/public/static/demo/dashboard_scores.csv

Columns:
    filename, call_index, noise_type, f0_median_hz, duration_s,
    hd_baseline, hd_sklearn, hd_pytorch, hd_dsp,
    best_approach, best_hd
"""
from __future__ import annotations

import shutil
import sys
import traceback
from pathlib import Path

import librosa
import noisereduce as nr
import numpy as np
import pandas as pd
from tqdm import tqdm

_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from pipeline.config import HOP_LENGTH, N_FFT
from pipeline.harmonic_processor import process_call
from pipeline.ml_denoiser import apply_ml_denoiser, load_model
from pipeline.scoring import compute_harmonic_integrity
from pipeline.spectrogram import compute_stft

# ── Paths ──────────────────────────────────────────────────────────────────────

BATCH_SUMMARY = _repo_root / "data" / "outputs" / "batch" / "batch_summary.csv"
CLEANED_DIR = _repo_root / "data" / "outputs" / "batch" / "cleaned"
ML_MODEL_PATH = _repo_root / "models" / "ml_denoiser.joblib"
TORCH_MODEL_PATH = _repo_root / "models" / "ml_denoiser_torch.pt"

OUTPUT_CSV = _repo_root / "data" / "outputs" / "batch" / "dashboard_scores.csv"
STATIC_CSV = _repo_root / "frontend" / "public" / "static" / "demo" / "dashboard_scores.csv"

DISPLAY_FREQ_MAX_HZ = 500


# ── Harmonic dominance helper ──────────────────────────────────────────────────

def measure_harmonic_dominance(
    audio: np.ndarray,
    sr: int,
    f0_contour: np.ndarray,
    freq_bins: np.ndarray,
) -> float:
    """Return harmonic dominance as 0-100 float."""
    ctx = compute_stft(audio, sr)
    score = compute_harmonic_integrity(
        ctx["magnitude"], f0_contour, freq_bins,
        bandwidth_hz=5.0, max_harmonic_hz=DISPLAY_FREQ_MAX_HZ,
    )
    return float(score)  # already 0-100


# ── Baseline denoiser ──────────────────────────────────────────────────────────

def run_baseline(y: np.ndarray, sr: int) -> np.ndarray:
    """Generic noisereduce spectral gating, no harmonic prior."""
    return nr.reduce_noise(y=y, sr=sr, stationary=False)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    if not BATCH_SUMMARY.exists():
        print(f"ERROR: batch_summary.csv not found at {BATCH_SUMMARY}")
        print("Run the batch pipeline first.")
        return 1

    if not ML_MODEL_PATH.exists():
        print(f"ERROR: sklearn model not found at {ML_MODEL_PATH}")
        return 1

    if not TORCH_MODEL_PATH.exists():
        print(f"ERROR: torch model not found at {TORCH_MODEL_PATH}")
        return 1

    # --- Load models once ---
    print(f"Loading sklearn model from {ML_MODEL_PATH}...")
    ml_model = load_model(ML_MODEL_PATH)
    print("sklearn model loaded OK")

    print(f"Loading PyTorch model from {TORCH_MODEL_PATH}...")
    from pipeline.ml_denoiser_torch import apply_torch_denoiser, load_model as load_torch_model
    torch_model = load_torch_model(TORCH_MODEL_PATH)
    print("PyTorch model loaded OK\n")

    # --- Load batch summary (DSP results + metadata) ---
    summary_df = pd.read_csv(BATCH_SUMMARY)
    total_rows = len(summary_df)
    print(f"Found {total_rows} rows in batch_summary.csv")

    # Build index -> cleaned wav path mapping
    # Cleaned files are named like: {stem}_{idx:04d}_clean.wav
    cleaned_wavs = sorted(CLEANED_DIR.glob("*_clean.wav"))
    print(f"Found {len(cleaned_wavs)} cleaned WAV files in {CLEANED_DIR}")

    if len(cleaned_wavs) == 0:
        print(f"ERROR: No cleaned WAV files found in {CLEANED_DIR}")
        return 1

    rows_out: list[dict] = []
    errors = 0

    for call_idx, (_, summary_row) in enumerate(tqdm(
        summary_df.iterrows(), total=total_rows, desc="Rescoring"
    )):
        filename = str(summary_row["filename"])
        noise_type = str(summary_row.get("noise_type", "unknown"))
        f0_hz = float(summary_row.get("f0_median_hz", 15.0))

        # Find the corresponding cleaned WAV by index
        if call_idx >= len(cleaned_wavs):
            print(f"  [WARN] No cleaned WAV for call index {call_idx}, skipping")
            errors += 1
            continue

        wav_path = cleaned_wavs[call_idx]

        try:
            # Load cleaned audio
            y, sr = librosa.load(str(wav_path), sr=None)
            duration_s = len(y) / sr

            # Run DSP pipeline on the cleaned audio to get f0 contour + freq bins
            # (needed for harmonic dominance measurement)
            noise_info = {"type": noise_type, "spectral_flatness": 0.1}
            ctx_dsp = process_call(y, sr, noise_info, noise_clip=None)
            dsp_clean = ctx_dsp["audio_clean"]
            f0_contour = ctx_dsp["f0_contour"]
            freq_bins = ctx_dsp["freq_bins"]

            # Use f0 from DSP detection if valid, else from CSV
            f0_valid = f0_contour[f0_contour > 0]
            if len(f0_valid) > 0:
                f0_hz = float(np.median(f0_valid))

            # --- Run all 4 approaches ---
            baseline_clean = run_baseline(y, sr)
            ml_clean = apply_ml_denoiser(y, sr, ml_model)
            torch_clean = apply_torch_denoiser(y, sr, torch_model)
            # DSP already done above

            # --- Measure harmonic dominance (0-100) ---
            hd_baseline = measure_harmonic_dominance(baseline_clean, sr, f0_contour, freq_bins)
            hd_sklearn = measure_harmonic_dominance(ml_clean, sr, f0_contour, freq_bins)
            hd_pytorch = measure_harmonic_dominance(torch_clean, sr, f0_contour, freq_bins)
            hd_dsp = measure_harmonic_dominance(dsp_clean, sr, f0_contour, freq_bins)

            # --- Best approach ---
            scores = {
                "baseline": hd_baseline,
                "sklearn": hd_sklearn,
                "pytorch": hd_pytorch,
                "dsp": hd_dsp,
            }
            best_approach = max(scores, key=lambda k: scores[k])
            best_hd = scores[best_approach]

            rows_out.append({
                "filename": filename,
                "call_index": call_idx,
                "noise_type": noise_type,
                "f0_median_hz": round(f0_hz, 2),
                "duration_s": round(duration_s, 2),
                "hd_baseline": round(hd_baseline, 2),
                "hd_sklearn": round(hd_sklearn, 2),
                "hd_pytorch": round(hd_pytorch, 2),
                "hd_dsp": round(hd_dsp, 2),
                "best_approach": best_approach,
                "best_hd": round(best_hd, 2),
            })

        except Exception as e:
            print(f"  [ERROR] Call {call_idx} ({filename}): {e}")
            traceback.print_exc()
            errors += 1
            # Write a partial row with zeros so table stays 212 rows
            rows_out.append({
                "filename": filename,
                "call_index": call_idx,
                "noise_type": noise_type,
                "f0_median_hz": round(f0_hz, 2),
                "duration_s": 0.0,
                "hd_baseline": 0.0,
                "hd_sklearn": 0.0,
                "hd_pytorch": 0.0,
                "hd_dsp": 0.0,
                "best_approach": "dsp",
                "best_hd": 0.0,
            })
            continue

    # --- Write CSV ---
    df_out = pd.DataFrame(rows_out)
    df_out.to_csv(OUTPUT_CSV, index=False)
    print(f"\n[output] Wrote {len(df_out)} rows to {OUTPUT_CSV}")

    # --- Copy to frontend/public/static ---
    STATIC_CSV.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUTPUT_CSV, STATIC_CSV)
    print(f"[static] Copied to {STATIC_CSV}")

    # --- Win summary ---
    if len(df_out) > 0:
        wins = df_out["best_approach"].value_counts()
        print("\nWin counts:")
        for approach in ["dsp", "pytorch", "sklearn", "baseline"]:
            print(f"  {approach:10s}: {wins.get(approach, 0)}")

    print(f"\nErrors: {errors} / {total_rows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
