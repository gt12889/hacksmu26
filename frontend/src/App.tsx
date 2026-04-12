import { useEffect, useMemo, useState } from 'react'
import { UploadPanel } from './components/UploadPanel'
import { ConfidenceTable } from './components/ConfidenceTable'
import { CallDetail } from './components/CallDetail'
import { getBatchResults, audioUrl, batchAudioUrl } from './api/client'
import type { CallResult } from './types/api'
import './styles.css'

type Source =
  | { kind: 'batch'; results: CallResult[] }
  | {
      kind: 'upload'
      jobId: string
      fileId: string
      file: File
      results: CallResult[]
    }

export default function App() {
  const [source, setSource] = useState<Source | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  // On mount, load the 212 pre-processed batch results
  useEffect(() => {
    getBatchResults()
      .then((r) => {
        setSource({ kind: 'batch', results: r.results })
        setLoading(false)
      })
      .catch((e) => {
        setLoadError(String(e))
        setLoading(false)
      })
  }, [])

  // Blob URL for the noisy uploaded file (only fresh-upload mode)
  const noisyBlobUrl = useMemo(() => {
    if (source?.kind === 'upload') return URL.createObjectURL(source.file)
    return null
  }, [source])

  useEffect(() => {
    return () => {
      if (noisyBlobUrl) URL.revokeObjectURL(noisyBlobUrl)
    }
  }, [noisyBlobUrl])

  const handleUploadComplete = (args: {
    jobId: string
    fileId: string
    file: File
    results: CallResult[]
  }) => {
    setSource({ kind: 'upload', ...args })
    setSelectedIndex(0)
  }

  const selectedResult =
    selectedIndex !== null && source ? source.results[selectedIndex] ?? null : null

  // noisyUrl: only for fresh uploads (blob URL)
  const noisyUrl =
    source?.kind === 'upload' && selectedResult ? noisyBlobUrl : null

  // cleanUrl: set for BOTH upload and batch-disk rows so SpectrogramView renders.
  // For batch rows, batchAudioUrl encodes the absolute clean_wav_path and hits
  // GET /api/batch/audio?path=..., which enforces server-side path allowlist.
  const cleanUrl: string | null = (() => {
    if (!selectedResult) return null
    if (source?.kind === 'upload' && selectedIndex !== null) {
      return audioUrl(source.jobId, selectedIndex)
    }
    if (source?.kind === 'batch') {
      return selectedResult.clean_wav_path
        ? batchAudioUrl(selectedResult.clean_wav_path)
        : null
    }
    return null
  })()

  return (
    <div className="app">
      <h1>ElephantVoices Denoiser</h1>
      <p style={{ opacity: 0.7 }}>
        Harmonic comb masking for infrasonic elephant vocalizations.
      </p>

      <UploadPanel onComplete={handleUploadComplete} />

      {loading && <p>Loading batch results...</p>}
      {loadError && (
        <p style={{ color: '#f66' }}>Failed to load batch results: {loadError}</p>
      )}

      {source && (
        <>
          <h2 style={{ marginTop: 24 }}>
            {source.kind === 'upload' ? 'Upload Results' : 'Batch Results (212 calls)'}
          </h2>
          <ConfidenceTable
            results={source.results}
            selectedIndex={selectedIndex}
            onSelect={setSelectedIndex}
          />
          {selectedResult && (
            <CallDetail
              result={selectedResult}
              noisyUrl={noisyUrl}
              cleanUrl={cleanUrl}
            />
          )}
        </>
      )}
    </div>
  )
}
