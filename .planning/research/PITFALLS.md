# Pitfalls Research

**Domain:** Bioacoustic audio denoising — infrasonic elephant vocalizations
**Researched:** 2026-04-11
**Confidence:** MEDIUM-HIGH (DSP fundamentals HIGH; hackathon-specific MEDIUM; elephant-specific comb masking LOW due to limited published implementations)

---

## Critical Pitfalls

### Pitfall 1: Defaulting n_fft to 2048 (or Worse, 1024) Destroys Infrasonic Resolution

**What goes wrong:**
At 44100 Hz sample rate, n_fft=2048 gives frequency resolution of 44100/2048 ≈ 21.5 Hz per bin. At 22050 Hz (librosa's default resampling), that's 10.8 Hz/bin. An elephant fundamental at 14 Hz falls between two bins, or worse, gets averaged with the engine noise at 30 Hz. The entire scientific premise of the project collapses before any processing begins.

**Why it happens:**
Librosa's default is n_fft=2048. Every tutorial and example uses this. Developers copy from working speech/music code without recalculating what 2048 means in Hz.

**How to avoid:**
Use n_fft=8192 minimum. At 44100 Hz, this gives 5.4 Hz/bin — enough to resolve a 14 Hz fundamental from a 20 Hz fundamental. Do not let librosa resample to 22050 Hz by default; load with `sr=None` to preserve native sample rate, then decide if resampling is needed. The formula: required_n_fft = sample_rate / desired_hz_resolution. For 5 Hz resolution at 44100 Hz: n_fft = 44100/5 = 8820, round up to 16384.

**Warning signs:**
- Spectrograms where the 10-25 Hz range looks like 2-3 coarse blobs instead of distinct lines
- Elephant fundamentals and engine noise appearing in the same frequency bin
- Any code that copies n_fft from a speech processing tutorial without modification

**Phase to address:**
Phase 1 (Pipeline foundation) — establish n_fft=8192+ and sr=None as the project defaults before any other processing code is written.

---

### Pitfall 2: librosa.load() Silently Resamples and Merges Channels

**What goes wrong:**
`librosa.load("file.wav")` defaults to `sr=22050, mono=True`. Field recordings captured at 44100 Hz or 96000 Hz are downsampled, destroying high-harmonic content above 11025 Hz and introducing resampling artifacts in the transition band. Stereo recordings with spatially-separated elephant calls get merged. The developer sees no error — the data is just wrong.

**Why it happens:**
Librosa documents the defaults but they were chosen for speech/music use cases. Bioacoustics developers copy load patterns from music tutorials without reading the parameter docs.

**How to avoid:**
Always load with `librosa.load(path, sr=None, mono=False)` first. Inspect `sr` and channel count. Only downsample if processing budget demands it, and only after verifying the target sr still resolves your lowest frequency of interest. Resampling to 44100 Hz keeps harmonics up to 22050 Hz — sufficient for elephant rumble harmonics up to ~1000 Hz.

**Warning signs:**
- Any load call without explicit `sr=` parameter
- Spectrograms that stop showing content above 11 kHz on recordings you know contain high harmonics
- Sample rate printed as 22050 when you know the recording was 44100 Hz

**Phase to address:**
Phase 1 (Pipeline foundation) — add a defensive assertion at the top of every audio loading function that prints sr and shape, fails loudly if sr < 44100.

---

### Pitfall 3: HPSS Margin Parameter Tuned for Speech Fails on Infrasound

**What goes wrong:**
`librosa.decompose.hpss()` with default kernel sizes is tuned for speech-frequency harmonic content (fundamentals at 80-300 Hz, harmonics spaced ~100 Hz apart). For elephant rumbles, harmonics are spaced 10-20 Hz apart — much narrower in frequency than the default harmonic filter expects. The result: engine noise harmonics at 30/60/90 Hz get classified as "harmonic" (they are horizontal in the spectrogram), and elephant content gets partially discarded.

**Why it happens:**
The HPSS kernel size in the spectrogram domain corresponds to physical Hz. What looks like a narrow horizontal stripe at 200 Hz looks like a wide smear at 15 Hz when using the same pixel kernel.

**How to avoid:**
Tune HPSS kernel sizes in frequency-bin units, not pixel units. With n_fft=8192 at 44100 Hz, one bin = 5.4 Hz. Elephant harmonics are 10-20 Hz apart = 2-4 bins. Set the harmonic filter length to at least 10 bins. Increase `margin` above 1.0 to create a residual bucket that captures neither-harmonic-nor-percussive content (which will include some noise). Test with `margin=(2.0, 2.0)` and inspect the residual component.

**Warning signs:**
- HPSS harmonic component includes clearly tonal engine noise lines
- HPSS harmonic component looks empty in the 10-50 Hz region where elephant content should be
- Default kernel size used without calculating what it means in Hz at your n_fft

**Phase to address:**
Phase 2 (HPSS + harmonic detection) — calibrate kernel sizes first on a known-good recording before running batch.

---

### Pitfall 4: Octave Errors in Subharmonic Summation at Low SNR

**What goes wrong:**
Subharmonic summation (SHS) works by detecting peaks at f0 *and* 2f0, 3f0, 4f0 and voting for the fundamental. When SNR is very low, the true fundamental at 14 Hz may be weaker than the 2nd harmonic at 28 Hz. The algorithm votes 28 Hz as the "most supported" frequency — a one-octave error. Every harmonic comb mask is then built at 28/56/84 Hz instead of 14/28/42 Hz, retaining noise and discarding elephant content.

**Why it happens:**
The elephant's 2nd harmonic is deliberately stronger than the fundamental (stated in project context). SHS algorithms assume fundamental is strongest — the opposite of the elephant case. Standard cetacean-derived SHS implementations make this assumption.

**How to avoid:**
Use a modified SHS that explicitly models the elephant case: weight harmonics by known relative amplitude profiles (2nd harmonic > fundamental for elephants). Alternatively, detect the 2nd harmonic first (stronger peak), then infer f0 as half that frequency, then verify with higher harmonics. Add an octave-check: if detected_f0 > 30 Hz and there's a strong peak at detected_f0/2, halve the estimate.

**Warning signs:**
- Detected f0 values clustering around 25-50 Hz instead of 10-25 Hz for known elephant calls
- Comb masks built at frequencies that clearly correspond to engine harmonics, not elephant harmonics
- Confidence scores high but subjective audio quality poor (mask is on wrong content)

**Phase to address:**
Phase 2 (f0 detection) — test SHS against at least 5 annotated calls with known f0 before trusting batch output.

---

### Pitfall 5: Harmonic Comb Mask Width Too Narrow Causes Temporal Smearing Artifacts

**What goes wrong:**
A comb mask that is exactly 1 bin wide at each harmonic will cleanly remove all harmonic content from a perfectly stationary tone. Real elephant rumbles have pitch modulation — f0 wanders ±2-5 Hz over the call duration. A 1-bin mask at each harmonic leaves pitch-modulated content partially masked, creating audible warbling artifacts in the output. The mask must be wide enough to track pitch drift.

**Why it happens:**
DSP implementations often model signals as stationary. Bioacoustic calls are not — they modulate in pitch (glides, chirps, frequency sweeps). The gap between "this works in theory" and "this sounds right" is pitch modulation handling.

**How to avoid:**
Apply temporal smoothing to the f0 estimate before building the mask (median filter over 5-10 frames). Widen each comb tooth to ±3-5 bins around the center frequency. Use a soft mask (0.0 to 1.0 weights) instead of a hard binary mask at tooth edges — this avoids the abrupt cutoff artifacts.

**Warning signs:**
- Output audio has a "warbling" or "underwater" quality in the 20-100 Hz range
- Spectrogram of output shows alternating retained/masked bins at harmonic frequencies
- f0 estimates are noisy frame-to-frame rather than smoothly evolving

**Phase to address:**
Phase 2 (comb masking) — listen to output of first processed call before batch. Listening takes 30 seconds and catches this immediately.

---

### Pitfall 6: Phase Reconstruction Artifacts When Modifying the Spectrogram Magnitude

**What goes wrong:**
When you multiply a spectrogram magnitude by a mask and then call `librosa.istft()`, you're using the *original* phase from the STFT. If the mask significantly attenuates energy at certain bins, the phase at those bins is now mismatched with the reduced magnitude. Audible artifacts include metallic ringing, musical noise (random tonal blips), and low-frequency rumble that isn't the elephant.

**Why it happens:**
Spectral masking (including Wiener filtering and comb masking) modifies magnitude while leaving phase unchanged. Phase-magnitude consistency is broken. This is only a problem at bin transitions — where mask goes from 1.0 to 0.0 abruptly.

**How to avoid:**
Use soft masks everywhere (never hard binary). Keep mask slope gradual at bin boundaries. For the residual noisereduce step, use its built-in smoothing parameters (`smoothing_factor` and `prop_decrease`). Avoid Griffin-Lim reconstruction in this pipeline — it adds 50-1000 iterations of overhead and may not improve the output enough to justify the cost in a 24-hour hackathon. Instead, use the original phase consistently with a well-designed soft mask.

**Warning signs:**
- Output has musical noise (random tonal artifacts that weren't in the original)
- Listening test reveals metallic-sounding artifacts in mid-frequency ranges
- Hard (binary) masks used anywhere in the pipeline

**Phase to address:**
Phase 2 (masking) — use soft masks from day one; never introduce hard masks as a "temporary simplification."

---

### Pitfall 7: Generator Noise Profile Estimated from Wrong Region

**What goes wrong:**
`noisereduce` learns the noise profile from a provided "noise clip." If the noise clip is too short (< 0.5 seconds), the estimated noise floor has high variance and incorrectly gates frequency bands where noise energy happened to be low in that clip. On the other hand, if the noise clip contains partial elephant vocalization, the vocalization is subtracted as "noise" from the cleaned output.

**Why it happens:**
Field recordings don't have clean "noise-only" sections labeled. Developers grab the first N seconds of a recording as the noise profile, which may contain an elephant rumble already.

**How to avoid:**
Use the project's noise-type classification (generator/car/plane) to select the noise profile strategy:
- **Generator:** Find the quietest 1-2 second window in the recording (minimum RMS). Generator noise is constant so any quiet window is representative.
- **Car/plane:** Use noisereduce's non-stationary mode (`stationary=False`) — these noises vary in amplitude and frequency and a fixed profile will not capture them.
Use `noisereduce.reduce_noise(y=signal, sr=sr, stationary=False)` for transient noise types.

**Warning signs:**
- Cleaned output sounds "underwater" or has spectral smearing in the 100-500 Hz range
- Noise profile clip overlaps with a timestamp in the spreadsheet annotations
- Static noise profile used for car or plane recordings

**Phase to address:**
Phase 1 (noise classification) — build the noise-profile selection logic before the noisereduce call. Do not hardcode a fixed noise clip duration.

---

### Pitfall 8: FastAPI Blocks on Audio Processing, Times Out React Request

**What goes wrong:**
Audio processing (STFT at n_fft=8192 × 212 calls × multi-step pipeline) can take minutes. If the FastAPI endpoint runs processing synchronously in the request handler, the HTTP connection times out (default 30 seconds for most browsers and many frameworks), the React frontend shows a failed request, and the user has no feedback that processing is happening.

**Why it happens:**
It's easiest to write `result = process_audio(file)` directly in the endpoint handler. Works fine for quick operations. Fails for heavy computation.

**How to avoid:**
Use FastAPI's `BackgroundTasks` for processing: accept the upload, return a job ID immediately, process in background. React polls `GET /status/{job_id}` every 2 seconds. Return progress percentage from the background task. This is a 30-minute implementation that prevents the most visible demo failure mode.

**Warning signs:**
- No background task system designed before implementing the processing endpoint
- Processing endpoint has `await` on CPU-bound numpy operations (these don't actually await; use `run_in_executor` for true async)
- No progress feedback UI in the React frontend

**Phase to address:**
Phase 3 (API layer) — design the job queue before implementing any processing endpoint.

---

### Pitfall 9: CORS Misconfiguration Blocks All Browser Requests

**What goes wrong:**
React dev server runs on port 5173. FastAPI runs on port 8000. Browsers block cross-origin requests. Without explicit CORS headers, every fetch() from React returns "Failed to fetch" with no useful error message. This looks like a React bug, a network bug, or a server crash to someone who hasn't hit CORS before.

**Why it happens:**
CORS is invisible in Postman/curl (server-to-server doesn't enforce CORS). Developers test the API with curl, it works, then the React frontend fails and they spend an hour confused.

**How to avoid:**
Add `CORSMiddleware` at FastAPI startup — first line, before any routes. Set `allow_origins=["http://localhost:5173"]` explicitly. Never use `allow_origins=["*"]` with `allow_credentials=True` — this causes a second CORS failure. Do this in the first commit that creates the FastAPI app, not when debugging later.

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
```

**Warning signs:**
- Browser network tab shows "CORS policy" in error details
- curl works but fetch() fails
- Any `allow_origins=["*"]` with `allow_credentials=True` in the same config

**Phase to address:**
Phase 3 (API layer) — add CORS middleware before writing any route handler.

---

### Pitfall 10: Spectrogram Canvas Rendering Freezes Browser for Long Audio Files

**What goes wrong:**
Rendering a 5-minute spectrogram computed at n_fft=8192 produces a matrix of roughly 4096 frequency bins × 13000 time frames. Rendering this as a canvas image in React on the main thread causes a multi-second freeze. With two spectrograms (before/after), plus a harmonic mask overlay, the page becomes unresponsive during render.

**Why it happens:**
`canvas.drawImage()` and `putImageData()` with large typed arrays block the main thread. This is fine at speech-frequency resolution (smaller matrices) but fails at the resolutions needed for infrasound.

**How to avoid:**
Render spectrograms server-side as PNG and serve as static image files from FastAPI. The browser just displays an `<img>` tag — no canvas processing needed for the comparison view. For the interactive overlay (harmonic comb visualization), limit canvas to a zoomed 0-200 Hz slice, not the full spectrum. Use `drawImage(canvas, canvas, offsetX, 0)` for shift operations if real-time canvas work is needed.

**Warning signs:**
- Frontend renders large spectrograms with `putImageData()` in a React useEffect
- No server-side image generation for the before/after comparison
- Canvas dimensions exceed 4096px in either dimension (GPU texture limit on some browsers)

**Phase to address:**
Phase 4 (React frontend) — decide at design time whether spectrograms are server-rendered PNGs or client-rendered canvas. Do not choose client-rendered canvas for files longer than 30 seconds.

---

### Pitfall 11: Browser Autoplay Policy Blocks Audio on Demo Day

**What goes wrong:**
Chrome requires a user gesture before any AudioContext can play sound. If the demo loads a page with auto-playing A/B audio, or if AudioContext is initialized before a click event, Chrome silently suspends the context and no audio plays. On demo day, this looks like the playback feature is broken.

**Why it happens:**
Chrome's autoplay policy (enforced since Chrome 66) is invisible during development if you click the page before testing audio. In a demo, a fresh browser tab with no prior interaction triggers the policy.

**How to avoid:**
Always initialize `AudioContext` inside a click handler, not in `useEffect` on mount. Check `audioContext.state === 'suspended'` and call `audioContext.resume()` on the first user interaction. Use a simple `<audio>` tag with `controls` as a fallback — it handles autoplay policy automatically and works reliably in demos.

**Warning signs:**
- `AudioContext` created in `useEffect` without a user gesture check
- No fallback for suspended AudioContext state
- Demo tested in a browser window that was already interacted with (masks the issue)

**Phase to address:**
Phase 4 (React frontend) — test audio playback in a fresh incognito window before demo. This takes 2 minutes and catches the issue.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hard-coded noise profile path | Skip noise classification logic | Breaks on recordings with different noise types | Never — classification is ~2 hours |
| Binary comb masks instead of soft | Simpler to implement | Phase artifacts, musical noise in output | Never — soft masks are same code complexity |
| Synchronous processing in FastAPI handler | No job queue to implement | Timeout on any recording > 30 seconds | Never — background task is 30 min |
| Fixed n_fft=2048 across all analysis | Consistent with tutorials | Destroys infrasonic frequency resolution | Never |
| Client-side spectrogram rendering | No server-side image generation | Browser freeze on files > 60 seconds | Acceptable if files are < 15 seconds each |
| Skip per-call confidence scoring | Batch runs faster | No way to sort/filter calls by quality | Acceptable if dashboard is cut from scope |
| `allow_origins=["*"]` in CORS | Works immediately | Security risk (not a concern in local demo) | Acceptable for hackathon local-only demo |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| librosa + numpy | Using `librosa.load()` default sr then computing frequency resolution in Hz | Always compute `freq_resolution = sr / n_fft` and verify < 6 Hz before any processing |
| noisereduce + field recordings | Using stationary mode for car/plane noise types | Use `stationary=False` for transient noise; `stationary=True` only for generator constant hum |
| FastAPI + React multipart upload | Sending audio as JSON base64 | Use `multipart/form-data` with `UploadFile`; base64 adds 33% size overhead |
| FastAPI + React audio streaming | Returning entire WAV file in JSON response | Return file via `FileResponse` or stream with `StreamingResponse` |
| STFT → mask → istft | Using `center=True` in stft but `center=False` in istft | Keep `center` parameter consistent between stft and istft calls |
| scipy.signal vs librosa STFT | Mixing scipy and librosa STFT conventions (different normalization) | Use one library for the full STFT/mask/istft chain |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading all 212 calls into RAM simultaneously | OOM crash mid-batch | Stream one call at a time through the pipeline; delete arrays after writing output WAV | At ~20 calls with n_fft=8192 and long recordings |
| Recomputing STFT multiple times per call | Processing takes 10x longer than expected | Compute STFT once per call, pass the matrix through all processing steps | On every call; wastes time budget |
| noisereduce on full recording before segmentation | Noise profile from wrong section of recording | Segment first (using spreadsheet timestamps), then apply noisereduce per segment | Always — architectural choice, not scale issue |
| Per-pixel spectrogram rendering in React | Browser freeze on render | Server-side PNG generation via matplotlib/librosa.display | For any recording > 15 seconds |
| Pandas timestamp parsing without timezone | Timestamps off by hours, wrong segments extracted | Check if spreadsheet timestamps are UTC or local; print 3 parsed timestamps and verify against known call locations | Always — silent correctness issue |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No processing progress indicator | Judge thinks the demo is frozen; refreshes the page and loses the job | Show per-call progress bar ("Processing call 47 of 212") |
| Spectrogram frequency axis not labeled in Hz | Judges cannot see that the infrasonic range is actually being resolved | Always label y-axis with Hz values; highlight 10-100 Hz region |
| A/B toggle has audio-sync offset | Before/after don't align temporally; comparison is misleading | Use same audio start time and Web Audio API scheduling to sync |
| Confidence score not explained | Judges don't know if 73% is good or bad | Show color scale with labels: red=low (<40%), yellow=medium, green=high (>70%) |
| No comparison to LALAL.AI visible on same page | Demo's key differentiator is not clear | Show 3-panel: original / LALAL.AI result / your result, side by side |

---

## "Looks Done But Isn't" Checklist

- [ ] **STFT resolution:** Verify `sr / n_fft < 6 Hz` is printed at pipeline startup — not just that n_fft=8192 is set
- [ ] **Timestamp parsing:** Print 3 parsed segment boundaries and manually verify one against the recording file
- [ ] **Noise type routing:** Verify generator, car, and plane recordings each use the correct noisereduce mode (stationary vs. non-stationary)
- [ ] **f0 detection octave check:** Run against 5 annotated calls with known f0 from the spreadsheet; verify detected f0 is in 10-25 Hz range, not 20-50 Hz range
- [ ] **Output WAV compatibility:** Load one output file in Audacity and verify it opens correctly, sample rate is correct, not clipped
- [ ] **Browser audio test:** Open frontend in fresh incognito window, click play — verify audio plays without clicking "resume" manually
- [ ] **CORS test:** Start both servers, open browser network tab, make a request — verify no CORS errors appear
- [ ] **Batch full run:** Run all 212 calls once before demo; verify no crashes, all outputs written, confidence scores generated

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong n_fft discovered after batch runs | LOW | Rerun batch with correct n_fft; takes same time as original run |
| f0 octave errors in batch output | MEDIUM | Add octave-check heuristic, re-run f0 detection only (no full STFT recompute if cached) |
| CORS blocking frontend | LOW | Add CORSMiddleware, restart server — 5 minutes |
| Browser autoplay blocking demo | LOW | Switch to `<audio controls>` tag — 15 minutes |
| OOM crash mid-batch | MEDIUM | Add `del` and `gc.collect()` after each call; re-run from checkpoint |
| Processing timeout blocking React | HIGH | Refactor to background task + polling; 2-4 hours if done late |
| HPSS misclassifying noise as harmonic | MEDIUM | Tune margin parameter and kernel size; rerun processing steps only |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Wrong n_fft / wrong sr | Phase 1 — Pipeline foundation | Assert `sr/n_fft < 6 Hz` at pipeline start |
| librosa silent resampling | Phase 1 — Pipeline foundation | Print sr and shape on every load |
| Timestamp parsing errors | Phase 1 — Segmentation | Manually verify 3 segment boundaries |
| Noise profile from wrong region | Phase 1 — Noise classification | Log which region is used as noise profile per recording |
| HPSS kernel size for speech, not infrasound | Phase 2 — HPSS | Visual inspection of HPSS components on one known recording |
| Subharmonic summation octave errors | Phase 2 — f0 detection | Spot-check 5 annotated calls with known f0 |
| Harmonic comb mask too narrow for pitch drift | Phase 2 — Comb masking | Listen to first 3 processed calls; check for warbling |
| Phase reconstruction artifacts from hard masks | Phase 2 — Comb masking | Use soft masks from first implementation; never introduce hard masks |
| noisereduce wrong mode for noise type | Phase 2 — Noisereduce | Log which mode is used per noise type; verify routing logic |
| FastAPI sync processing timeout | Phase 3 — API layer | Design BackgroundTasks before any endpoint implementation |
| CORS blocking frontend | Phase 3 — API layer | Add CORSMiddleware before first route; test with browser immediately |
| Canvas freeze on large spectrograms | Phase 4 — React frontend | Decide server-side vs. client-side at design time; test with a 5-minute recording |
| Browser autoplay policy blocking demo | Phase 4 — React frontend | Test in fresh incognito window before demo |
| Scope creep past demo deadline | All phases — time management | Hard stop on stretch features at 18h mark |

---

## Hackathon-Specific Pitfalls

### Pitfall H1: Starting on Stretch Features Before Core Pipeline Validates

The stretch features (multi-caller separation, full dashboard) are high-complexity. Building them before the core STFT/mask/denoise pipeline is verified on real recordings means any pipeline flaw propagates through stretch work, and you have nothing to demo if the core fails.

**Prevention:** Run the full pipeline end-to-end on 3 calls in the first 4 hours. No stretch feature work until that passes a listening test.

---

### Pitfall H2: No Demo Script Rehearsed Before Judging

A working pipeline with an unrehearsed demo looks worse than a partial pipeline with a polished 3-minute demo. Judges see the presentation, not the code.

**Prevention:** Allocate the last 2 hours to demo prep only. One team member owns the demo flow script. Practice it twice.

---

### Pitfall H3: Batch Run Not Completed Before Demo

Judges want to see the dashboard of 212 processed calls. If the batch pipeline hasn't fully run before the demo, there's nothing to show. At n_fft=8192 with multi-step processing, 212 calls may take 15-45 minutes to process.

**Prevention:** Start the batch run at the 20-hour mark. If processing isn't complete by 22 hours, cut scope (process only the 30 highest-confidence calls, skip the rest).

---

### Pitfall H4: LALAL.AI Comparison Unfair to LALAL.AI

If the LALAL.AI comparison uses LALAL.AI's default settings on elephant audio it was never designed for, the comparison is valid but may feel "cheap" to a technically sophisticated judge. On the other hand, if judges see you've genuinely tested LALAL.AI and documented why it fails (spectrograms showing infrasonic content LALAL.AI cannot resolve), this strengthens your pitch.

**Prevention:** Process 5 calls through LALAL.AI explicitly. Capture spectrograms showing where it fails (likely everything below 50 Hz). Include in the demo as evidence, not just assertion.

---

## Sources

- librosa STFT documentation: https://librosa.org/doc/main/generated/librosa.stft.html
- librosa fft_frequencies documentation: https://librosa.org/doc/main/generated/librosa.fft_frequencies.html
- librosa load sr=None deprecation discussion: https://github.com/librosa/librosa/issues/1573
- librosa HPSS documentation: https://librosa.org/doc/latest/generated/librosa.decompose.hpss.html
- noisereduce PyPI: https://pypi.org/project/noisereduce/
- noisereduce GitHub (stationary/non-stationary modes): https://github.com/timsainb/noisereduce
- Griffin-Lim phase reconstruction artifacts (arXiv): https://arxiv.org/pdf/1903.03971
- Subharmonic summation octave error in bioacoustics: https://biomedeng.jmir.org/2025/1/e80089
- Bioacoustic F0 estimation benchmark 2025: https://www.tandfonline.com/doi/full/10.1080/09524622.2025.2500380
- Elephant rumble harmonic structure: https://pmc.ncbi.nlm.nih.gov/articles/PMC12968057/
- EarthToolsMaker elephant rumble detection: https://www.earthtoolsmaker.org/posts/how-to-analyze-elephant-rumbles-at-scale/
- FastAPI CORS configuration: https://davidmuraya.com/blog/fastapi-cors-configuration/
- FastAPI async file upload pitfalls: https://davidmuraya.com/blog/fastapi-file-uploads/
- Web Audio API autoplay policy (Chrome): https://developer.chrome.com/blog/web-audio-autoplay
- MDN autoplay guide: https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay
- Canvas spectrogram performance (drawImage vs putImageData): https://dev.to/hexshift/real-time-audio-spectrograms-in-the-browser-using-web-audio-api-and-canvas-4b2d
- Spectral leakage and windowing (FMP): https://brianmcfee.net/dstbook-site/content/ch06-dft-properties/Leakage.html
- Hackathon scope creep and demo pitfalls: https://medium.com/@BizthonOfficial/top-5-mistakes-developers-make-at-hackathons-and-how-to-avoid-them-d7e870746da1

---
*Pitfalls research for: Elephant bioacoustic denoising — HackSMU 2026*
*Researched: 2026-04-11*
