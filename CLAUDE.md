<!-- GSD:project-start source:PROJECT.md -->
## Project

**ElephantVoices Denoiser**

A domain-specific audio denoising system for ElephantVoices that extracts elephant vocalizations from field recordings contaminated by mechanical noise (generators, cars, planes). Built for HackSMU 2026, it exploits the strict harmonic structure of elephant rumbles to surgically isolate calls even when they share the exact same frequency band as the noise. Delivered as a Python pipeline + FastAPI + React web demo.

**Core Value:** Denoise elephant vocalizations by exploiting their harmonic integer-multiple structure — the one technique that separates us from generic AI denoising tools that fail on infrasonic bioacoustics.

### Constraints

- **Timeline:** 24 hours (HackSMU hackathon)
- **Team:** 2-3 people working in parallel
- **Tech stack:** Python (librosa, noisereduce, scipy, numpy, pandas) + FastAPI + React (Vite + TypeScript)
- **FFT resolution:** Must use n_fft=8192+ (most teams use 1024 → garbage below 50Hz)
- **Data:** 44 recordings, 212 calls — pipeline must handle all without manual intervention
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| librosa | 0.11.0 | Audio loading, STFT, HPSS, feature extraction | De facto standard for Python audio analysis; HPSS built-in; supports n_fft=8192+ for infrasonic resolution; soundfile backend (not audioread) is fast and maintained; March 2025 release |
| scipy | >=1.13 | STFT/ISTFT, signal filtering, ShortTimeFFT | Modern `ShortTimeFFT` class (replaces legacy `spectrogram`) gives full STFT round-trip needed for comb mask apply/invert; ShortTimeFFT is the recommended path for new code in scipy 1.13+ |
| numpy | >=1.26 | Array math, mask construction, harmonic arithmetic | Required by both librosa and scipy; numpy 2.0 supported as of librosa 0.11.0 |
| noisereduce | 3.0.3 | Residual spectral gating after comb mask | Explicitly designed for bioacoustics; stationary (generator hum) and non-stationary (car/plane) modes; no training data needed; lightweight; has a Nature/Scientific Reports paper validating domain-general use |
| soundfile | >=0.12 | WAV I/O (read/write), 24-bit/32-bit float support | librosa's primary backend; 10x faster than audioread; Raven Pro exports 16/24-bit WAV — soundfile handles these correctly |
| pandas | >=2.0 | Parse spreadsheet of 212 annotated timestamps | Standard; `read_excel` with openpyxl engine for .xlsx; `read_csv` fallback |
| FastAPI | 0.115+ | REST API for upload/process/result | Async UploadFile + python-multipart handles large WAV uploads without blocking; native OpenAPI docs; type-safe with Pydantic; production-proven |
| uvicorn | >=0.29 | ASGI server for FastAPI | Standard FastAPI server; `uvicorn[standard]` includes uvloop for performance |
| React + Vite | React 18, Vite 5+ | Web demo UI | Team familiarity declared in PROJECT.md; Vite dev server HMR is fast for demo iteration |
| TypeScript | >=5.0 | Type-safe frontend | Standard with Vite + React template |
| wavesurfer.js | 7.x (7.11+) | Waveform + spectrogram visualization, audio playback | Only library with both (a) built-in spectrogram plugin and (b) official React wrapper (@wavesurfer/react); TypeScript types included; v7 Shadow DOM isolation avoids CSS collisions; actively maintained |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| openpyxl | >=3.1 | Excel .xlsx engine for pandas.read_excel | When annotation spreadsheet is .xlsx format |
| python-multipart | >=0.0.9 | Required by FastAPI for UploadFile/form data | Always — file upload won't work without it |
| numba | >=0.59 | JIT-accelerate inner loops (optional) | If n_fft=8192 batch processing of 212 calls is too slow; librosa uses it automatically if installed |
| tqdm | >=4.66 | Progress bars for batch pipeline | Batch processing 212 calls without feedback is painful to debug |
| pydantic | >=2.0 | Request/response models in FastAPI | Already a FastAPI dependency; define `ProcessRequest`, `ProcessResult` schemas explicitly |
| axios | latest | HTTP client for React → FastAPI calls | Standard React HTTP client for multipart uploads |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Python test runner | Verify pipeline on a single clip before running all 212 |
| black + ruff | Python formatting + linting | Keeps team code consistent during 24-hour sprint |
| vite | Frontend build tool | `npm create vite@latest` with react-ts template |
| concurrently | Run FastAPI + Vite together | `concurrently "uvicorn main:app --reload" "npm run dev"` in root package.json |
## Installation
# Python backend
# Frontend
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| librosa 0.11.0 | torchaudio | If the team adds ML model inference (U-Net, etc.) — torchaudio integrates better with PyTorch pipelines. Out of scope for this hackathon. |
| librosa 0.11.0 | essentia | Essentia has more MIR features but is harder to install (C++ bindings) and less common. No advantage for this use case. |
| scipy ShortTimeFFT | librosa.stft alone | librosa.stft is fine for forward transform; use scipy ShortTimeFFT when you need clean ISTFT round-trip for mask application at n_fft=8192 |
| noisereduce | pysndfx / pedalboard | Those are effects chains (EQ, compression), not spectral gating denoising. Wrong tool category. |
| soundfile | audioread | audioread is deprecated in librosa 0.10+ and will be removed in 1.0. Do not use. |
| wavesurfer.js | Plotly.js spectrogram | Plotly can render spectrograms but has no audio playback or A/B toggle capability. wavesurfer.js is the only option that handles both visualization and playback. |
| wavesurfer.js | custom Canvas + Web Audio API | Correct approach for production but not buildable in 24 hours. wavesurfer.js gives this out of the box. |
| FastAPI | Flask | Flask is synchronous; file uploads block the thread. FastAPI's async UploadFile is necessary for large WAV files without a queue. |
| pandas | csv module | Annotation spreadsheet likely has timestamps, labels, and metadata; pandas handles messy Excel data far better than csv module. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| audioread | Deprecated in librosa 0.10, removed in 1.0; 10x slower than soundfile for WAV | soundfile (librosa uses it automatically) |
| librosa.set_fftlib() | Deprecated in 0.11.0, removed in 1.0 | scipy.fft.set_backend() if needed |
| scipy.signal.spectrogram() (legacy) | Marked as "will no longer receive updates" in scipy 1.13+; missing features | scipy.signal.ShortTimeFFT |
| xlrd for .xlsx | xlrd only supports old .xls binary format now; will raise an error on .xlsx | openpyxl engine with pandas.read_excel |
| pydub | Convenient but wraps ffmpeg CLI, adds process overhead, poor float precision for DSP | soundfile directly |
| ML denoising models (Demucs, RNNoise) | Trained on speech/music frequencies; fail on infrasonic content; also not trainable in 24 hours on 44 recordings | Domain-specific harmonic comb masking + noisereduce |
| n_fft < 4096 | At 44100 Hz sample rate, n_fft=1024 gives ~43 Hz frequency resolution — garbage for 10-20 Hz fundamentals. Most tutorials use 1024 and will send you down a dead end. | n_fft=8192 (5.4 Hz resolution at 44100 Hz) |
| Default librosa.load() sample rate (sr=22050) | Downsampling to 22050 Hz cuts harmonics above 11025 Hz and changes frequency resolution. Load at native sample rate. | librosa.load(path, sr=None) |
## Stack Patterns by Variant
- Use librosa + scipy + noisereduce directly in a Python script
- Parallelize with `concurrent.futures.ProcessPoolExecutor` (each file is independent)
- tqdm for progress; log confidence scores to CSV via pandas
- FastAPI `UploadFile` → save to `tempfile.NamedTemporaryFile` → run pipeline → return WAV bytes as `StreamingResponse`
- React: upload form → poll job status → render wavesurfer.js with before/after toggle
- Compute spectrogram in Python, serialize as JSON array (frequency bins × time frames, downsampled for transfer)
- Render as a Canvas overlay on top of wavesurfer.js — wavesurfer does not natively support custom mask overlays, so you draw the comb on a `<canvas>` positioned absolutely over the waveform
- Use `noisereduce.reduce_noise(y, sr, stationary=True, prop_decrease=0.8)` after comb masking
- Capture noise profile from a pre-call silence segment
- Use `noisereduce.reduce_noise(y, sr, stationary=False)` — estimates noise dynamically
- Apply after comb masking; noisereduce handles the sweep without an explicit noise profile
## Version Compatibility
| Package | Compatible With | Notes |
|---------|-----------------|-------|
| librosa==0.11.0 | numpy>=1.26, scipy>=1.13 | numpy 2.0 explicitly supported as of 0.11.0 release notes (March 2025) |
| scipy>=1.13 | numpy>=1.26 | scipy requires numpy 1.26.4+ for Feb 2026 releases |
| noisereduce==3.0.3 | numpy, scipy, librosa | No known conflicts; pure Python + numpy |
| wavesurfer.js 7.x | React 18, TypeScript 5 | Shadow DOM in v7 — do not try to inject global CSS into wavesurfer container |
| FastAPI 0.115+ | Pydantic v2 | FastAPI 0.100+ requires Pydantic v2; do not mix with Pydantic v1 |
| python-multipart >=0.0.9 | FastAPI 0.115+ | Earlier versions had security CVEs; use 0.0.9+ |
## Sources
- PyPI librosa page + librosa.org/doc changelog — librosa 0.11.0 released March 11, 2025; numpy 2.0 support confirmed; audioread deprecation confirmed; scipy FFT backend change confirmed. HIGH confidence.
- GitHub timsainb/noisereduce + Nature Scientific Reports paper (2025) — version 3.0.3 confirmed; bioacoustics domain explicitly listed; stationary/non-stationary modes confirmed. HIGH confidence.
- scipy.org docs (ShortTimeFFT page, v1.17.0) — ShortTimeFFT is the recommended modern API; legacy spectrogram "no longer receives updates" confirmed. HIGH confidence.
- wavesurfer.xyz official docs + npm page — v7.11+ confirmed active; @wavesurfer/react official package; Spectrogram plugin with fftSamples param confirmed; TypeScript included. HIGH confidence.
- FastAPI official docs (fastapi.tiangolo.com) + PyPI — 0.115+ stable; python-multipart required for UploadFile; CORS middleware built-in. HIGH confidence.
- WebSearch: FastAPI version (0.135.1 cited for March 2026), pandas 3.0.2 docs for read_excel/openpyxl. MEDIUM confidence (version numbers from search, not official release page directly).
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
