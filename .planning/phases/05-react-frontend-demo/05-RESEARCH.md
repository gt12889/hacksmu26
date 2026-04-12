# Phase 5: React Frontend & Demo - Research

**Researched:** 2026-04-12
**Domain:** React 18 + Vite + wavesurfer.js 7 + FastAPI REST integration
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Before/after spectrogram display with harmonic comb mask overlay in distinct color | wavesurfer.js SpectrogramPlugin renders spectrogram; comb mask overlay rendered on absolute-positioned `<canvas>` at z-index 5+ above plugin canvas (z-index 4) |
| UI-02 | Audio playback with A/B toggle between noisy and cleaned at same timestamp | Two WavesurferPlayer instances, one visible at a time; `wavesurfer.setTime(t)` synchronizes position; A/B toggle swaps which instance is active |
| UI-03 | Side-by-side comparison panel: Original / LALAL.AI / Our result with SNR metrics | Three columns rendered from result dict; SNR fields `snr_before_db`, `snr_after_db` available directly from `/api/result/{job_id}`; LALAL.AI column is a static placeholder or manual upload |
| UI-04 | Confidence dashboard with sortable/filterable table of all processed calls | Client-side sort/filter on result array from `/api/result/{job_id}`; columns: filename, f0_median_hz, snr_before_db, snr_after_db, confidence, noise_type |
| UI-05 | Click any row in dashboard to view spectrogram and play audio | Row click sets `selectedCall` state; detail panel renders WavesurferPlayer + spectrogram overlay for that call index |
</phase_requirements>

---

## Summary

The Phase 4 backend already exposes all data needed: `/api/result/{job_id}` returns per-call dicts with `filename`, `f0_median_hz`, `snr_before_db`, `snr_after_db`, `confidence`, `noise_type`, `clean_wav_path`, and `status`. Audio is served via `/api/result/{job_id}/audio/{call_index}` as a `FileResponse`. The spectrogram endpoint (`/api/result/{job_id}/spectrogram/{call_index}`) returns 404 — the backend does not generate PNG files.

For the spectrogram visual, the simplest hackathon-viable approach is: use the wavesurfer.js SpectrogramPlugin for client-side FFT rendering, then draw the harmonic comb mask as colored horizontal bands on a separate `<canvas>` element positioned absolutely over the plugin's canvas (z-index 5). The comb mask data comes from the backend as a lightweight JSON endpoint (new endpoint needed: `/api/result/{job_id}/mask/{call_index}`) that serializes `f0_median_hz` — the frontend can recompute band positions from f0 arithmetic rather than shipping the full 4097×n_frames mask array.

The UI architecture is: upload form → poll status → result loads into two views: (a) ConfidenceTable (sortable table of all calls), (b) CallDetail (spectrogram + A/B player) rendered when a row is clicked.

**Primary recommendation:** Use wavesurfer.js SpectrogramPlugin for audio visualization, overlay harmonic bands from f0 arithmetic on a Canvas, and render the confidence table with client-side sort/filter. No extra libraries needed — the locked stack (React 18, Vite, wavesurfer.js 7.x, axios) covers everything.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | 19.2.5 (current npm latest) | Component model, state, effects | Locked decision |
| vite | 8.0.8 (current) | Dev server + build, HMR | Locked decision |
| typescript | >=5.0 | Type safety | Locked decision |
| wavesurfer.js | 7.12.6 (current) | Waveform + spectrogram + playback | Locked decision — only library with both spectrogram plugin and React wrapper |
| @wavesurfer/react | 1.0.12 (current) | React wrapper: `WavesurferPlayer` component + `useWavesurfer` hook | Official package from same author |
| axios | latest | Multipart file upload + JSON API calls | Locked decision |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none) | — | No additional UI library needed | Plain CSS / inline styles sufficient for hackathon |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| wavesurfer.js SpectrogramPlugin | Custom Canvas + Web Audio API AnalyserNode | More accurate FFT params, but 4-6 hours build time vs 30 minutes |
| wavesurfer.js SpectrogramPlugin | Backend-generated PNG served as `<img>` | Accurate Python-side FFT but requires backend change + adds Phase 4 scope creep |
| Harmonic bands from f0 arithmetic | Full mask array via JSON | Full mask is ~4097 × n_frames floats (~several MB per call); f0 arithmetic is 10 lines of JS and < 1KB |
| Client-side sort/filter | React-Table / TanStack Table | Adds dependency; native Array.sort() is sufficient for ≤212 rows |

**Installation:**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install wavesurfer.js @wavesurfer/react axios
```

---

## Architecture Patterns

### Recommended Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts          # typed axios wrappers for all FastAPI endpoints
│   ├── components/
│   │   ├── UploadPanel.tsx     # file input + POST /api/upload + POST /api/process
│   │   ├── StatusPoller.tsx    # polls GET /api/status/{job_id} every 2s
│   │   ├── ConfidenceTable.tsx # sortable/filterable table of all results (UI-04)
│   │   ├── CallDetail.tsx      # spectrogram + A/B player for selected call (UI-05)
│   │   ├── SpectrogramView.tsx # WavesurferPlayer + SpectrogramPlugin + comb overlay (UI-01)
│   │   └── ABPlayer.tsx        # A/B toggle between noisy and clean WAV (UI-02)
│   ├── hooks/
│   │   └── useJobStatus.ts     # setInterval poll, returns {status, progress, total}
│   ├── types/
│   │   └── api.ts              # TypeScript interfaces for all API response shapes
│   ├── App.tsx                 # top-level: upload → poll → results
│   └── main.tsx
├── vite.config.ts              # proxy /api/* to http://localhost:8000
└── package.json
```

### Pattern 1: Vite API Proxy (Critical)

**What:** Configure Vite dev server to proxy `/api/*` to `http://localhost:8000` so React fetches work without CORS issues during development.

**When to use:** Always — without this, every fetch to the FastAPI backend triggers a preflight. The backend has CORS `allow_origins=["*"]` but proxying is cleaner and avoids port conflicts.

**Example:**
```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

### Pattern 2: WavesurferPlayer with SpectrogramPlugin

**What:** Mount the SpectrogramPlugin via the `plugins` prop (memoized). Capture the wavesurfer instance via `onReady` callback. Control playback externally via `wavesurfer.playPause()` and `wavesurfer.setTime(t)`.

**Critical:** The `plugins` array MUST be memoized with `useMemo`. Recreating the array on every render re-initializes wavesurfer, causing infinite loops and flickering.

**Example:**
```typescript
// Source: @wavesurfer/react docs + github.com/katspaugh/wavesurfer-react
import { useMemo, useState, useRef } from 'react'
import { WavesurferPlayer } from '@wavesurfer/react'
import Spectrogram from 'wavesurfer.js/dist/plugins/spectrogram.esm.js'

function SpectrogramView({ audioUrl }: { audioUrl: string }) {
  const [ws, setWs] = useState<WaveSurfer | null>(null)

  const plugins = useMemo(() => [
    Spectrogram.create({
      labels: true,
      height: 200,
      fftSamples: 512,        // power of 2; 512 is fast enough for demo
      frequencyMax: 2000,     // show 0-2000 Hz; elephant harmonics top out ~1000 Hz
      colorMap: 'roseus',     // built-in preset; or pass array of [r,g,b,a] rows
    })
  ], [])

  return (
    <WavesurferPlayer
      height={80}
      waveColor="#4F4A85"
      url={audioUrl}
      plugins={plugins}
      onReady={(wavesurfer) => setWs(wavesurfer)}
    />
  )
}
```

### Pattern 3: Comb Mask Overlay Canvas

**What:** Draw horizontal frequency bands on a `<canvas>` absolutely positioned over the SpectrogramPlugin canvas. Band positions are computed from `f0_median_hz` arithmetic (f0, 2f0, 3f0, …, up to 1000 Hz).

**Why arithmetic not full mask array:** The comb mask in the backend is shape `(4097, n_frames)` — serializing it as JSON would be ~10-30 MB per call. Instead, since the mask is deterministic from f0, recompute band positions client-side: center_hz = k * f0, y_position = (center_hz / frequencyMax) * canvasHeight.

**Canvas z-index:** The SpectrogramPlugin renders at z-index 4 inside its wrapper. Overlay canvas needs z-index 5 with `pointer-events: none` so wavesurfer click/drag still works.

**Example:**
```typescript
// Overlay canvas rendering
function drawCombOverlay(
  canvas: HTMLCanvasElement,
  f0Hz: number,
  frequencyMax: number = 2000,
  bandwidthHz: number = 5,
) {
  const ctx = canvas.getContext('2d')!
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = 'rgba(255, 80, 0, 0.4)'  // distinct orange-red

  for (let k = 1; k * f0Hz <= frequencyMax; k++) {
    const centerHz = k * f0Hz
    const centerY = canvas.height - (centerHz / frequencyMax) * canvas.height
    const bandHalfPx = (bandwidthHz / frequencyMax) * canvas.height

    ctx.fillRect(0, centerY - bandHalfPx, canvas.width, bandHalfPx * 2)
  }
}
```

### Pattern 4: A/B Toggle with Timestamp Sync

**What:** Render two WavesurferPlayer instances, one per audio URL (noisy original vs. clean). On toggle, pause the active one, record `wavesurfer.getCurrentTime()`, load the other, and call `wavesurfer.setTime(t)` in its `onReady` callback.

**Constraint:** The "noisy original" audio needs to be served by the backend. The upload endpoint saves the original file at `data/uploads/{file_id}_{filename}`. A new endpoint `/api/result/{job_id}/original` (or reuse the file_id from the job registry) is needed to serve the noisy WAV. Alternatively, the frontend can store the uploaded file in memory via `URL.createObjectURL(file)` and pass that as the noisy URL.

**Simplest approach for hackathon:** Use `URL.createObjectURL(uploadedFile)` for the noisy audio (browser-native, no backend change needed). Use `/api/result/{job_id}/audio/0` for the cleaned audio.

**Example:**
```typescript
const [mode, setMode] = useState<'noisy' | 'clean'>('noisy')
const [timestamp, setTimestamp] = useState(0)
const activeUrl = mode === 'noisy' ? noisyObjectUrl : cleanAudioUrl

// On toggle button click:
function handleToggle() {
  if (ws) setTimestamp(ws.getCurrentTime())
  setMode(m => m === 'noisy' ? 'clean' : 'noisy')
}

// In WavesurferPlayer:
<WavesurferPlayer
  url={activeUrl}
  onReady={(wavesurfer) => {
    wavesurfer.setTime(timestamp)
  }}
/>
```

### Pattern 5: Status Polling Hook

**What:** `useJobStatus` hook runs `setInterval` at 2000ms, calls `GET /api/status/{job_id}`, stops when status is `"complete"` or `"failed"`.

**Example:**
```typescript
// hooks/useJobStatus.ts
export function useJobStatus(jobId: string | null) {
  const [status, setStatus] = useState<StatusResponse | null>(null)

  useEffect(() => {
    if (!jobId) return
    const id = setInterval(async () => {
      const res = await axios.get<StatusResponse>(`/api/status/${jobId}`)
      setStatus(res.data)
      if (res.data.status === 'complete' || res.data.status === 'failed') {
        clearInterval(id)
      }
    }, 2000)
    return () => clearInterval(id)
  }, [jobId])

  return status
}
```

### Pattern 6: TypeScript Types for API Responses

**What:** Define interfaces matching the actual FastAPI Pydantic models and result dicts.

**Example:**
```typescript
// types/api.ts
export interface UploadResponse {
  file_id: string
  filename: string
  path: string
}

export interface ProcessResponse {
  job_id: string
}

export interface StatusResponse {
  job_id: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  progress: number
  total: number
  eta_seconds?: number
}

export interface CallResult {
  filename: string
  start: number
  end: number
  f0_median_hz: number
  snr_before_db: number
  snr_after_db: number
  confidence: number    // 0-100 float
  noise_type: string    // 'generator' | 'car' | 'plane' | 'mixed' | 'unknown'
  status: 'ok' | 'skipped'
  clean_wav_path: string
}

export interface ResultResponse {
  job_id: string
  results: CallResult[]
}

export interface BatchSummaryResponse {
  total_jobs: number
  total_calls_processed: number
  average_confidence: number | null
  average_snr_improvement_db: number | null
}
```

### Anti-Patterns to Avoid

- **Plugins array not memoized:** Creating `[Spectrogram.create(...)]` inline in JSX triggers wavesurfer re-init on every render. Always wrap with `useMemo`.
- **Injecting CSS into wavesurfer's Shadow DOM:** wavesurfer 7 uses Shadow DOM. Global CSS selectors cannot reach internal elements. Use the `container` prop to target the outer wrapper only.
- **Serving large mask arrays:** Do not serialize the full `(4097, n_frames)` numpy mask to JSON. Recompute band positions from `f0_median_hz` arithmetic in JS.
- **Polling without cleanup:** `setInterval` in `useEffect` without a cleanup `return () => clearInterval(id)` leaks on unmount or job_id change.
- **Missing Vite proxy:** Without proxy config, requests to `/api/*` hit the Vite dev server (port 5173), not FastAPI (port 8000). CORS will fail on preflight even with `allow_origins=["*"]` in some browsers.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Spectrogram rendering | Custom WebAudio AnalyserNode + Canvas draw loop | `Spectrogram.create()` from wavesurfer.js | Already handles FFT, colormap, resize, time sync — 30 minutes vs 4 hours |
| Audio waveform | Raw `<canvas>` with decoded PCM drawing | `WavesurferPlayer` waveColor prop | Free with wavesurfer |
| Audio playback control | HTML5 `<audio>` element with custom UI | wavesurfer `playPause()` / `setTime()` | Already integrated with waveform visual |
| HTTP upload with progress | Raw `fetch` with `ReadableStream` | `axios` with `onUploadProgress` | Built-in progress callback |
| Table sort | Custom comparator + DOM sort | `Array.sort()` + React state | 212 rows — no performance concern, native is fine |

**Key insight:** The hardest part of this phase is the comb mask overlay — everything else is wiring. Spend complexity budget there.

---

## Critical Backend Gap: No Noisy Audio Endpoint

The backend stores the uploaded noisy WAV at `data/uploads/{file_id}_{filename}` but has no endpoint to serve it back. For UI-02 (A/B toggle), the frontend needs both noisy and clean audio from the same timestamp.

**Options (in order of implementation cost):**

1. **Cheapest (no backend change):** Store the uploaded `File` object in React state via `URL.createObjectURL(file)`. The blob URL works for the life of the page session. No backend change needed.

2. **Clean (minor backend change):** Add `GET /api/upload/{file_id}/audio` to serve the original WAV from `UPLOAD_REGISTRY`. ~10 lines of FastAPI code.

**Recommendation for hackathon:** Use option 1 (blob URL). Avoids Phase 4 scope creep.

---

## Critical Backend Gap: No Original Audio for Pre-Processed Demo Calls

UI-03 requires showing "Original | LALAL.AI | Our result" for the 212 pre-processed calls from `data/segments/`. These segments are not uploaded through the API — they exist on disk from Phase 1 batch processing.

**Options:**

1. **Batch-mode demo:** Add `GET /api/batch/calls` endpoint that reads `data/outputs/` directory and returns the full result list from disk (not from JOB_REGISTRY). This makes the pre-existing 212-call run browsable without re-uploading.

2. **Upload-mode only:** Phase 5 only demonstrates single-file upload flow. The 212-call results are shown via a static summary screen.

**Recommendation:** Implement option 1 — it dramatically improves demo impact (showing 212 processed calls vs. 1). The endpoint is read-only and ~20 lines.

---

## Common Pitfalls

### Pitfall 1: wavesurfer SpectrogramPlugin fftSamples vs n_fft=8192 Mismatch

**What goes wrong:** wavesurfer.js SpectrogramPlugin default `fftSamples=512` gives ~86 Hz frequency resolution at 44100 Hz. Elephant harmonics start at ~8-20 Hz. The spectrogram looks flat/blank in the infrasonic range.

**Why it happens:** The plugin's built-in Web Audio API FFT cannot match Python's n_fft=8192 resolution easily. Even setting `fftSamples=8192` in the plugin would require large `noverlap` and would be very slow in-browser.

**How to avoid:** Set `frequencyMax: 1000` (or even 500) in the SpectrogramPlugin to zoom into the frequency range where elephant calls actually appear. The harmonics from f0=15 Hz up to ~15×15=225 Hz will be visible at any fftSamples. The plugin does not need to show above 1000 Hz to demonstrate the algorithm.

**Warning signs:** All-dark or all-flat spectrogram at low frequencies is a sign you're looking at the wrong frequency range.

### Pitfall 2: WavesurferPlayer Plugins Array Recreated on Render

**What goes wrong:** SpectrogramPlugin re-initializes, causing audio to reset, canvas to flicker, and React to enter re-render loop.

**Why it happens:** `plugins={[Spectrogram.create({...})]}` creates a new array every render. wavesurfer detects a different plugin array and re-initializes.

**How to avoid:** Always `useMemo(() => [Spectrogram.create({...})], [])`.

**Warning signs:** Spectrogram flickers, `onReady` fires repeatedly, console errors about plugin re-registration.

### Pitfall 3: A/B Toggle Loses Playback Position

**What goes wrong:** User is at 3.5s in noisy audio, toggles to clean, clean starts at 0s.

**Why it happens:** `url` prop change triggers wavesurfer reload. `onReady` fires after decode, which is async. If `setTime` is called before decode completes, it has no effect.

**How to avoid:** Capture timestamp in the toggle handler _before_ changing URL. Pass it as a prop to the new instance and call `setTime` inside `onReady`, not in a `useEffect` that may fire before ready.

### Pitfall 4: CORS Errors in Development

**What goes wrong:** `POST http://localhost:8000/api/upload` fails with CORS preflight error even though backend has `allow_origins=["*"]`.

**Why it happens:** Browser sends OPTIONS preflight for multipart form upload. Some browser versions reject wildcard origins for credentialed requests.

**How to avoid:** Use Vite proxy (`server.proxy`) so all `/api/*` requests go through the same origin (localhost:5173). The proxy strips the CORS issue entirely.

### Pitfall 5: axios multipart upload requires explicit Content-Type

**What goes wrong:** `axios.post('/api/upload', formData)` fails with 422 Unprocessable Entity.

**Why it happens:** Need to let axios set Content-Type with correct boundary. Setting `Content-Type: multipart/form-data` manually breaks the boundary string.

**How to avoid:** Do NOT set `Content-Type` manually. Pass `FormData` directly and let axios set the header.

```typescript
const formData = new FormData()
formData.append('file', file)
await axios.post('/api/upload', formData)  // no Content-Type header needed
```

---

## Code Examples

### Full Upload → Poll → Results Flow

```typescript
// api/client.ts
import axios from 'axios'
import type { UploadResponse, ProcessResponse, StatusResponse, ResultResponse } from '../types/api'

export async function uploadFile(file: File): Promise<UploadResponse> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await axios.post<UploadResponse>('/api/upload', fd)
  return res.data
}

export async function startProcessing(fileId: string): Promise<ProcessResponse> {
  const res = await axios.post<ProcessResponse>(`/api/process?file_id=${fileId}`)
  return res.data
}

export async function getStatus(jobId: string): Promise<StatusResponse> {
  const res = await axios.get<StatusResponse>(`/api/status/${jobId}`)
  return res.data
}

export async function getResult(jobId: string): Promise<ResultResponse> {
  const res = await axios.get<ResultResponse>(`/api/result/${jobId}`)
  return res.data
}

export function audioUrl(jobId: string, callIndex: number): string {
  return `/api/result/${jobId}/audio/${callIndex}`
}
```

### ConfidenceTable with Client-Side Sort

```typescript
// components/ConfidenceTable.tsx
import { useState } from 'react'
import type { CallResult } from '../types/api'

type SortKey = keyof Pick<CallResult, 'confidence' | 'snr_before_db' | 'snr_after_db' | 'f0_median_hz' | 'noise_type'>

interface Props {
  results: CallResult[]
  onSelect: (index: number, result: CallResult) => void
}

export function ConfidenceTable({ results, onSelect }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('confidence')
  const [sortDesc, setSortDesc] = useState(true)
  const [filterText, setFilterText] = useState('')

  const filtered = results
    .filter(r => r.filename.toLowerCase().includes(filterText.toLowerCase()) ||
                 r.noise_type.includes(filterText.toLowerCase()))

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey] as number | string
    const bv = b[sortKey] as number | string
    if (typeof av === 'number' && typeof bv === 'number') {
      return sortDesc ? bv - av : av - bv
    }
    return sortDesc
      ? String(bv).localeCompare(String(av))
      : String(av).localeCompare(String(bv))
  })

  const handleColClick = (key: SortKey) => {
    if (sortKey === key) setSortDesc(d => !d)
    else { setSortKey(key); setSortDesc(true) }
  }

  return (
    <div>
      <input
        placeholder="Filter by filename or noise type"
        value={filterText}
        onChange={e => setFilterText(e.target.value)}
      />
      <table>
        <thead>
          <tr>
            <th onClick={() => handleColClick('confidence')}>Confidence %</th>
            <th onClick={() => handleColClick('f0_median_hz')}>f0 (Hz)</th>
            <th onClick={() => handleColClick('snr_before_db')}>SNR Before (dB)</th>
            <th onClick={() => handleColClick('snr_after_db')}>SNR After (dB)</th>
            <th onClick={() => handleColClick('noise_type')}>Noise Type</th>
            <th>Filename</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={i} onClick={() => onSelect(filtered.indexOf(r), r)} style={{ cursor: 'pointer' }}>
              <td>{r.confidence.toFixed(1)}</td>
              <td>{r.f0_median_hz.toFixed(1)}</td>
              <td>{r.snr_before_db.toFixed(1)}</td>
              <td>{r.snr_after_db.toFixed(1)}</td>
              <td>{r.noise_type}</td>
              <td>{r.filename}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

### Comb Mask Canvas Overlay Component

```typescript
// Inside SpectrogramView.tsx — overlay canvas renders after WavesurferPlayer mounts
import { useEffect, useRef } from 'react'

function CombOverlay({
  f0Hz,
  frequencyMax = 1000,
  bandwidthHz = 5,
  width,
  height,
}: {
  f0Hz: number
  frequencyMax?: number
  bandwidthHz?: number
  width: number
  height: number
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || f0Hz <= 0) return
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, width, height)
    ctx.fillStyle = 'rgba(255, 100, 0, 0.35)'

    for (let k = 1; k * f0Hz <= frequencyMax; k++) {
      const centerHz = k * f0Hz
      // Y=0 is top (high freq in canvas), invert for spectrogram convention
      const centerY = height - (centerHz / frequencyMax) * height
      const halfPx = Math.max(1, (bandwidthHz / frequencyMax) * height)
      ctx.fillRect(0, centerY - halfPx, width, halfPx * 2)
    }
  }, [f0Hz, frequencyMax, bandwidthHz, width, height])

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        pointerEvents: 'none',
        zIndex: 5,    // above SpectrogramPlugin canvas (z-index 4)
      }}
    />
  )
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| wavesurfer.js v6 global CSS | v7 Shadow DOM isolation | 2023 | Cannot inject CSS globally; use `::part()` or inline styles on wrapper only |
| WaveSurfer.create() in React useEffect | `WavesurferPlayer` component from @wavesurfer/react | v7.x | Handles cleanup and re-init lifecycle automatically |
| `plugins` passed at WaveSurfer.create time | `plugins` prop on WavesurferPlayer (memoized) | v7.x | Must memoize; dynamic plugin changes trigger re-init |
| `frequenciesDataUrl` expects URL to JSON Uint8Array[][] | Same, but format must be precise | v7.x | Not useful for our Python data without custom serialization |

**Deprecated/outdated:**
- wavesurfer.js v6 API (`.load()`, `.backend` etc.): completely replaced in v7. Any tutorial from before 2023 uses the old API.
- `WaveSurfer.create()` inside React `useEffect`: still works but leak-prone. Use `@wavesurfer/react` instead.

---

## Open Questions

1. **noisy audio serving for A/B toggle**
   - What we know: backend does not expose the original upload at a stable URL; `UPLOAD_REGISTRY` maps file_id → disk path
   - What's unclear: whether blob URL (`URL.createObjectURL`) is acceptable for demo or a backend endpoint is needed
   - Recommendation: Use blob URL approach for hackathon; add backend endpoint only if blob URL causes issues (e.g., page refresh loses the file)

2. **212-call batch results browsability**
   - What we know: batch results from Phase 3/4 exist on disk at `data/outputs/` but are not in JOB_REGISTRY
   - What's unclear: whether Phase 5 should browse pre-existing batch results or only show freshly uploaded single-file results
   - Recommendation: Add a `GET /api/batch/results` endpoint that reads `data/outputs/` directory and builds the result list from disk. This is the most impactful thing for the demo.

3. **SpectrogramPlugin frequency resolution at infrasonic range**
   - What we know: `fftSamples=512` gives ~86 Hz/bin; even `fftSamples=8192` won't show detail below ~10 Hz due to Web Audio API limitations
   - What's unclear: whether judges will notice the spectrograms look different from the publication-quality Python matplotlib figures
   - Recommendation: Set `frequencyMax=1000` and `fftSamples=1024` to show harmonics up to ~1000 Hz; draw the comb overlay to visually indicate where harmonic content was preserved. The overlay is the main visual story.

---

## Sources

### Primary (HIGH confidence)
- github.com/katspaugh/wavesurfer.js `src/plugins/spectrogram.ts` — SpectrogramPluginOptions interface, canvas z-index (z-index 4), DOM structure, `frequenciesDataUrl` format (Uint8Array[][])
- github.com/katspaugh/wavesurfer-react README — WavesurferPlayer props, `plugins` useMemo requirement, `onReady` instance capture pattern
- npm registry — verified current versions: wavesurfer.js 7.12.6, @wavesurfer/react 1.0.12, react 19.2.5, vite 8.0.8

### Secondary (MEDIUM confidence)
- wavesurfer.xyz/examples/spectrogram.js — SpectrogramPlugin basic usage, `labels: true`, confirmed plugin import path
- FastAPI docs (fastapi.tiangolo.com) — file upload pattern, query param for `file_id` in POST /api/process, FileResponse usage

### Tertiary (LOW confidence)
- wavesurfer.xyz docs site — spectrogram colorMap presets ('gray', 'igray', 'roseus') confirmed by fetched GitHub source, elevated to HIGH

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — npm registry versions verified live
- Architecture: HIGH — based on direct examination of Phase 4 backend code (result dict fields, endpoint behavior, 404 spectrogram)
- wavesurfer.js integration: HIGH — SpectrogramPlugin source code read directly from GitHub
- Pitfalls: HIGH — derived from code analysis (plugin memoization requirement, spectrogram frequency range constraints, backend audio gap)

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (wavesurfer.js 7.x stable; React 19 stable)
