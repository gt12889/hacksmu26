import { useMemo, useState } from 'react'
import WavesurferPlayer from '@wavesurfer/react'
import Spectrogram from 'wavesurfer.js/dist/plugins/spectrogram.esm.js'
import type WaveSurfer from 'wavesurfer.js'
import { CombOverlay } from './CombOverlay'

export interface SpectrogramViewProps {
  audioUrl: string        // any playable URL (blob:, /api/..., etc.)
  f0Hz: number           // used to compute harmonic comb band positions
  height?: number        // spectrogram panel height in px; default 240
  onReady?: (ws: WaveSurfer) => void
}

const FREQ_MAX_HZ = 1000
const WAVE_HEIGHT = 80   // waveform strip above the spectrogram
const SPECTRO_HEIGHT = 240

export function SpectrogramView({
  audioUrl,
  f0Hz,
  height = SPECTRO_HEIGHT,
  onReady,
}: SpectrogramViewProps) {
  const [containerWidth, setContainerWidth] = useState(800)

  // CRITICAL: memoize plugins array  recreating on every render re-initializes wavesurfer,
  // causing an infinite render loop and canvas flicker. See 05-RESEARCH.md Pitfall 2.
  const plugins = useMemo(
    () => [
      Spectrogram.create({
        labels: true,
        height,
        fftSamples: 1024,
        frequencyMax: FREQ_MAX_HZ,
        colorMap: 'roseus',
      }),
    ],
    [height],
  )

  const handleReady = (ws: WaveSurfer) => {
    // Measure rendered container width for the overlay canvas
    const el = (ws as unknown as { getWrapper?: () => HTMLElement }).getWrapper?.()
    if (el && el.clientWidth > 0) setContainerWidth(el.clientWidth)
    onReady?.(ws)
  }

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <WavesurferPlayer
        height={WAVE_HEIGHT}
        waveColor="#4F4A85"
        progressColor="#7A74B8"
        url={audioUrl}
        plugins={plugins}
        onReady={handleReady}
      />
      {/* Overlay div positioned over the spectrogram canvas, which renders below the waveform */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: WAVE_HEIGHT, // spectrogram starts directly below the waveform strip
          width: '100%',
          height,
          pointerEvents: 'none',
        }}
      >
        <CombOverlay
          f0Hz={f0Hz}
          width={containerWidth}
          height={height}
          frequencyMax={FREQ_MAX_HZ}
        />
      </div>
    </div>
  )
}
