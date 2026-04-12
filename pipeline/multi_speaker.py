"""
Phase 6: Multi-speaker separation.
Covers MULTI-01 (detect multiple f0 tracks), MULTI-02 (crossing harmonic identification),
MULTI-03 (per-caller WAV output).

Functions:
  detect_f0_shs_topk  — returns top-k f0 candidates per STFT frame
  link_f0_tracks      — greedy nearest-neighbour track linker + median smooth
  separate_speakers   — per-caller comb mask + WAV output
  is_multi_speaker    — score ratio gate: True when two callers are present
  is_harmonic_overlap — True when one f0 is an integer multiple of the other

Anti-patterns avoided (see 06-RESEARCH.md):
  - HPSS is NOT run inside this module — ctx already has magnitude_harmonic from caller
  - ctx["magnitude_harmonic"] is NOT used for reconstruction — build_comb_mask uses ctx["magnitude"]
  - Tracks are median-filtered INDEPENDENTLY — not jointly
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.ndimage import median_filter

from pipeline.config import F0_JUMP_TOLERANCE_HZ, MIN_SCORE_RATIO, MIN_TRACK_FRAMES
from pipeline.harmonic_processor import apply_comb_mask, build_comb_mask


def detect_f0_shs_topk(ctx: dict, k: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """
    MULTI-01: Top-k subharmonic summation — returns k candidate f0 values per frame.

    Replicates the shs_scores matrix from detect_f0_shs (same search range, same
    harmonic summation formula) then extracts the top-k candidates using
    np.argpartition for O(n_candidates) per-frame extraction.

    Uses ctx["magnitude_harmonic"] (HPSS output) for SHS voting, consistent with
    the single-f0 detect_f0_shs function.

    Args:
        ctx: Context dict; must contain magnitude_harmonic, hz_per_bin.
        k:   Number of top candidates to return per frame (default 2).

    Returns:
        top_k_f0s:    (k, n_frames) float array — f0 candidates in Hz, row 0 = best
        top_k_scores: (k, n_frames) float array — corresponding SHS scores, row 0 = best
    """
    magnitude = ctx["magnitude_harmonic"]  # HPSS-enhanced magnitude (NOT raw)
    hz_per_bin = ctx["hz_per_bin"]

    F0_MIN_HZ = 8.0
    F0_MAX_HZ = 25.0
    MAX_HARMONIC_HZ = 1000.0

    n_freq_bins, n_frames = magnitude.shape

    # Candidate f0 values: 0.5 Hz fixed step for consistent resolution independent of sr.
    # Half-bin step (hz_per_bin/2 ≈ 2.69 Hz at 44100/8192) is too coarse to resolve
    # two callers separated by only 4 Hz; 0.5 Hz gives sufficient sub-bin precision.
    f0_candidates = np.arange(F0_MIN_HZ, F0_MAX_HZ, 0.5)
    n_candidates = len(f0_candidates)

    # Build SHS score matrix: shs_scores[i, t] = NSSH score for f0_candidates[i] at frame t
    # Use raw magnitude for peak detection (HPSS can suppress one of two simultaneous
    # harmonic sources; raw magnitude preserves both sources' energy)
    shs_magnitude = ctx["magnitude"]
    shs_scores = np.zeros((n_candidates, n_frames))

    for i, f0_cand in enumerate(f0_candidates):
        k_max = int(MAX_HARMONIC_HZ / f0_cand)
        harmonic_bins = np.round(
            np.arange(1, k_max + 1) * f0_cand / hz_per_bin
        ).astype(int)
        # Clamp to valid bin range
        harmonic_bins = harmonic_bins[harmonic_bins < n_freq_bins]
        if len(harmonic_bins) == 0:
            continue
        # NSSH: mean power at all harmonics — use raw magnitude (not HPSS) so both
        # simultaneous harmonic sources retain their energy in the score matrix
        shs_scores[i, :] = shs_magnitude[harmonic_bins, :].sum(axis=0) / len(harmonic_bins)

    # Extract top-k candidates per frame ensuring they are well-separated in frequency.
    # Minimum separation prevents selecting near-duplicates of the same harmonic series.
    # 3.0 Hz allows detecting callers as close as 4 Hz apart (14 vs 18 Hz case).
    MIN_SEPARATION_HZ = 3.0

    k_actual = min(k, n_candidates)
    top_k_f0s = np.zeros((k_actual, n_frames))
    top_k_scores = np.zeros((k_actual, n_frames))

    for t in range(n_frames):
        scores_t = shs_scores[:, t]
        selected_idx: list[int] = []
        selected_f0s: list[float] = []

        # Greedily select k well-separated peaks
        remaining = scores_t.copy()
        for _ in range(k_actual):
            best_i = int(np.argmax(remaining))
            best_f0 = f0_candidates[best_i]
            selected_idx.append(best_i)
            selected_f0s.append(best_f0)
            # Suppress candidates within MIN_SEPARATION_HZ of this pick
            too_close = np.abs(f0_candidates - best_f0) < MIN_SEPARATION_HZ
            remaining[too_close] = -np.inf

        for rank, (idx, f0) in enumerate(zip(selected_idx, selected_f0s)):
            top_k_f0s[rank, t] = f0
            top_k_scores[rank, t] = scores_t[idx]

    # Sort each frame's top-k by score descending so row 0 = best candidate
    order = np.argsort(-top_k_scores, axis=0)  # (k, n_frames)
    top_k_f0s = np.take_along_axis(top_k_f0s, order, axis=0)
    top_k_scores = np.take_along_axis(top_k_scores, order, axis=0)

    return top_k_f0s, top_k_scores


def link_f0_tracks(
    top_k_f0s: np.ndarray,
    top_k_scores: np.ndarray,
    n_tracks: int = 2,
    jump_hz: float = F0_JUMP_TOLERANCE_HZ,
    min_score_ratio: float = MIN_SCORE_RATIO,
) -> np.ndarray:
    """
    MULTI-02: Greedy nearest-neighbour track linker.

    Seeds each track with its initial frame candidate, then greedily assigns each
    subsequent frame's candidates to the track whose last f0 is closest (within
    jump_hz tolerance). After linking, applies an independent median filter (size=9)
    to each track to remove outlier frames while preserving slow pitch glides.

    Args:
        top_k_f0s:       (K, n_frames) — best K f0 candidates per frame
        top_k_scores:    (K, n_frames) — corresponding SHS scores
        n_tracks:        Number of tracks to produce (default 2)
        jump_hz:         Max Hz jump allowed between consecutive frames
        min_score_ratio: score[1]/score[0] threshold for 2-caller detection

    Returns:
        tracks: (n_tracks, n_frames) float array — one f0 contour per track in Hz
    """
    K, n_frames = top_k_f0s.shape
    n_tracks = min(n_tracks, K)
    tracks = np.zeros((n_tracks, n_frames))

    # Seed tracks using the modal (most common) f0 candidates across all frames.
    # Seeding from the first frame alone is unreliable because edge-of-recording frames
    # may have atypical candidates. Modal seeding picks the dominant pitch globally.
    all_candidates = top_k_f0s.flatten()  # all K*n_frames candidates pooled
    # Round to 1 Hz bins for modal analysis
    rounded = np.round(all_candidates)
    unique_vals, counts = np.unique(rounded, return_counts=True)
    # Greedily pick n_tracks modal values that are >= jump_hz apart from each other
    seed_f0s: list[float] = []
    order_by_count = np.argsort(-counts)
    for idx in order_by_count:
        candidate = float(unique_vals[idx])
        if all(abs(candidate - s) > jump_hz * 0.9 for s in seed_f0s):  # 90% of jump_hz to allow ±10% boundary
            seed_f0s.append(candidate)
        if len(seed_f0s) == n_tracks:
            break
    # Pad with evenly-spaced values if not enough distinct modal candidates found
    while len(seed_f0s) < n_tracks:
        seed_f0s.append(seed_f0s[-1] + jump_hz if seed_f0s else 14.0)
    seed_f0s.sort()  # ascending so track 0 = lower pitch seed

    for t_idx in range(n_tracks):
        tracks[t_idx, 0] = seed_f0s[t_idx]

    # Greedy forward pass: O(n_frames * n_tracks * K)
    # Assign tracks in order of minimum distance to avoid priority bias:
    # tracks with a CLOSER candidate get assigned first, preventing track0 from
    # stealing a candidate that's actually closer to track1.
    for t in range(1, n_frames):
        candidates = top_k_f0s[:, t]       # (K,)
        assigned = [False] * K

        # Compute all pairwise distances: dists_all[track_idx, cand_idx]
        dists_all = np.abs(candidates[np.newaxis, :] - tracks[:, t - 1][:, np.newaxis])

        # Find the minimum distance for each track
        min_dists = dists_all.min(axis=1)  # best distance per track

        # Process tracks in ascending order of minimum distance (closest match first)
        track_order = np.argsort(min_dists)

        for track_idx in track_order:
            dists = dists_all[track_idx].copy()
            # Don't reassign already-assigned candidates
            for ai, a in enumerate(assigned):
                if a:
                    dists[ai] = np.inf
            best = int(np.argmin(dists))
            if dists[best] <= jump_hz:
                tracks[track_idx, t] = candidates[best]
                assigned[best] = True
            else:
                # No candidate within tolerance — hold last known value
                tracks[track_idx, t] = tracks[track_idx, t - 1]

    # Smooth each track independently (never jointly — preserves identity at crossings)
    for track_idx in range(n_tracks):
        tracks[track_idx] = median_filter(tracks[track_idx], size=9)

    # Sort tracks by mean f0 ascending so track 0 = lower pitch, track 1 = higher pitch
    # This gives deterministic labelling regardless of which candidate scored higher
    track_means = tracks.mean(axis=1)
    sort_order = np.argsort(track_means)
    tracks = tracks[sort_order]

    return tracks


def is_multi_speaker(
    top_k_scores: np.ndarray,
    min_score_ratio: float = MIN_SCORE_RATIO,
) -> bool:
    """
    Score ratio gate: True when the recording contains two simultaneous callers.

    A single-caller recording always returns two SHS candidates, but the second
    candidate's score will be much lower (noise floor, not a real harmonic series).
    Gate on: median(score[1] / score[0]) >= min_score_ratio.

    Args:
        top_k_scores:    (K, n_frames) — SHS scores from detect_f0_shs_topk
        min_score_ratio: Threshold for second candidate (default 0.4)

    Returns:
        True if two callers are detected, False for single-caller fallback
    """
    # Avoid division by zero
    ratio = top_k_scores[1] / (top_k_scores[0] + 1e-9)
    return bool(float(np.median(ratio)) >= min_score_ratio)


def is_harmonic_overlap(f0_a: float, f0_b: float, tolerance: float = 0.05) -> bool:
    """
    Degenerate harmonic overlap detector.

    Returns True when one f0 is within `tolerance` (fraction) of an integer multiple
    of the other. In this case, the two callers' comb combs share many frequency bins
    and reliable separation is not possible.

    Args:
        f0_a:      First f0 in Hz
        f0_b:      Second f0 in Hz
        tolerance: Fractional tolerance for integer ratio test (default 0.05 = 5%)

    Returns:
        True if ratio is within 5% of an integer (harmonic overlap), False otherwise

    Examples:
        is_harmonic_overlap(10.0, 20.0) → True  (ratio=2.0, exactly integer)
        is_harmonic_overlap(14.0, 18.0) → False (ratio≈1.29, not integer)
    """
    if f0_a <= 0 or f0_b <= 0:
        return False
    ratio = max(f0_a, f0_b) / min(f0_a, f0_b)
    return abs(ratio - round(ratio)) < tolerance


def separate_speakers(
    ctx: dict,
    f0_tracks: np.ndarray,
    output_dir: str,
    base_name: str,
) -> list[dict]:
    """
    MULTI-03: Build one independent comb mask per f0 track, reconstruct, write WAV.

    For each row i in f0_tracks:
      - Creates a shallow ctx copy with ctx["f0_contour"] = f0_tracks[i]
      - Calls build_comb_mask + apply_comb_mask (existing Phase 2 primitives)
      - Writes ctx_caller["audio_comb_masked"] to {output_dir}/{base_name}_caller_{i+1}.wav

    IMPORTANT: Does NOT re-run HPSS — ctx must already have magnitude_harmonic set.
    Uses ctx["magnitude"] (original) for reconstruction, NOT magnitude_harmonic.
    This is enforced by build_comb_mask and apply_comb_mask internals.

    Args:
        ctx:        Context dict with magnitude, phase, hz_per_bin, sr, hop_length, etc.
        f0_tracks:  (n_tracks, n_frames) — one f0 contour per caller in Hz
        output_dir: Directory path for output WAV files (will be created if missing)
        base_name:  Filename prefix (e.g. "elephant_001")

    Returns:
        List of per-caller ctx dicts, each containing audio_comb_masked, comb_mask, etc.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, f0_contour in enumerate(f0_tracks):
        # Shallow copy — all read-only keys (magnitude, phase, etc.) are shared
        ctx_caller = {**ctx, "f0_contour": f0_contour}
        ctx_caller = build_comb_mask(ctx_caller)   # adds comb_mask
        ctx_caller = apply_comb_mask(ctx_caller)    # adds audio_comb_masked, masked_magnitude

        out_path = out_dir / f"{base_name}_caller_{i + 1}.wav"
        sf.write(str(out_path), ctx_caller["audio_comb_masked"], ctx["sr"])
        results.append(ctx_caller)

    return results
