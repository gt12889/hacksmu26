---
phase: 08-frontend-component-integration
plan: "01"
subsystem: frontend
tags: [react, typescript, ui-integration, upload, batch-results]
dependency_graph:
  requires: []
  provides: [upload-ui, batch-results-ui, call-detail-ui]
  affects: [frontend/src/App.tsx, frontend/src/index.css]
tech_stack:
  added: [axios@1.15.0, wavesurfer.js@7.12.6, "@wavesurfer/react@1.0.12"]
  patterns: [component-composition, callback-lifting, useEffect-fetch-on-mount]
key_files:
  created: []
  modified:
    - frontend/src/App.tsx
    - frontend/src/index.css
    - frontend/package.json
    - frontend/package-lock.json
decisions:
  - "noisyUrl for fresh upload = uploadAudioUrl(fileId) — served from /api/upload/{fileId}/audio"
  - "cleanUrl for fresh upload = audioUrl(jobId, 0) — served from /api/result/{jobId}/audio/0"
  - "noisyUrl for batch row = null — original noisy audio not stored for batch-processed calls"
  - "cleanUrl for batch row = batchAudioUrl(result.clean_wav_path) — uses absolute path on disk"
  - "UploadSection and BatchSection defined at module level (not nested inside App) for clean React lifecycle"
  - "activeUpload state lifted to App() so UploadSection can receive it as a prop and re-render correctly"
metrics:
  duration_seconds: 173
  completed_date: "2026-04-12"
  tasks_completed: 2
  tasks_total: 3
  files_modified: 4
---

# Phase 08 Plan 01: Frontend Component Integration Summary

**One-liner:** Wired UploadPanel + useJobStatus + CallDetail and ConfidenceTable + CallDetail into App.tsx as two new named sections below the existing static demo, with brand-matched CSS.

## What Was Built

1. **UploadSection component** (App.tsx, module-level): Wraps `UploadPanel`, handles `onComplete` callback to set `ActiveResult` state, conditionally renders `CallDetail` with `noisyUrl = uploadAudioUrl(fileId)` and `cleanUrl = audioUrl(jobId, 0)`.

2. **BatchSection component** (App.tsx, module-level): Fetches `getBatchResults()` on mount, renders `ConfidenceTable` with sort/filter, renders `CallDetail` inline on row click with `noisyUrl = null` and `cleanUrl = batchAudioUrl(result.clean_wav_path)`.

3. **ActiveResult interface**: Typed container for `{ result: CallResult, noisyUrl: string | null, cleanUrl: string | null }` shared between UploadSection and App state.

4. **App() additions**: `activeUpload` state, `<UploadSection>` and `<BatchSection>` inserted between `<ComparisonSection />` and `<footer>` with dividers. All existing code left verbatim.

5. **index.css additions** (114 lines): `.upload-section`, `.call-detail-section`, `.confidence-section` with full table/input/header styling using only existing CSS design tokens.

## Key Implementation Decisions

| Decision | Rationale |
|---|---|
| `noisyUrl` = `uploadAudioUrl(fileId)` for uploads | fileId persists in API; serves original pre-processed audio |
| `noisyUrl` = `null` for batch rows | Batch pipeline only stores clean output; no original available |
| `cleanUrl` = `audioUrl(jobId, 0)` for uploads | Index 0 = first call result from the job |
| `cleanUrl` = `batchAudioUrl(path)` for batch | clean_wav_path is absolute disk path; API enforces allowlist |
| Components at module level, not nested | Avoids React re-mount on every App render; cleaner lifecycle |
| `activeUpload` lifted to App() | UploadSection can be unmounted/remounted without losing result |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing npm dependencies**
- **Found during:** Task 1 verification (npm run build)
- **Issue:** `axios`, `wavesurfer.js`, and `@wavesurfer/react` were imported by existing components (`api/client.ts`, `ABPlayer.tsx`, `SpectrogramView.tsx`) but not listed in `package.json` — causing TypeScript compilation errors
- **Fix:** `npm install axios wavesurfer.js @wavesurfer/react` — added to dependencies in package.json
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`
- **Commit:** f56c820

## Build Status

`npm run build` exits 0 with zero TypeScript errors. Output:
- `dist/assets/index-BZ8hQAty.css` 14.92 kB (gzip: 3.51 kB)
- `dist/assets/index-oaSWLfVc.js` 282.65 kB (gzip: 94.65 kB)

## Known Stubs

None — all components are wired to live API endpoints. `BatchSection` shows "No batch results yet" message (not a stub — this is accurate empty-state UI).

## Commits

| Task | Commit | Description |
|---|---|---|
| Task 1 | f56c820 | feat(08-01): integrate UploadPanel, ConfidenceTable, CallDetail into App.tsx |
| Task 2 | 1e7a81d | feat(08-01): add CSS section styles for upload, call-detail, confidence-section |

## Self-Check: PASSED

- `frontend/src/App.tsx` — exists, contains UploadSection, BatchSection, UploadPanel, ConfidenceTable, CallDetail
- `frontend/src/index.css` — exists, contains .upload-section, .call-detail-section, .confidence-section
- Commits f56c820 and 1e7a81d — both verified in git log
- `npm run build` exits 0 — confirmed above
