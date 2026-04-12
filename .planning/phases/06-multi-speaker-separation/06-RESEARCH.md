# Phase 6: Multi-Speaker Separation - Research

**Researched:** 2026-04-11
**Domain:** Multi-pitch tracking, harmonic source separation, time-frequency masking
**Confidence:** HIGH (algorithm design is self-contained; verified against existing codebase primitives)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MULTI-01 | System detects multiple f0 tracks when elephants vocalize simultaneously | Modified SHS returning top-2 candidates per frame; greedy track linker |
| MULTI-02 | System identifies crossing harmonics to distinguish different callers | Crossing is a *feature* not a bug — same-caller harmonics are phase-locked integer multiples, cross-caller harmonics are independent. Track continuity + harmonic lock discriminates. |
| MULTI-03 | System outputs separate cleaned WAV per detected caller | Build independent comb mask per track → apply to original magnitude → ISTFT via existing reconstruct_audio() |
| MULTI-04 | Generates multi-speaker spectrogram figure showing separated f0 tracks in different colors | ax.imshow() spectrogram + ax.plot() one color per f0 track; reuse existing figure style |
</phase_requirements>

---

## Summary

Phase 6 extends the existing single-f0 pipeline to handle simultaneous vocalizations from two elephants. The core insight (from the domain brief) is that harmonics from a single caller are phase-locked integer multiples of one f0 — they can never cross in the time-frequency plane. When two callers vocalize simultaneously, their harmonic series are independent, so the pitch contours *can* cross. Track continuity and harmonic coherence are the discriminating features.

The algorithm consists of three connected stages: (1) extend `detect_f0_shs` to return the top-2 SHS scores per frame instead of a single argmax; (2) link frame-level candidates into temporally continuous tracks using a greedy nearest-neighbor forward pass with a configurable pitch-jump tolerance; and (3) for each confirmed track, build an independent comb mask using the existing `build_comb_mask` primitive and reconstruct a separate WAV via the existing `reconstruct_audio` function.

All heavy lifting reuses existing pipeline primitives. The new code is three focused functions: `detect_f0_shs_topk`, `link_f0_tracks`, and `separate_speakers`. The figure (MULTI-04) adds two `ax.plot()` calls on the existing spectrogram axes — no new figure infrastructure needed.

**Primary recommendation:** Implement as a standalone `pipeline/multi_speaker.py` module that accepts a `ctx` dict and returns a list of per-caller `ctx` copies. Keep the existing `harmonic_processor.py` pipeline untouched.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | >=1.26 | Top-k candidate extraction, track arrays, mask arithmetic | Already in stack; `np.argpartition` gives O(n) top-k without full sort |
| librosa | 0.11.0 | STFT, HPSS, ISTFT — all already called | Already in stack; no new dependency |
| matplotlib | >=3.8 | Multi-color f0 track overlay on spectrogram | Already used in Phase 3 figures |
| scipy.ndimage.median_filter | >=1.13 | Smooth per-track f0 contour after linking | Already in stack; used in `detect_f0_shs` |
| soundfile | >=0.12 | Write separate per-caller WAV files | Already in stack |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy.signal | >=1.13 | Optional: validate separation quality on synthetic mixture | For the synthetic test case only (MULTI-01 validation) |

No new dependencies required. Phase 6 is pure algorithmic extension of Phase 2.

**Installation:** No new packages — all libraries already in `requirements.txt`.

---

## Architecture Patterns

### Recommended Project Structure
```
pipeline/
├── harmonic_processor.py   # UNCHANGED — existing single-f0 chain
├── multi_speaker.py        # NEW — multi-f0 detection + separation
└── config.py               # UNCHANGED — add F0_JUMP_TOLERANCE_HZ constant

scripts/
└── demo_multi_speaker.py   # NEW — synthetic test + figure generation

tests/
└── test_multi_speaker.py   # NEW — unit tests on synthetic mixture
```

### Pattern 1: Top-K SHS Extension

**What:** Modify the frame-level argmax in `detect_f0_shs` to return the indices of the top-2 SHS scores per frame. The existing SHS score matrix `shs_scores[i, t]` (candidates × frames) already contains all the information needed.

**When to use:** Whenever the mixture may contain ≥2 simultaneous callers.

**Key implementation detail:** `np.argpartition` on `shs_scores[:, t]` gives O(n_candidates) top-k extraction without sorting the full array. For K=2 this matters little at runtime, but it's the idiomatic numpy pattern.

```python
# Source: numpy.argpartition docs (numpy.org/doc/stable)
# shs_scores shape: (n_candidates, n_frames)
K = 2
# Per frame: indices of top-K candidates (unordered)
# argpartition(-arr, K-1) partitions so top K are in positions [0..K-1]
top_k_idx = np.argpartition(-shs_scores, K - 1, axis=0)[:K, :]  # shape (K, n_frames)
# Get the actual candidate f0 values
top_k_f0s = f0_candidates[top_k_idx]         # shape (K, n_frames)
top_k_scores = np.take_along_axis(shs_scores, top_k_idx, axis=0)  # shape (K, n_frames)
```

**Critical gotcha:** `argpartition` does NOT sort the top-K indices — the 0th row is not necessarily the best. Sort by score descending after extracting:

```python
# Sort top-k by score descending within each frame
order = np.argsort(-top_k_scores, axis=0)   # shape (K, n_frames)
top_k_f0s   = np.take_along_axis(top_k_f0s,   order, axis=0)
top_k_scores = np.take_along_axis(top_k_scores, order, axis=0)
```

### Pattern 2: Greedy Track Linker

**What:** Forward pass over frames. For each frame, assign each candidate f0 to the existing track whose last f0 is closest, subject to a pitch-jump tolerance. If no track is within tolerance, optionally start a new track (capped at K=2). Works left-to-right: O(n_frames × K²).

**When to use:** When only 2 simultaneous callers are expected (stretch goal, not generalized K).

**Design choice — greedy vs Viterbi:**
- Full Viterbi requires defining transition cost and emission cost matrices; correct but adds ~50 lines and a backward pass.
- Greedy nearest-neighbor is adequate for elephant calls because: (a) f0 changes slowly (infrasonic, 8-25 Hz range, smooth glides), (b) we use a 5-frame look-ahead via median smoothing afterward, (c) the 24-hour hackathon time budget favors the simpler implementation.
- Recommendation: **greedy forward pass**. If tracks swap identity at crossings, a post-hoc identity correction can be applied using the harmonic coherence score (re-score the full track against the SHS spectrum and swap if swapped tracks score higher).

```python
# Greedy linker — O(n_frames * K^2)
F0_JUMP_HZ = 4.0   # max Hz jump allowed between consecutive frames
tracks = [{"f0s": [], "active": True} for _ in range(K)]
# ... seed first frame, then greedily assign subsequent frames
# median filter each track's f0 contour afterward
```

**Track validity gate:** A track is considered real if it spans at least `MIN_TRACK_FRAMES` consecutive active frames (suggest 10 frames ≈ 0.12 s at HOP_LENGTH=512, sr=44100). Tracks shorter than this are noise artifacts and should be suppressed.

### Pattern 3: Independent Comb Mask + Reconstruction

**What:** For each valid f0 track, call the existing `build_comb_mask` with that track's f0 contour, then `reconstruct_audio` to get a per-caller WAV. The masks overlap in frequency where harmonics coincide — this is acceptable because elephant callers at different f0 have harmonics at different exact Hz values, and the comb bandwidth (±5 Hz) is narrow enough that they rarely overlap unless f0_a is an integer multiple of f0_b (unlikely in the 8-25 Hz range for two independent callers).

**When to use:** After track linking produces two valid f0 contours.

```python
# Reuse existing primitives — no new reconstruction code needed
for i, f0_contour in enumerate(valid_tracks):
    ctx_copy = ctx.copy()
    ctx_copy["f0_contour"] = f0_contour
    ctx_copy = build_comb_mask(ctx_copy)          # existing function
    ctx_copy = apply_comb_mask(ctx_copy)           # existing function
    # write ctx_copy["audio_comb_masked"] to WAV as caller_{i+1}.wav
```

**Important:** Use `ctx["magnitude"]` (original), NOT `magnitude_harmonic`, in the per-caller mask — exactly as the existing pipeline does. This preserves original amplitude relationships.

### Pattern 4: Multi-Speaker Figure (MULTI-04)

**What:** Render the log-magnitude spectrogram using `ax.imshow()`, then overlay each f0 contour with a distinct color using `ax.plot()`. Matches the existing Phase 3 figure style.

```python
# Pattern consistent with existing Phase 3 demo scripts
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

TRACK_COLORS = ["#FF4444", "#4488FF"]   # red for caller A, blue for caller B

fig, ax = plt.subplots(figsize=(14, 5))
# Spectrogram background (reuse existing imshow pattern from Phase 3)
ax.imshow(
    20 * np.log10(ctx["magnitude"] + 1e-9),
    origin="lower",
    aspect="auto",
    extent=[0, n_frames * hop_length / sr, 0, sr / 2],
    cmap="magma",
    vmin=-80, vmax=0,
)
# Overlay f0 tracks
time_axis = np.arange(n_frames) * hop_length / sr
for i, (f0_contour, color) in enumerate(zip(valid_tracks, TRACK_COLORS)):
    ax.plot(time_axis, f0_contour, color=color, linewidth=2,
            label=f"Caller {i+1}: {f0_contour.mean():.1f} Hz")
ax.set_ylim(0, 300)   # zoom to infrasonic + first ~10 harmonics
ax.legend()
ax.set_xlabel("Time (s)")
ax.set_ylabel("Frequency (Hz)")
fig.savefig("multi_speaker.png", dpi=300, bbox_inches="tight")
```

### Synthetic Test Case (MULTI-01 Validation)

The algorithm must be validated on a controlled mixture before running on real recordings. Generate two independent harmonic sources at f0_a=14 Hz and f0_b=18 Hz, mix them, and verify that the tracker recovers both f0 values within ±1 Hz.

```python
# Synthetic mixture at sr=44100
sr = 44100
duration = 5.0
t = np.linspace(0, duration, int(sr * duration))

def synth_harmonic(f0, n_harmonics=10, sr=44100):
    """Sum of sine waves at f0, 2*f0, ..., n*f0."""
    y = np.zeros(len(t))
    for k in range(1, n_harmonics + 1):
        if k * f0 < sr / 2:
            y += np.sin(2 * np.pi * k * f0 * t) / k  # 1/k amplitude rolloff
    return y / np.max(np.abs(y))

# Mix at equal amplitude — worst case for separation
y_a = synth_harmonic(14.0)
y_b = synth_harmonic(18.0)
y_mix = 0.5 * y_a + 0.5 * y_b
```

This lets us verify: (1) top-2 SHS recovers both f0 values, (2) track linker produces two stable tracks, (3) per-caller reconstructions match the individual sources when compared via SNR.

### Anti-Patterns to Avoid

- **Running HPSS on per-caller audio:** HPSS operates on the mixture; apply it once to `ctx` before the multi-speaker split. Never re-run HPSS on the reconstructed per-caller audio.
- **Modifying `harmonic_processor.py`:** The existing single-f0 pipeline must remain unmodified. Phase 6 is additive.
- **Hard binary comb masks for separation:** The existing soft triangular mask is essential. Hard binary masks create audible artifacts at mask boundaries.
- **Using `magnitude_harmonic` for reconstruction:** As documented in `apply_comb_mask`, always use `ctx["magnitude"]` (original) for the final reconstruction.
- **Median-filtering across tracks:** Each track's f0 contour must be median-filtered independently. Joint filtering would smear the identity of the two tracks at crossing points.
- **Assuming both tracks are always active:** Many frames will have only one caller. The track linker must handle "inactive" frames where a track's SHS score falls below a minimum threshold (suggest: score < 10% of max score across all frames for that track).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Top-K candidate extraction | Custom sort loop | `np.argpartition` | O(n) vs O(n log n); already in numpy |
| Per-caller audio reconstruction | Custom ISTFT wrapper | `reconstruct_audio(masked_mag, ctx["phase"])` | Exact same function already tested in Phase 2 |
| Harmonic mask construction | Custom mask loop | `build_comb_mask(ctx)` | Existing function handles bin clamping, soft window, ±5 Hz bandwidth |
| WAV file export | Custom soundfile wrapper | `soundfile.write(path, audio, sr)` | One-liner; `soundfile` is already in stack |
| Spectrogram figure base | Re-implement imshow pipeline | Existing Phase 3 figure code | Copy the pattern from `scripts/demo_spectrograms.py` |

**Key insight:** Phase 6 requires approximately 100-150 lines of NEW code. Everything else delegates to existing, tested pipeline functions.

---

## Common Pitfalls

### Pitfall 1: Track Identity Swap at Crossings
**What goes wrong:** At the frame where two f0 contours cross (f0_a descending, f0_b ascending), the greedy linker may swap identities — track A picks up f0_b's value and vice versa.

**Why it happens:** The crossing point is ambiguous to a pure frame-level distance metric. Both candidates are equidistant from both tracks.

**How to avoid:** After linking, check harmonic coherence continuity: re-score each track against the full SHS spectrum. If swapping the last N frames of two tracks improves their combined SHS score, apply the swap. Alternatively, add a small "inertia" cost: prefer the candidate that minimizes the sum of distance AND the second derivative of f0 (penalize sudden direction reversals).

**Warning signs:** The output figure shows the two f0 tracks crossing and then both continuing in the swapped direction after the crossing point.

### Pitfall 2: Single-Caller Recordings Misidentified as Two-Caller
**What goes wrong:** SHS always returns two candidates. In a single-caller recording, the second candidate is noise. The linker may build a spurious second track.

**Why it happens:** No voicing detection gate is applied before the linker.

**How to avoid:** Gate on SHS score ratio. If `score[1] / score[0] < MIN_SCORE_RATIO` (suggest 0.4) for more than 80% of frames, classify as single-caller and fall back to the existing `detect_f0_shs` + `build_comb_mask` pipeline. This is critical for the hackathon — most recordings will be single-caller.

**Warning signs:** Second caller's f0 is very close to first caller's f0 (within 1-2 Hz) or the second track is irregular/gappy.

### Pitfall 3: Harmonic Overlap When f0_b ≈ 2 × f0_a
**What goes wrong:** If caller A is at 10 Hz and caller B is at 20 Hz, B's fundamental overlaps with A's 2nd harmonic. Their harmonic series collide at every even multiple of 10 Hz. Comb masks will assign ambiguous bins to both callers.

**Why it happens:** The two harmonic combs are not independent when one f0 is an integer multiple of the other.

**How to avoid:** For the hackathon scope (8-25 Hz range), the ratio f0_b/f0_a being exactly an integer is unlikely in real data. Detect this case (ratio within 5% of an integer) and warn in the output log. Do not attempt to separate in this degenerate case — fall back to single-caller output.

**Warning signs:** Separated WAVs sound nearly identical to each other.

### Pitfall 4: Frame Count Mismatch Between Tracks and Audio
**What goes wrong:** The per-caller f0 contour has `n_frames` values but the audio array length from `reconstruct_audio` may differ by a few samples from the original audio length, causing silent padding issues.

**Why it happens:** ISTFT length depends on `n_frames × hop_length` which may not exactly match the input audio length.

**How to avoid:** This is already handled by `librosa.istft` when called via `reconstruct_audio` — it returns the correct length. No special handling needed. Document the known behavior.

---

## Code Examples

Verified patterns from existing codebase and numpy docs:

### Top-2 SHS Candidates Per Frame
```python
# Source: existing detect_f0_shs + numpy.argpartition docs
# shs_scores: (n_candidates, n_frames) — already computed by existing SHS loop
K = 2
# Partition: top K unsorted, then sort descending
top_k_idx = np.argpartition(-shs_scores, K - 1, axis=0)[:K, :]
top_k_scores = np.take_along_axis(shs_scores, top_k_idx, axis=0)
top_k_f0s = f0_candidates[top_k_idx]
# Sort by score descending (best candidate = row 0)
order = np.argsort(-top_k_scores, axis=0)
top_k_f0s = np.take_along_axis(top_k_f0s, order, axis=0)
top_k_scores = np.take_along_axis(top_k_scores, order, axis=0)
# Result: top_k_f0s[0, :] = best f0 per frame, top_k_f0s[1, :] = second-best
```

### Greedy Track Linker (Simplified)
```python
# Source: algorithm derived from domain insight + standard greedy DP
def link_f0_tracks(top_k_f0s, top_k_scores, n_tracks=2,
                   jump_hz=4.0, min_score_ratio=0.4):
    """
    top_k_f0s:    (K, n_frames) — best K f0 candidates per frame
    top_k_scores: (K, n_frames) — corresponding SHS scores
    Returns: list of n_tracks f0 contour arrays, shape (n_frames,) each
    """
    n_frames = top_k_f0s.shape[1]
    tracks = np.zeros((n_tracks, n_frames))
    # Seed: first frame gets the top-K candidates as track starts
    for k in range(n_tracks):
        tracks[k, 0] = top_k_f0s[k, 0]

    for t in range(1, n_frames):
        candidates = top_k_f0s[:, t]   # shape (K,)
        assigned = [False] * len(candidates)
        for k in range(n_tracks):
            # Find closest unassigned candidate within jump_hz
            dists = np.abs(candidates - tracks[k, t - 1])
            dists[assigned] = np.inf
            best = np.argmin(dists)
            if dists[best] <= jump_hz:
                tracks[k, t] = candidates[best]
                assigned[best] = True
            else:
                # No candidate within tolerance — hold last value
                tracks[k, t] = tracks[k, t - 1]

    # Smooth each track independently
    from scipy.ndimage import median_filter
    for k in range(n_tracks):
        tracks[k] = median_filter(tracks[k], size=9)
    return tracks
```

### Per-Caller Reconstruction
```python
# Source: existing apply_comb_mask pattern in harmonic_processor.py
import soundfile as sf

def separate_speakers(ctx, f0_tracks, output_dir, base_name):
    """Build one comb mask per track, reconstruct and write WAV."""
    results = []
    for i, f0_contour in enumerate(f0_tracks):
        ctx_caller = {**ctx, "f0_contour": f0_contour}
        ctx_caller = build_comb_mask(ctx_caller)   # existing function
        ctx_caller = apply_comb_mask(ctx_caller)    # existing function
        out_path = f"{output_dir}/{base_name}_caller_{i+1}.wav"
        sf.write(out_path, ctx_caller["audio_comb_masked"], ctx["sr"])
        results.append(ctx_caller)
    return results
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full Viterbi for pitch tracking | Greedy nearest-neighbor + median filter | Standard for real-time/hackathon use | Same output quality for slow-moving pitch (elephants); 80% less code |
| Separate STFT per caller | Single STFT + independent masks | Always preferred | Phase preservation from original recording; no reconstruction artifacts |
| Hard binary comb mask | Soft triangular mask | Already established in Phase 2 | Avoids musical noise at mask edges |

**Deprecated/outdated:**
- Full polyphonic separation (NMF, ICA, deep learning): Not needed here — we know the structure is harmonic, so the comb mask approach is cleaner and domain-specific.

---

## Open Questions

1. **Score ratio threshold for single-caller detection**
   - What we know: Need to gate on SHS score ratio (score[1] / score[0]) to avoid spurious second tracks.
   - What's unclear: Optimal threshold — 0.4 is a reasonable first guess but needs empirical tuning on real recordings.
   - Recommendation: Start at 0.4. The synthetic test case will reveal if it needs adjustment.

2. **Track identity at exact crossing frames**
   - What we know: Greedy linker can swap identities at exact crossings.
   - What's unclear: How often this happens with real elephant calls; fundamentals rarely make sharp-crossing glides.
   - Recommendation: Implement swap-detection as a post-processing step (check if swapping the tail of two tracks increases their joint SHS score). Skip if not triggering in the synthetic test.

3. **Whether any real recordings in the dataset contain simultaneous callers**
   - What we know: The hackathon brief mentions this as a stretch goal; no confirmed examples in the 44 recordings.
   - What's unclear: Whether the algorithm will ever fire on real data during the demo.
   - Recommendation: Prioritize the synthetic test case for the demo. If time allows, run the multi-speaker detector on all 212 calls and flag any with score ratio > threshold as candidates.

---

## Sources

### Primary (HIGH confidence)
- Existing `pipeline/harmonic_processor.py` — direct code inspection; SHS implementation, `build_comb_mask`, `apply_comb_mask`, `reconstruct_audio` primitives all verified.
- `numpy.argpartition` official docs (numpy.org/doc/stable/reference/generated/numpy.argpartition.html) — top-k selection pattern verified.
- Existing `pipeline/spectrogram.py` — `reconstruct_audio` signature and behavior verified directly.

### Secondary (MEDIUM confidence)
- WebSearch: "source separation independent harmonic comb masks two pitches ISTFT" — confirmed that mask-then-ISTFT is the standard approach; librosa ISTFT pattern verified against existing code.
- WebSearch: "matplotlib spectrogram two f0 tracks different colors" — confirmed ax.imshow + ax.plot overlay pattern; consistent with Phase 3 figure code already in codebase.

### Tertiary (LOW confidence — verify on synthetic test)
- Score ratio threshold (0.4) for single-caller gate: derived from first principles, not verified empirically.
- Jump tolerance (4.0 Hz) for greedy linker: reasonable for infrasonic calls (slow pitch glides); not benchmarked against real data.

---

## Metadata

**Confidence breakdown:**
- Algorithm design: HIGH — directly derived from existing codebase primitives; no new dependencies
- Top-K SHS extension: HIGH — numpy.argpartition documented and verified
- Track linker: MEDIUM — greedy approach is correct in principle; thresholds (jump_hz, min_score_ratio) need empirical tuning
- Figure overlay: HIGH — ax.plot() on ax.imshow() is standard matplotlib and matches Phase 3 pattern

**Research date:** 2026-04-11
**Valid until:** Stable — no external dependencies change; only algorithmic tuning thresholds may need revision after synthetic test.
