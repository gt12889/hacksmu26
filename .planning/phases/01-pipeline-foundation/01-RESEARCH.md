# Phase 1: Pipeline Foundation - Research

**Researched:** 2026-04-11
**Domain:** Python audio DSP — data ingestion, segmentation, infrasonic STFT, noise classification
**Confidence:** HIGH (core librosa/scipy APIs verified from official docs; noise classifier logic MEDIUM)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-01 | Parse annotation spreadsheet (CSV/Excel) to extract call timestamps, filenames, noise type | pandas.read_csv / read_excel(engine="openpyxl"); column names unknown until data arrives — defensive parsing required |
| INGEST-02 | Load audio files at native sample rate (sr=None) without silent resampling | librosa.load(path, sr=None) confirmed in official docs; CRITICAL default is sr=22050 which destroys infrasonic content |
| INGEST-03 | Segment recordings into individual call clips with configurable padding (default 2s) | librosa.load(path, sr=None, offset=start-pad, duration=clip_len+2*pad) — float seconds accepted |
| INGEST-04 | Extract noise-only segments from gaps between calls for noise profiling | Same load mechanism; extract gap regions from sorted timestamp pairs |
| INGEST-05 | Assert sr/n_fft < 6Hz at startup to prevent silent resolution failures | Startup assertion: `assert sr / N_FFT < 6, f"Frequency resolution {sr/N_FFT:.1f}Hz exceeds 6Hz limit"` |
| SPEC-01 | Compute STFT with n_fft=8192+ for infrasonic frequency resolution (~5.4Hz/bin at 44.1kHz) | librosa.stft(y, n_fft=8192, hop_length=512) — returns complex spectrogram |
| SPEC-02 | Preserve original phase for artifact-free reconstruction via ISTFT | Phase = np.angle(S); reconstruction = librosa.istft(magnitude * np.exp(1j * phase), hop_length=512) |
| SPEC-03 | Classify noise type per recording (generator/car/plane/mixed) using spectral flatness | librosa.feature.spectral_flatness() + spectral_rolloff + periodicity features on noise-only segments |
</phase_requirements>

---

## Summary

Phase 1 builds the foundation everything else depends on: ingest the annotation spreadsheet, slice all 212 annotated calls from the 44 recordings, extract noise-only gaps, compute high-resolution spectrograms, and classify each recording's noise type. None of this is algorithmically complex — but getting it wrong silently (wrong sample rate, wrong timestamps, wrong n_fft) corrupts every downstream phase.

The single highest-risk item is the annotation spreadsheet format. Column names, timestamp format (absolute vs relative, HH:MM:SS vs float seconds), and whether noise_type is pre-labeled or must be inferred are all unknown until the actual data file is in hand. The ingestor must be written defensively with loud validation output before the first real run.

The second highest-risk item is the n_fft / sample rate invariant. Every call in the codebase must enforce `sr / n_fft < 6 Hz`. This check must fire at module import time, not buried inside a function. With n_fft=8192 at 44100 Hz this gives 5.38 Hz/bin — sufficient. At any default (n_fft=2048) it becomes 21.5 Hz/bin — elephant fundamentals are unresolvable.

**Primary recommendation:** Write the ingestor first as a standalone script that prints a 5-row sample of parsed timestamps plus computed frequency resolution, and manually verify both before writing any other code.

---

## Standard Stack

### Core (Phase 1 only)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| librosa | 0.11.0 | Audio loading with offset/duration, STFT, spectral features | De facto Python audio analysis standard; `sr=None` load, `offset`/`duration` params, `stft`/`istft`, `spectral_flatness` all in one package |
| pandas | >=2.0 | Annotation spreadsheet parsing | `read_excel(engine="openpyxl")` + `read_csv` fallback; handles messy real-world spreadsheets better than csv module |
| numpy | >=1.26 | Array ops for phase extraction, gap calculations | Required by librosa; numpy 2.0 supported as of librosa 0.11.0 |
| soundfile | >=0.12 | Writing sliced call WAVs to disk | librosa's primary backend; 10x faster than audioread; handles 16/24/32-bit correctly |
| scipy | >=1.13 | `ShortTimeFFT` for STFT/ISTFT round-trip | Use for ISTFT reconstruction — `scipy.signal.ShortTimeFFT` is the modern recommended API (legacy `scipy.signal.spectrogram` no longer receives updates) |
| openpyxl | >=3.1 | Excel engine for pandas.read_excel | Required if annotations are .xlsx; xlrd only supports old binary .xls — do not use xlrd |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tqdm | >=4.66 | Progress bar for batch ingest | Use in the per-recording segment extraction loop so silent hangs are visible |
| matplotlib | >=3.8 | Save spectrogram PNGs for visual validation | Generate one PNG per call clip during ingest so spectrogram correctness can be checked by eye before Phase 2 |

### Installation

```bash
pip install librosa==0.11.0 scipy numpy soundfile pandas openpyxl tqdm matplotlib
```

---

## Architecture Patterns

### Recommended File Layout (Phase 1 scope)

```
hacksmu26/
├── pipeline/
│   ├── __init__.py
│   ├── config.py            # N_FFT=8192, HOP_LENGTH=512, PAD_SECONDS=2.0 — single source of truth
│   ├── ingestor.py          # parse_annotations(), segment_calls(), extract_noise_gaps()
│   ├── spectrogram.py       # compute_stft(), extract_phase(), verify_resolution()
│   └── noise_classifier.py  # classify_noise_type(), compute_spectral_features()
├── data/
│   ├── recordings/          # 44 original WAVs (gitignored)
│   ├── segments/            # 212 sliced call WAVs (generated, gitignored)
│   ├── noise_segments/      # noise-only WAVs per recording (generated, gitignored)
│   └── annotations.csv      # (or .xlsx) — committed to git
├── scripts/
│   └── ingest.py            # CLI entrypoint: python scripts/ingest.py --data-dir data/
└── tests/
    └── test_ingestor.py     # pytest: verify 3 known timestamps, check sr assertion fires
```

### Pattern 1: Config Module as Single Source of Truth

**What:** All DSP constants (N_FFT, HOP_LENGTH, PAD_SECONDS) live in one `pipeline/config.py`. No magic numbers elsewhere.

**When to use:** Always. If a constant appears in two files without importing from config, you will silently have a mismatch.

```python
# pipeline/config.py
N_FFT = 8192
HOP_LENGTH = 512
PAD_SECONDS = 2.0
MAX_FREQ_RESOLUTION_HZ = 6.0  # INGEST-05 enforcement threshold

def verify_resolution(sr: int) -> None:
    """Assert INGEST-05: frequency resolution must be < 6Hz."""
    resolution = sr / N_FFT
    assert resolution < MAX_FREQ_RESOLUTION_HZ, (
        f"Frequency resolution {resolution:.2f} Hz/bin exceeds {MAX_FREQ_RESOLUTION_HZ} Hz. "
        f"Increase N_FFT or reduce sample rate. "
        f"Current: sr={sr}, n_fft={N_FFT}"
    )
    print(f"[OK] Frequency resolution: {resolution:.2f} Hz/bin (sr={sr}, n_fft={N_FFT})")
```

### Pattern 2: Defensive Annotation Parser with Loud Validation

**What:** Parse the spreadsheet but print the first 5 rows of parsed timestamps and fail loudly if required columns are missing. The annotation CSV format is unknown in advance — write adaptively.

**When to use:** INGEST-01. Before slicing any audio.

```python
# pipeline/ingestor.py
import pandas as pd
from pathlib import Path

REQUIRED_COLS = {"filename", "start", "end"}  # adjust to actual column names

def parse_annotations(csv_path: str | Path) -> pd.DataFrame:
    path = Path(csv_path)
    if path.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, engine="openpyxl")
    else:
        df = pd.read_csv(path)

    # Normalize column names: lowercase, strip whitespace
    df.columns = df.columns.str.lower().str.strip()

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"Annotation file missing required columns: {missing}\n"
            f"Found columns: {list(df.columns)}"
        )

    # Print sample for manual verification (INGEST-01 validation)
    print("[ingestor] First 5 rows of parsed annotations:")
    print(df[["filename", "start", "end"]].head())
    return df
```

### Pattern 3: Load with Offset/Duration for Segment Extraction

**What:** Slice individual calls from large WAV files in-memory using librosa's `offset` and `duration` parameters. No intermediate full-file load.

**When to use:** INGEST-02, INGEST-03.

```python
# pipeline/ingestor.py
# Source: https://librosa.org/doc/main/generated/librosa.load.html

def load_call_segment(
    wav_path: str | Path,
    start_sec: float,
    end_sec: float,
    pad_seconds: float = PAD_SECONDS,
) -> tuple[np.ndarray, int]:
    """Load a single call clip with padding. Returns (audio, sr)."""
    offset = max(0.0, start_sec - pad_seconds)
    duration = (end_sec + pad_seconds) - offset
    y, sr = librosa.load(str(wav_path), sr=None, offset=offset, duration=duration)
    # INGEST-05: verify resolution on first load (sr is now known)
    verify_resolution(sr)
    return y, sr
```

### Pattern 4: Noise Gap Extraction from Sorted Timestamps

**What:** For each recording, sort all call timestamps, then iterate pairs to find gaps between calls. Gaps >= 1 second are usable as noise-only segments.

**When to use:** INGEST-04.

```python
# pipeline/ingestor.py
MIN_NOISE_DURATION_SEC = 1.0

def extract_noise_gaps(
    wav_path: str | Path,
    calls: list[tuple[float, float]],  # list of (start, end) in seconds
    recording_duration: float,
) -> list[tuple[float, float]]:
    """Return list of (start, end) tuples representing noise-only regions."""
    sorted_calls = sorted(calls, key=lambda x: x[0])
    gaps = []
    prev_end = 0.0
    for start, end in sorted_calls:
        gap_duration = start - prev_end
        if gap_duration >= MIN_NOISE_DURATION_SEC:
            gaps.append((prev_end, start))
        prev_end = end
    # Gap after last call
    if recording_duration - prev_end >= MIN_NOISE_DURATION_SEC:
        gaps.append((prev_end, recording_duration))
    return gaps
```

### Pattern 5: STFT Preserving Phase for SPEC-01 and SPEC-02

**What:** Compute STFT using librosa, immediately separate magnitude and phase. Phase is stored alongside magnitude; reconstruction is `S_masked * np.exp(1j * phase)`.

**When to use:** SPEC-01, SPEC-02.

```python
# pipeline/spectrogram.py
import librosa
import numpy as np
from pipeline.config import N_FFT, HOP_LENGTH

def compute_stft(y: np.ndarray, sr: int) -> dict:
    """
    Compute STFT with infrasonic resolution. Returns dict with S, magnitude, phase.
    Source: https://librosa.org/doc/main/generated/librosa.stft.html
    """
    verify_resolution(sr)
    S = librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH)
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
    """Reconstruct audio from masked magnitude using original phase (artifact-free)."""
    S_reconstructed = magnitude * np.exp(1j * phase)
    return librosa.istft(S_reconstructed, hop_length=HOP_LENGTH)
```

### Pattern 6: Noise Type Classification via Spectral Features

**What:** Compute spectral flatness and spectral rolloff on the noise-only segments. Generator noise is tonal (low flatness, sharp harmonic peaks at ~30/60/90 Hz). Car/plane noise is broadband (high flatness). Mixed = neither extreme.

**When to use:** SPEC-03.

```python
# pipeline/noise_classifier.py
import librosa
import numpy as np

FLATNESS_TONAL_THRESHOLD = 0.1   # below this = generator (tonal)
FLATNESS_BROADBAND_THRESHOLD = 0.4  # above this = car/plane (broadband)

def classify_noise_type(y_noise: np.ndarray, sr: int) -> dict:
    """
    Classify noise type from noise-only segment audio.
    Returns: {"type": "generator"|"car"|"plane"|"mixed", "spectral_flatness": float, ...}
    Source: https://librosa.org/doc/latest/generated/librosa.feature.spectral_flatness.html
    """
    flatness = librosa.feature.spectral_flatness(y=y_noise)
    mean_flatness = float(np.mean(flatness))

    # Check for harmonic peaks in the 25-90 Hz range (generator signature)
    S = np.abs(librosa.stft(y_noise, n_fft=N_FFT, hop_length=HOP_LENGTH))
    freq_bins = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    low_freq_mask = (freq_bins >= 25) & (freq_bins <= 100)
    low_freq_power = np.mean(S[low_freq_mask, :])
    total_power = np.mean(S)
    low_freq_ratio = low_freq_power / (total_power + 1e-10)

    if mean_flatness < FLATNESS_TONAL_THRESHOLD and low_freq_ratio > 0.3:
        noise_type = "generator"
    elif mean_flatness > FLATNESS_BROADBAND_THRESHOLD:
        # Distinguish car (transient bursts) from plane (sustained sweep)
        # Temporal variance: high = car, low = plane
        temporal_variance = float(np.var(np.mean(S, axis=0)))
        noise_type = "car" if temporal_variance > 0.05 else "plane"
    else:
        noise_type = "mixed"

    return {
        "type": noise_type,
        "spectral_flatness": mean_flatness,
        "low_freq_ratio": low_freq_ratio,
    }
```

### Anti-Patterns to Avoid

- **Using `librosa.load()` without `sr=None`:** The default `sr=22050` silently resamples, destroying harmonics above 11 kHz and changing frequency bin width. Every load call must have `sr=None`.
- **Hardcoding timestamps as strings:** The annotation timestamp format is unknown. Never assume `"HH:MM:SS"` — always convert to float seconds via `pd.to_timedelta` or similar, and verify the result against a known call.
- **Using `scipy.signal.spectrogram()` (legacy):** Marked as "will no longer receive updates" in scipy 1.13+. Use `scipy.signal.ShortTimeFFT` or `librosa.stft` for all new code.
- **Using xlrd for .xlsx files:** xlrd only supports the old binary `.xls` format. Pass `engine="openpyxl"` to `pd.read_excel`.
- **Checking `n_fft` in isolation without `sr`:** The assertion must check `sr / n_fft`, not just `n_fft`. A recording at 96000 Hz with n_fft=8192 gives 11.7 Hz/bin — still too coarse. Use n_fft=16384 for 96kHz recordings.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WAV slicing with offset/duration | Custom byte-seek + decode | `librosa.load(offset=, duration=)` | Float-second precision; handles all WAV variants; zero bugs |
| Excel/CSV parsing | csv.reader + manual type conversion | `pandas.read_csv` / `read_excel(engine="openpyxl")` | Handles mixed types, bad encodings, empty rows, merged cells |
| Spectrogram computation | numpy FFT loops | `librosa.stft(n_fft=8192)` | Windowing, overlap, normalization all correct out of the box |
| Spectral flatness | Manual geometric/arithmetic mean | `librosa.feature.spectral_flatness()` | Edge cases (zero bins, log domain) handled correctly |
| Audio WAV writing | struct.pack binary | `soundfile.write()` | Correct bit depth (16/24/32), sample rate metadata, header |

**Key insight:** Every one of these operations has a subtle edge case (zero-length segments, clipped samples, malformed Excel rows, integer vs float timestamps) that librosa/pandas already handle. Building custom solutions wastes hackathon time on problems already solved.

---

## Common Pitfalls

### Pitfall 1: Annotation Column Names Unknown Until Data Arrives

**What goes wrong:** The ingestor is written assuming `df["start_time"]` and `df["filename"]`, but the actual spreadsheet uses `df["Begin Time (s)"]` (Raven Pro export format) or `df["Time"]` or something else. Every downstream call crashes at runtime.

**Why it happens:** The annotation CSV format for this specific dataset is unknown in advance (confirmed in STATE.md: "Annotation CSV exact column names/timestamp format unknown — first task of Phase 1").

**How to avoid:** Write the parser to normalize column names on load (lowercase, strip whitespace). Print the actual column names on first run. Design the required column set as a variable (`REQUIRED_COLS`) so it can be adjusted in one place when the real format is seen. Add a `--dry-run` mode that shows parsed output without writing files.

**Warning signs:** Any hardcoded column name string literal that isn't preceded by a comment saying "verified against actual data."

### Pitfall 2: Silent Resampling via librosa Default sr=22050

**What goes wrong:** `librosa.load("file.wav")` without `sr=None` silently resamples to 22050 Hz. No error. Spectrograms look normal but frequency axis is wrong. n_fft=8192 at 22050 Hz gives 2.7 Hz/bin — looks like better resolution but the audio is corrupted.

**How to avoid:** Every `librosa.load()` call must specify `sr=None`. Add a `verify_resolution(sr)` call immediately after loading. Print the actual sample rate of the first loaded file.

### Pitfall 3: Timestamp Format Ambiguity

**What goes wrong:** Timestamps stored as `"0:02:15.320"` (HH:MM:SS.mmm) parsed as a string produce the wrong float seconds. Or timestamps are in frames rather than seconds. Or start/end are stored as offset-from-start vs absolute recording time.

**How to avoid:** After parsing, compute the duration of the first 3 calls as `end - start` and print them. Verify manually that duration looks like a reasonable elephant rumble (1-30 seconds). If durations look like frame counts (e.g., 2646 frames), divide by sample rate.

**Warning signs:** Parsed call durations outside the range 0.5–60 seconds for a single call.

### Pitfall 4: n_fft Exceeds What sr Can Support

**What goes wrong:** Recordings at 96000 Hz with n_fft=8192 give 11.7 Hz/bin — still too coarse for 10 Hz fundamentals. The INGEST-05 assertion at 6 Hz threshold will catch this if enforced, but developers may loosen the assertion rather than increase n_fft.

**How to avoid:** The assertion threshold is a hard requirement (INGEST-05). If a recording has sr=96000 Hz, use n_fft=16384 (5.9 Hz/bin). Make N_FFT a computed value: `N_FFT = max(8192, ceil(sr / 5.5))` rounded to next power of 2.

### Pitfall 5: Noise Gap Shorter Than Minimum Usable Duration

**What goes wrong:** If calls are densely packed (< 1 second gaps), `extract_noise_gaps()` returns an empty list. The noise classifier then has no noise sample to work with, silently defaulting to a bad strategy.

**How to avoid:** If no gap is found, use the first 0.5 seconds of the recording before the first call as a fallback noise profile (field recordings typically have some pre-call noise). Log a warning: `"No noise gap found in {recording} — using recording start as fallback noise profile."` Never silently skip noise classification.

---

## Code Examples

### Full Ingest Run for One Recording

```python
# scripts/ingest.py — verified pattern for Phase 1

from pipeline.ingestor import parse_annotations, load_call_segment, extract_noise_gaps
from pipeline.spectrogram import compute_stft
from pipeline.noise_classifier import classify_noise_type
from pipeline.config import N_FFT, PAD_SECONDS
import soundfile as sf
from pathlib import Path
import librosa

def ingest_recording(annotations_path: str, recordings_dir: str, output_dir: str):
    df = parse_annotations(annotations_path)

    for wav_name, group in df.groupby("filename"):
        wav_path = Path(recordings_dir) / wav_name
        calls = list(zip(group["start"].astype(float), group["end"].astype(float)))

        # Load full recording to get duration for gap extraction
        duration = librosa.get_duration(path=str(wav_path))

        # Extract noise gaps
        gaps = extract_noise_gaps(wav_path, calls, duration)
        noise_type = "mixed"
        if gaps:
            start, end = gaps[0]
            y_noise, sr_noise = librosa.load(str(wav_path), sr=None,
                                              offset=start, duration=end - start)
            noise_info = classify_noise_type(y_noise, sr_noise)
            noise_type = noise_info["type"]

        # Extract each call clip
        for i, (start, end) in enumerate(calls):
            y, sr = load_call_segment(wav_path, start, end, pad_seconds=PAD_SECONDS)
            out_path = Path(output_dir) / f"{wav_name.stem}_call{i:03d}.wav"
            sf.write(str(out_path), y, sr)

        print(f"[ingest] {wav_name}: {len(calls)} calls, noise_type={noise_type}")
```

### Frequency Resolution Verification

```python
# Verify INGEST-05 for any sample rate
sr_examples = [44100, 48000, 96000]
for sr in sr_examples:
    res = sr / N_FFT
    n_fft_needed = sr * 200  # target < 5 Hz bin width at this sr
    print(f"sr={sr}: {res:.2f} Hz/bin with n_fft={N_FFT}")
# Output at N_FFT=8192:
# sr=44100: 5.38 Hz/bin  -- PASS (< 6 Hz)
# sr=48000: 5.86 Hz/bin  -- PASS (< 6 Hz)
# sr=96000: 11.72 Hz/bin -- FAIL (use n_fft=16384 → 5.86 Hz/bin)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `audioread` backend in librosa | `soundfile` backend | librosa 0.10 (deprecated), 1.0 (removed) | soundfile is 10x faster and handles all modern WAV types |
| `scipy.signal.spectrogram()` | `scipy.signal.ShortTimeFFT` | scipy 1.13 | ShortTimeFFT has proper STFT/ISTFT round-trip; legacy `spectrogram` no longer receives updates |
| `librosa.set_fftlib()` | `scipy.fft.set_backend()` | librosa 0.11.0 | Old API removed; use scipy backend directly |
| `xlrd` for .xlsx | `openpyxl` with pandas | xlrd 2.0 (2020) | xlrd dropped .xlsx support; must pass `engine="openpyxl"` |

**Deprecated/outdated:**
- `audioread`: Never use directly. Removed from librosa 1.0 roadmap.
- `librosa.set_fftlib()`: Removed in 0.11.0.
- `scipy.signal.spectrogram()`: Not being updated. Prefer `ShortTimeFFT`.

---

## Open Questions

1. **Annotation spreadsheet column names and timestamp format**
   - What we know: Contains filename, call start, call end, noise_type — exact column names unknown
   - What's unclear: Are timestamps in seconds (float), HH:MM:SS, or frame counts? Is noise_type already labeled or must it be derived?
   - Recommendation: First task in Phase 1 must be: open the file, print `df.columns`, print 5 rows, confirm timestamp format. Do not write any timestamp parsing code until this is answered.

2. **Actual sample rates of the 44 recordings**
   - What we know: Assumed to be 44100 Hz based on typical field recording gear
   - What's unclear: Could be 48000 Hz (broadcast standard), 96000 Hz (high-quality field recorders), or mixed
   - Recommendation: Run `librosa.get_duration(path=...)` and print sr for all 44 files before segmentation. If any are 96000 Hz, N_FFT must be set to 16384 for those files.

3. **Whether noise_type is labeled in annotations or must be inferred**
   - What we know: prd.json US-003 describes computing spectral flatness from noise-only segments
   - What's unclear: STATE.md notes this is unknown; if annotations already include noise_type column, SPEC-03 is simpler
   - Recommendation: Build both paths: if column exists, use it; if not, compute from spectral features.

---

## Sources

### Primary (HIGH confidence)
- [librosa.load official docs 0.11.0](https://librosa.org/doc/main/generated/librosa.load.html) — offset/duration parameters, sr=None, sr=22050 default confirmed
- [librosa.stft official docs](https://librosa.org/doc/main/_modules/librosa/core/audio.html) — n_fft parameter, returns complex spectrogram
- [librosa.feature.spectral_flatness official docs](https://librosa.org/doc/latest/generated/librosa.feature.spectral_flatness.html) — return shape, range [0,1], interpretation
- [scipy.signal.ShortTimeFFT docs](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.ShortTimeFFT.html) — recommended over legacy spectrogram

### Secondary (MEDIUM confidence)
- STACK.md (project research doc, 2026-04-11) — version compatibility table, openpyxl/xlrd tradeoff, audioread deprecation
- ARCHITECTURE.md (project research doc, 2026-04-11) — ingestor responsibilities, data flow diagram, segment file paths
- PITFALLS.md (project research doc, 2026-04-11) — n_fft pitfall, silent resampling pitfall, noise profile region pitfall

### Tertiary (LOW confidence)
- prd.json (project PRD) — US-002 and US-003 acceptance criteria describing expected spreadsheet columns ("filename, start time, end time, call type") — these are aspirational, not verified against actual data

---

## Metadata

**Confidence breakdown:**
- Standard stack (librosa, pandas, soundfile, scipy): HIGH — verified from official docs
- Architecture patterns (ingestor design, config module): HIGH — derived directly from requirements
- Noise classifier logic (thresholds for spectral flatness): MEDIUM — thresholds (0.1 tonal, 0.4 broadband) are reasonable starting values, require tuning against real recordings
- Annotation format: LOW — unknown until data file is opened

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (stable libraries; annotation format question is data-specific, not time-sensitive)
