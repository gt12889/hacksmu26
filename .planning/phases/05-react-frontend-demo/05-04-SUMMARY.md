---
phase: 05-react-frontend-demo
plan: 04
subsystem: ui
tags: [react, typescript, vite, upload, table, comparison, frontend]

# Dependency graph
requires:
  - phase: 05-react-frontend-demo
    plan: 03
    provides: SpectrogramView, CombOverlay, ABPlayer components
  - phase: 05-react-frontend-demo
    plan: 02
    provides: types/api.ts, api/client.ts (batchAudioUrl, audioUrl, getBatchResults)
provides:
  - UploadPanel: WAV file upload + startProcessing + status polling via useJobStatus
  - ConfidenceTable: sortable (6 columns) + filterable table of CallResult rows (UI-04)
  - ComparisonPanel: 3-column SNR comparison — Original | LALAL.AI placeholder | Our Result (UI-03)
  - CallDetail: SpectrogramView + ABPlayer or SpectrogramView-only depending on noisyUrl (UI-05)
  - App.tsx: full end-to-end composition — batch results on mount, upload flow, row drill-down
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "useEffect for job completion callback — avoids side-effect-in-render React antipattern"
    - "useMemo for filtered+sorted table rows — O(n log n) only on dependency change"
    - "URL.createObjectURL(file) for noisyBlobUrl with useEffect cleanup via revokeObjectURL"
    - "batchAudioUrl(clean_wav_path) for batch-disk cleanUrl — enables SpectrogramView on all 212 batch rows"
    - "IIFE cleanUrl derivation — cleanly handles both source.kind branches in App.tsx"

key-files:
  created:
    - frontend/src/components/UploadPanel.tsx
    - frontend/src/components/ConfidenceTable.tsx
    - frontend/src/components/ComparisonPanel.tsx
    - frontend/src/components/CallDetail.tsx
  modified:
    - frontend/src/App.tsx
    - frontend/src/styles.css

key-decisions:
  - "noisyUrl is null for batch-disk rows (no blob available) — disables ABPlayer, falls back to SpectrogramView-only in CallDetail"
  - "cleanUrl is set for ALL rows (batch and upload) via batchAudioUrl/audioUrl — SpectrogramView always renders"
  - "URL.revokeObjectURL called in useEffect cleanup to prevent memory leak when source changes"
  - "ConfidenceTable uses original result index (i) from results.map as key and onSelect argument — preserved after sort/filter"

# Metrics
duration: 85s
completed: 2026-04-12
---

# Phase 5 Plan 04: Complete Frontend Demo — UploadPanel + ConfidenceTable + CallDetail + App.tsx Wiring Summary

**Full React demo with sortable/filterable 212-call browser, upload flow, spectrogram + comb overlay, A/B toggle, and 3-column SNR comparison — builds clean under strict TypeScript, pending human verification of the end-to-end flow**

## Performance

- **Duration:** ~85 seconds
- **Started:** 2026-04-12T04:05:34Z
- **Completed:** 2026-04-12T04:06:59Z
- **Tasks completed:** 2/3 (Task 3 is human-verify checkpoint)
- **Files created/modified:** 6

## Accomplishments

- `UploadPanel`: file input + Upload & Process button; calls uploadFile → startProcessing → polls via useJobStatus; useEffect fires onComplete when status===complete; error display; button disabled while processing
- `ConfidenceTable`: sortable on all 6 columns (confidence, f0_median_hz, snr_before_db, snr_after_db, noise_type, filename) with toggle asc/desc; filter input by filename or noise_type; row count display; useMemo for O(n log n) only on dep change; onSelect callback with original result index
- `ComparisonPanel`: 3-column CSS grid — Original (SNR before), LALAL.AI (N/A, dashed border, explanatory text), Our Result (SNR after, green background, improvement delta); all SNR values shown to 1 decimal
- `CallDetail`: determines canPlayAudio (noisyUrl AND cleanUrl both present) — renders ABPlayer if true, SpectrogramView-only if cleanUrl but no noisyUrl, "no audio" fallback if both null
- `App.tsx`: getBatchResults on mount; Source type union (batch | upload); noisyBlobUrl via createObjectURL with useEffect cleanup; cleanUrl IIFE derivation using batchAudioUrl for batch rows and audioUrl for upload rows; UploadPanel + ConfidenceTable + CallDetail composed end-to-end
- `npm run build` exits 0 — bundle 264.75 kB; strict TypeScript typecheck clean

## Task Commits

Each task was committed atomically:

1. **Task 1: UploadPanel + ConfidenceTable + ComparisonPanel + styles.css** - `9aabd05` (feat)
2. **Task 2: CallDetail + App.tsx wiring** - `4038446` (feat)
3. **Task 3: Human verify checkpoint** — pending

## Files Created/Modified

- `frontend/src/components/UploadPanel.tsx` - Upload flow with job status polling; exports UploadPanelProps + UploadPanel
- `frontend/src/components/ConfidenceTable.tsx` - Sortable/filterable table; exports ConfidenceTableProps + ConfidenceTable
- `frontend/src/components/ComparisonPanel.tsx` - 3-column SNR comparison; exports ComparisonPanelProps + ComparisonPanel
- `frontend/src/components/CallDetail.tsx` - Detail view with ABPlayer/SpectrogramView fallback; exports CallDetailProps + CallDetail
- `frontend/src/App.tsx` - Full demo composition with batch load, upload flow, row selection, cleanUrl derivation
- `frontend/src/styles.css` - Added input[type=file], button:disabled, h1 rules

## Decisions Made

- Used original array index `i` from `results.map((r, i) => ({ r, i }))` as the selection key — this preserves identity through sort/filter so `selectedIndex` correctly highlights the right row and passes the right index to `onSelect`
- `noisyUrl` is null for batch-disk rows by design — no blob is available without a fresh upload; this correctly disables ABPlayer while keeping SpectrogramView working via cleanUrl
- `batchAudioUrl(result.clean_wav_path)` provides cleanUrl for all 212 batch rows — this is the critical fix that makes SpectrogramView render on page load (the primary judge path)
- `URL.revokeObjectURL` in useEffect cleanup prevents blob URL memory leaks when user uploads a new file

## Deviations from Plan

None — plan executed exactly as written. Both templates in the plan correctly used `useEffect` (the plan itself included the antipattern note + correction). All components match the specified prop contracts exactly.

## Known Stubs

- `ComparisonPanel` LALAL.AI column shows "N/A" for SNR — this is intentional per the plan (LALAL.AI is a static comparison placeholder, not wired to any real LALAL.AI API). Judges are informed via explanatory note text.

## Self-Check: PASSED

- frontend/src/components/UploadPanel.tsx: FOUND
- frontend/src/components/ConfidenceTable.tsx: FOUND
- frontend/src/components/ComparisonPanel.tsx: FOUND
- frontend/src/components/CallDetail.tsx: FOUND
- frontend/src/App.tsx: modified (verified)
- frontend/src/styles.css: modified (verified)
- Commit 9aabd05: FOUND
- Commit 4038446: FOUND
- npm run build: exits 0 (verified — 264.75 kB bundle)
- dist/index.html: FOUND
