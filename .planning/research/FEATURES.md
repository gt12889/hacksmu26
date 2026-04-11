# Feature Research

**Domain:** Bioacoustic denoising — elephant vocalizations from field recordings
**Researched:** 2026-04-11
**Confidence:** MEDIUM — bioacoustic tool landscape confirmed via research literature and tool documentation; hackathon judge priorities inferred from general hackathon judging criteria sources

---

## Feature Landscape

### Table Stakes (Judges Expect These)

Features that any serious audio denoising tool has. Missing these makes the project look unfinished or like a script, not a product.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Before/after spectrogram visualization | Spectrograms are the universal language of bioacoustics; every researcher uses them (Raven Pro, Audacity, MATLAB). Without visual proof of denoising, judges cannot evaluate the result. | MEDIUM | Use matplotlib with n_fft=8192; overlay harmonic comb mask as third layer for differentiation. Librosa `display.specshow` is the fastest path. |
| Audio playback with A/B toggle | Judges need to hear the difference. Cannot evaluate denoising quality by looking only. A/B toggle is standard in any audio tool. | LOW | Simple HTML5 audio element pair with React toggle. Output WAVs already exist from pipeline. |
| Batch processing of all annotated calls | 212 calls across 44 recordings — processing one at a time is not a research tool, it is a toy. Batch is the baseline expectation for a research pipeline. | MEDIUM | Already scoped in PROJECT.md. Pandas DataFrame iterating over timestamp CSV, outputting one WAV per call. |
| WAV export compatible with Raven Pro | ElephantVoices researchers use Raven Pro (Cornell Lab of Ornithology) as their primary analysis tool. If cleaned files cannot be loaded into Raven Pro, the output has zero practical value. Raven Pro reads standard PCM WAV. | LOW | Use scipy.io.wavfile or soundfile to write standard 16-bit or 32-bit PCM WAV at original sample rate. No special metadata needed. |
| Noise type classification per recording | Generator vs. car vs. plane noise require different denoising strategies (stationary tonal vs. transient vs. slow-sweep). Showing awareness of noise type signals domain expertise to judges. | MEDIUM | Heuristic classifier: measure spectral stationarity (generators = flat over time), detect transients (cars), measure frequency sweep rate (planes). Can be rule-based without ML. |
| Basic confidence or quality score per call | Every research pipeline that batch-processes calls needs a signal quality indicator so researchers can prioritize which cleaned calls to trust. Without it, 212 WAVs are undifferentiated. | MEDIUM | SNR before/after, harmonic-to-noise ratio (HNR), or f0 detection confidence from subharmonic summation. Output as 0-100 normalized score. |

### Differentiators (Competitive Advantage at Hackathon)

Features that separate this project from "team that applied a generic denoiser" — which is what most hackathon competitors will do.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Harmonic comb masking with f0 detection | The core technical moat. Generic tools (LALAL.AI, noisereduce default) apply uniform noise models. This system detects elephant f0 via subharmonic summation (2nd harmonic stronger than fundamental) and builds a time-varying comb mask at integer multiples. Engine noise at 30/60Hz is killed while elephant harmonics at those same frequencies survive because they are tracked, not just attenuated. | HIGH | The algorithm itself is the differentiator. Implement first, everything else is demo scaffolding. |
| Spectrogram overlay with harmonic comb mask | Visual proof of the algorithm — shows judges exactly which frequencies were protected vs. attenuated. No generic denoiser can show this because they do not have a harmonic model. The three-panel view (noisy / mask / cleaned) is the single most powerful demo slide. | MEDIUM | Render mask as semi-transparent overlay on spectrogram using matplotlib. Save as PNG for web display alongside audio player. |
| Side-by-side LALAL.AI comparison | Demonstrates domain-specific advantage with concrete evidence. LALAL.AI is trained on speech/music at human-audible frequencies — it will mangle infrasonic content or leave it untouched. Showing the failure mode of the generic tool next to your approach is a compelling narrative for judges. | LOW | Pre-process a representative sample through LALAL.AI manually before the hackathon or during early hours. Store both outputs, render both spectrograms side-by-side. |
| Dashboard with sortable confidence scores | Turns a batch pipeline into a research instrument. Researchers can filter by noise type, sort by confidence, identify problematic recordings. Signals that the tool was built for real users (ElephantVoices researchers) not just demo purposes. | MEDIUM | React table with sort/filter on the 212-call result set. Columns: call ID, recording, noise type, confidence score, SNR delta. Click row to open audio player + spectrograms. |
| n_fft=8192 infrasonic resolution | Most hackathon teams using librosa will use default n_fft=2048 or 1024 — producing ~43Hz frequency resolution at 44.1kHz sample rate, which is garbage for 10-20Hz elephant fundamentals. n_fft=8192 gives ~5Hz resolution, the minimum needed to distinguish elephant f0 from engine harmonics. State this explicitly in the pitch. | LOW | One parameter change. Zero implementation complexity. High talking-point value. |

### Anti-Features (Do NOT Build in 24 Hours)

Features that seem impressive but will consume time without proportional judge impact, or that introduce scope risk.

| Feature | Why Requested | Why Problematic for Hackathon | What to Do Instead |
|---------|---------------|-------------------------------|-------------------|
| Multi-speaker / multi-elephant call separation | 58% of elephant recordings contain concurrent signalers (from research literature). Seems like an obvious extension. | Requires a trained neural source separation model (BioCPPNet, SepFormer) or at minimum blind source separation with ICA. No labeled training data exists for 24-hour training. Rule-based approaches do not work when callers are in the same frequency band. This is a PhD-level problem that will eat the entire hackathon. | Mark as "stretch goal" in the pitch. Show awareness of the problem. The confidence score dashboard already differentiates calls where overlapping is detected (low confidence score). |
| Real-time streaming denoising | Sounds impressive. Judges may ask about it. | Adds WebSocket infrastructure, real-time buffering constraints, and latency management. The project's value is batch processing annotated field recordings — real-time is a different use case entirely. | Demo is file upload → process → results. Explain the research-workflow use case explicitly so judges understand why batch is correct here. |
| ML model training (U-Net, GAN, denoising autoencoder) | Deep learning denoising is the current SOTA in the literature (2025 research confirms: GANs, U-Net, BioCPPNet all outperform classical methods on sufficient data). | 44 recordings is insufficient training data. Training would take longer than 24 hours even with a pretrained checkpoint as starting point. Models trained on speech (Biodenoising, DeepFilterNet) hurt infrasonic content. | The explicit anti-ML stance is a feature of this project's pitch: "We don't need a model because we exploit mathematical structure." Use this as differentiation, not a limitation to hide. |
| Cloud deployment / multi-tenancy | Judges might expect a live URL. | Unnecessary infrastructure complexity. This is a research pipeline tool for a small team of elephant researchers, not a SaaS product. | localhost demo with FastAPI + React. If judges want a live link, Ngrok tunneling is 5 minutes. Don't architect for scale that doesn't exist. |
| User authentication / file management | Web apps typically have these. | Zero research value and consumes frontend time that should go to the spectrogram visualization and dashboard. | Drop files in, get results back. Stateless API. Researchers will not be creating accounts. |
| FLAC, MP3, or exotic format support | Seems like robustness. | The 44 field recordings are already WAV. Adding format conversion introduces edge cases during a 24-hour window. | Accept WAV only. State this as a constraint. Raven Pro exports WAV. |

---

## Feature Dependencies

```
[f0 detection via subharmonic summation]
    └──required by──> [harmonic comb mask construction]
                          └──required by──> [comb mask spectrogram overlay]
                          └──required by──> [per-call confidence score (harmonic tracking confidence)]

[timestamp CSV parsing + call segmentation]
    └──required by──> [batch processing pipeline]
                          └──required by──> [confidence score dashboard]
                          └──required by──> [WAV export per call]

[batch pipeline output (cleaned WAVs + scores)]
    └──required by──> [audio A/B toggle in UI]
    └──required by──> [dashboard with sortable scores]
    └──required by──> [before/after spectrogram visualization]

[noise type classification]
    └──enhances──> [denoising strategy selection]
    └──enhances──> [dashboard (filterable by noise type)]

[LALAL.AI comparison samples]
    └──independent──> [must be pre-generated before or early in hackathon]
    └──feeds into──> [side-by-side spectrogram comparison panel]

[multi-elephant separation]
    └──conflicts with──> [24-hour timeline] (skip entirely)
```

### Dependency Notes

- **f0 detection is the critical path bottleneck.** Everything unique to this project (comb masking, mask overlay, per-call confidence) depends on reliable f0 detection. Subharmonic summation from the 2nd harmonic must be validated on at least 5-10 test calls before building the rest.
- **Batch pipeline must complete before UI work.** React frontend is blocked on having actual output files. Pipeline parallelism is essential — two team members can work on backend pipeline while one builds React scaffolding with mock data.
- **LALAL.AI comparison is time-sensitive.** Must be generated before or very early in the hackathon since it requires the online tool. Cannot be done last-minute.
- **Confidence score dashboard is low priority.** It enhances the research-tool narrative but is not blocking the core demo. Build last.

---

## MVP Definition

### Launch With (hackathon demo)

Minimum viable for a compelling judge presentation.

- [ ] Harmonic comb masking pipeline processing at least one representative call end-to-end — this is the whole project, nothing else matters without it
- [ ] Before/after spectrogram with comb mask overlay as a static image or web panel — the visual proof
- [ ] Audio A/B toggle in the React UI — the auditory proof
- [ ] Batch processing of all 212 calls producing cleaned WAVs — demonstrates scale
- [ ] Per-call confidence score (even a simple SNR delta is sufficient) — demonstrates research utility
- [ ] WAV export in Raven Pro-compatible format — demonstrates real-world deployment

### Add After Core is Working

Features that strengthen the pitch if time allows.

- [ ] LALAL.AI side-by-side comparison — adds competitive differentiation narrative; generate samples early so this is ready to drop in
- [ ] Noise type classifier per recording — adds domain sophistication; implement as heuristic rule-set, not ML
- [ ] Dashboard with sortable/filterable confidence scores — turns pipeline output into a research instrument

### Defer / Do Not Build

- [ ] Multi-elephant source separation — PhD-level problem, no training data, skip entirely
- [ ] Real-time streaming — wrong use case for this project
- [ ] ML model training — anti-pattern for this project's pitch

---

## Feature Prioritization Matrix

| Feature | Judge Value | Implementation Cost | Priority |
|---------|-------------|---------------------|----------|
| Harmonic comb masking (core algorithm) | HIGH | HIGH | P1 — build first, validate on test calls |
| Before/after spectrogram + mask overlay | HIGH | MEDIUM | P1 — primary visual demo artifact |
| Audio A/B toggle | HIGH | LOW | P1 — judges must hear the difference |
| Batch processing all 212 calls | HIGH | MEDIUM | P1 — demonstrates scale and real utility |
| WAV export (Raven Pro compatible) | HIGH | LOW | P1 — table stakes for researchers |
| Per-call confidence score | MEDIUM | MEDIUM | P2 — research credibility signal |
| Noise type classification | MEDIUM | MEDIUM | P2 — domain sophistication |
| LALAL.AI comparison | HIGH | LOW | P2 — pre-generate early; high return for effort |
| Dashboard with sortable scores | MEDIUM | MEDIUM | P2 — nice-to-have if time allows |
| Multi-elephant separation | LOW (for 24hrs) | VERY HIGH | P3 — mention as future work only |
| n_fft=8192 (talking point) | MEDIUM | LOW | P1 — one parameter, cite explicitly in pitch |

**Priority key:**
- P1: Must have for demo — build in first 12 hours
- P2: Should have — build in hours 12-20
- P3: Future work — mention in pitch as roadmap

---

## Competitor Feature Analysis

| Feature | Generic tools (LALAL.AI, media.io) | noisereduce (spectral gating) | This project |
|---------|-----------------------------------|-------------------------------|--------------|
| Infrasonic frequency resolution | Fails — trained on 20Hz+ speech/music | Works but uniform model — no harmonic awareness | n_fft=8192 gives ~5Hz resolution, tracks elephant harmonics specifically |
| Harmonic structure exploitation | None — frequency-agnostic separation | None — stationary/non-stationary noise profiles only | Comb mask at integer multiples of detected f0 |
| Domain-specific f0 detection | None | None | Subharmonic summation exploiting 2nd harmonic dominance in elephants |
| Raven Pro output | No — proprietary formats or web-only | Possible if scripted | Yes — explicit WAV export requirement |
| Batch processing of annotated calls | No — manual upload per file | Yes — scriptable | Yes — timestamp CSV drives automatic segmentation |
| Visual confidence per call | No | No | Yes — SNR delta + harmonic tracking confidence |
| Works without training data | Yes (pre-trained) | Yes | Yes — domain priors replace training data |

---

## Sources

- [noisereduce GitHub — domain-general spectral gating for bioacoustics](https://github.com/timsainb/noisereduce)
- [Noisereduce Scientific Reports paper 2025](https://www.nature.com/articles/s41598-025-13108-x) — confirms bioacoustics as primary use domain
- [BioCPPNet — bioacoustic source separation complexity](https://www.nature.com/articles/s41598-021-02790-2) — 58% of elephant recordings have concurrent signalers; neural model required for separation
- [Raven Pro feature set — Cornell Lab of Ornithology](https://www.ravensoundsoftware.com/software/raven-pro/) — WAV/AIF/FLAC input; spectrogram/waveform views; standard for field researchers
- [Biodenoising ICASSP 2025 — Earth Species Project](https://www.earthspecies.org/blog/biodenoising--a-novel-method-for-noise-reduction-in-animal-vocalizations) — current SOTA for generic animal denoising; not infrasonic-aware
- [Elephant Sound Classification 2025 — MDPI Sensors](https://www.mdpi.com/1424-8220/25/2/352) — ElephantCallerNet, researcher tool landscape
- [Computational bioacoustics roadmap — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8944344/) — standard analysis pipeline features
- [Hackathon judging criteria — Devpost](https://info.devpost.com/blog/hackathon-judging-tips) — impact, technical implementation, creativity as primary axes
- [Raven Pro spectrograms for publication — Cornell](https://www.ravensoundsoftware.com/knowledge-base/spectrograms-for-presentation-and-publication/) — spectrogram is the standard research communication medium

---

*Feature research for: elephant bioacoustic denoising (hackathon)*
*Researched: 2026-04-11*
