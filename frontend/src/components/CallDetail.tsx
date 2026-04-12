import type { CallResult } from '../types/api'
import { ABPlayer } from './ABPlayer'
import { SpectrogramView } from './SpectrogramView'
import { ComparisonPanel } from './ComparisonPanel'

export interface CallDetailProps {
  result: CallResult
  /** Noisy audio URL  only available for fresh uploads (blob URL) */
  noisyUrl: string | null
  /** Clean audio URL  available for BOTH fresh uploads and batch-disk rows */
  cleanUrl: string | null
}

export function CallDetail({ result, noisyUrl, cleanUrl }: CallDetailProps) {
  const canPlayAudio = noisyUrl !== null && cleanUrl !== null

  return (
    <div style={{ marginTop: 16 }}>
      <ComparisonPanel result={result} />
      <h2>Spectrogram + Audio</h2>
      {canPlayAudio ? (
        <ABPlayer
          noisyUrl={noisyUrl!}
          cleanUrl={cleanUrl!}
          f0Hz={result.f0_median_hz}
        />
      ) : (
        <div>
          {cleanUrl ? (
            <SpectrogramView audioUrl={cleanUrl} f0Hz={result.f0_median_hz} />
          ) : (
            <p style={{ opacity: 0.6 }}>
              No audio available for this call.
            </p>
          )}
          {!noisyUrl && (
            <p style={{ opacity: 0.5, fontSize: 13 }}>
              A/B audio toggle requires a fresh upload. Upload a file above to enable playback.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
