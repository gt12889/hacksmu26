---
phase: 05-react-frontend-demo
plan: 03
subsystem: ui
tags: [react, wavesurfer, spectrogram, canvas, typescript, frontend]

# Dependency graph
requires:
  - phase: 05-react-frontend-demo
    plan: 02
    provides: Vite + React + TypeScript scaffold, types/api.ts, api/client.ts
provides:
  - SpectrogramView: WavesurferPlayer + SpectrogramPlugin with memoized plugins array
  - CombOverlay: absolute-positioned canvas drawing harmonic bands at k*f0Hz (orange-red)
  - ABPlayer: A/B toggle between noisy/clean audio with timestamp-preserving setTime
affects: [05-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "useMemo() plugins array — prevents wavesurfer re-init loop on every render"
    - "WavesurferPlayer is a default export from @wavesurfer/react (not named export)"
    - "CombOverlay draws at position: absolute, zIndex 5, pointerEvents none above plugin canvas (z-index 4)"
    - "ABPlayer captures getCurrentTime() BEFORE URL state change, calls setTime() in onReady"
    - "key={activeUrl} on SpectrogramView forces remount so onReady reliably fires on source swap"

key-files:
  created:
    - frontend/src/components/CombOverlay.tsx
    - frontend/src/components/SpectrogramView.tsx
    - frontend/src/components/ABPlayer.tsx
  modified: []

key-decisions:
  - "WavesurferPlayer default import (not named) — confirmed from @wavesurfer/react module shape"
  - "colorMap string preset (roseus) accepted at runtime without @ts-expect-error — types already allow it"
  - "fftSamples=1024 with frequencyMax=1000 — zooms spectrogram to elephant harmonic range, fast enough in-browser"
  - "WAVE_HEIGHT=80px constant separates waveform strip from spectrogram for overlay top offset"

# Metrics
duration: 2min
completed: 2026-04-12
---

# Phase 5 Plan 03: SpectrogramView + CombOverlay + ABPlayer Components Summary

**Wavesurfer spectrogram view with memoized SpectrogramPlugin, harmonic comb canvas overlay at k*f0Hz, and A/B toggle player with pre-capture timestamp preservation — all three components compile strict-clean and build into production bundle**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-12T04:02:02Z
- **Completed:** 2026-04-12T04:03:55Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- `CombOverlay`: pure canvas component drawing orange-red horizontal bands at k*f0Hz for k=1..floor(1000/f0), y-inverted for spectrogram convention (low freq at bottom), sub-pixel guard, f0<=0 guard, z-index 5 above plugin canvas
- `SpectrogramView`: WavesurferPlayer with memoized SpectrogramPlugin (fftSamples=1024, frequencyMax=1000Hz, colorMap roseus); CombOverlay positioned at top=WAVE_HEIGHT (80px) over spectrogram canvas; measures container width via getWrapper() for accurate overlay sizing
- `ABPlayer`: toggle between noisy/clean URLs with pre-toggle getCurrentTime() + isPlaying() capture; setTime() called in onReady after new audio decodes; key={activeUrl} forces SpectrogramView remount for reliable onReady firing; auto-resumes playback if was playing
- `npm run build` exits 0 — bundle 142.78 kB (wavesurfer.js tree-shaken and included)
- `npm run typecheck` exits 0 — strict TypeScript clean

## Task Commits

Each task was committed atomically:

1. **Task 1: CombOverlay canvas component** - `81d169a` (feat)
2. **Task 2: SpectrogramView with memoized plugins + overlay** - `f465e98` (feat)
3. **Task 3: ABPlayer with timestamp-preserving toggle** - `7cd4462` (feat)

## Files Created/Modified

- `frontend/src/components/CombOverlay.tsx` - Canvas overlay with harmonic bands; exports CombOverlayProps + CombOverlay
- `frontend/src/components/SpectrogramView.tsx` - WavesurferPlayer + memoized SpectrogramPlugin + CombOverlay; exports SpectrogramViewProps + SpectrogramView
- `frontend/src/components/ABPlayer.tsx` - A/B toggle player over SpectrogramView; exports ABPlayerProps + ABPlayer

## Decisions Made

- Used default import for WavesurferPlayer (`import WavesurferPlayer from '@wavesurfer/react'`) — the package exports it as default, not as named export
- Removed @ts-expect-error on colorMap — types already accept string presets like 'roseus'; the directive would cause a TS2578 error
- WAVE_HEIGHT=80 separates the waveform strip from the spectrogram so CombOverlay top offset is correct

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] WavesurferPlayer is default export, not named export**
- **Found during:** Task 2 (SpectrogramView build)
- **Issue:** Plan template used `import { WavesurferPlayer } from '@wavesurfer/react'` but the package exports WavesurferPlayer as default. TypeScript error: `Module '"@wavesurfer/react"' has no exported member 'WavesurferPlayer'`
- **Fix:** Changed to `import WavesurferPlayer from '@wavesurfer/react'`
- **Files modified:** frontend/src/components/SpectrogramView.tsx
- **Commit:** f465e98

**2. [Rule 1 - Bug] Removed unused @ts-expect-error directive**
- **Found during:** Task 2 (SpectrogramView build)
- **Issue:** Plan included `@ts-expect-error` comment before `colorMap: 'roseus'` but wavesurfer.js types already accept string presets. TS2578 error: `Unused '@ts-expect-error' directive`
- **Fix:** Removed the `@ts-expect-error` line
- **Files modified:** frontend/src/components/SpectrogramView.tsx
- **Commit:** f465e98

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs — import style and unused ts-expect-error)
**Impact on plan:** Both fixes were in the same file during the same task; build passed after single correction cycle.

## Issues Encountered

None beyond the two type errors documented above.

## Known Stubs

None — these are pure presentational components. CombOverlay renders from f0Hz prop (real data from backend). SpectrogramView renders the actual audio via WavesurferPlayer. ABPlayer wires both sides. No hardcoded empty arrays, placeholder text, or unconnected props.

## Next Phase Readiness

- Plan 04 (App.tsx composition) can import `{ ABPlayer }`, `{ SpectrogramView }`, `{ CombOverlay }` directly from `../components/`
- All three components accept the exact prop contracts specified in the 05-03-PLAN.md interfaces block
- `batchAudioUrl()` from `api/client.ts` provides the cleanUrl for ABPlayer in batch-demo mode
- `URL.createObjectURL(uploadedFile)` provides the noisyUrl for single-upload mode (no backend change needed)

## Self-Check: PASSED

- frontend/src/components/CombOverlay.tsx: FOUND
- frontend/src/components/SpectrogramView.tsx: FOUND
- frontend/src/components/ABPlayer.tsx: FOUND
- Commit 81d169a: FOUND
- Commit f465e98: FOUND
- Commit 7cd4462: FOUND
- npm run build: exits 0 (verified)
- npm run typecheck: exits 0 (verified)
