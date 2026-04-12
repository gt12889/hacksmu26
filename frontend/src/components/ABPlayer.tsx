import { useRef, useState } from 'react'
import type WaveSurfer from 'wavesurfer.js'
import { SpectrogramView } from './SpectrogramView'

export interface ABPlayerProps {
  noisyUrl: string
  cleanUrl: string
  f0Hz: number   // passed through to SpectrogramView for comb overlay
}

type Mode = 'noisy' | 'clean'

export function ABPlayer({ noisyUrl, cleanUrl, f0Hz }: ABPlayerProps) {
  const [mode, setMode] = useState<Mode>('noisy')
  const [resumeAt, setResumeAt] = useState(0)
  const [wasPlaying, setWasPlaying] = useState(false)
  const wsRef = useRef<WaveSurfer | null>(null)

  const activeUrl = mode === 'noisy' ? noisyUrl : cleanUrl

  const handleReady = (ws: WaveSurfer) => {
    wsRef.current = ws
    if (resumeAt > 0) {
      try {
        ws.setTime(resumeAt)
      } catch {
        // setTime can throw on 0-duration audio; ignore
      }
    }
    if (wasPlaying) {
      ws.play().catch(() => {})
    }
  }

  const handleToggle = () => {
    const ws = wsRef.current
    if (ws) {
      // CRITICAL: capture state BEFORE changing URL (Pitfall 3  A/B loses timestamp).
      // setTime() is called inside onReady of the new instance after decode completes.
      setResumeAt(ws.getCurrentTime())
      setWasPlaying(ws.isPlaying())
      ws.pause()
    }
    setMode((m) => (m === 'noisy' ? 'clean' : 'noisy'))
  }

  const handlePlayPause = () => {
    const ws = wsRef.current
    if (!ws) return
    if (ws.isPlaying()) ws.pause()
    else ws.play().catch(() => {})
  }

  return (
    <div className="ab-player">
      <div
        style={{
          display: 'flex',
          gap: 12,
          alignItems: 'center',
          marginBottom: 8,
        }}
      >
        <button onClick={handlePlayPause}>Play / Pause</button>
        <button
          onClick={handleToggle}
          style={{
            background: mode === 'clean' ? '#2a7a3a' : '#7a2a2a',
            color: 'white',
            padding: '6px 14px',
            borderRadius: 4,
            border: 'none',
            cursor: 'pointer',
          }}
        >
          {mode === 'noisy' ? 'Noisy (click for Clean)' : 'Clean (click for Noisy)'}
        </button>
        <span style={{ opacity: 0.6 }}>f0 = {f0Hz.toFixed(1)} Hz</span>
      </div>
      {/* key={activeUrl} forces SpectrogramView remount on URL change so onReady fires
          reliably  necessary for setTime to execute after new audio has decoded */}
      <SpectrogramView
        key={activeUrl}
        audioUrl={activeUrl}
        f0Hz={f0Hz}
        onReady={handleReady}
      />
    </div>
  )
}
