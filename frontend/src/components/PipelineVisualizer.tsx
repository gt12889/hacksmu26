/**
 * PipelineVisualizer  animated 7-stage pipeline demo for judges.
 *
 * Accepts a WAV file drop/upload, sends it to POST /api/pipeline/visualize,
 * then animates through each pipeline stage using the stage.duration_ms timing.
 * At the end shows A/B audio and summary metrics.
 */
import { useState, useRef, useCallback, useEffect } from 'react'

// ─── Types ───────────────────────────────────────────────────────────────────

interface StageBase {
  id: string
  name: string
  description: string
  duration_ms: number
}

interface StageStft extends StageBase {
  id: 'stft'
  image_b64: string
}

interface StageClassify extends StageBase {
  id: 'classify'
  noise_type: string
  spectral_flatness: number
  image_b64: string
}

interface StageHpss extends StageBase {
  id: 'hpss'
  harmonic_image_b64: string
  percussive_image_b64: string
}

interface StageShs extends StageBase {
  id: 'shs'
  f0_median_hz: number
  f0_range_hz: [number, number]
  shs_heatmap_b64: string
}

interface StageCombMask extends StageBase {
  id: 'comb_mask'
  mask_overlay_b64: string
  harmonic_frequencies_hz: number[]
}

interface StageReconstruct extends StageBase {
  id: 'reconstruct'
  cleaned_image_b64: string
}

interface StageDenoise extends StageBase {
  id: 'denoise'
  final_image_b64: string
  final_audio_b64: string
  original_audio_b64: string
}

type Stage =
  | StageStft
  | StageClassify
  | StageHpss
  | StageShs
  | StageCombMask
  | StageReconstruct
  | StageDenoise

interface PipelineResult {
  sample_rate: number
  duration_sec: number
  n_fft: number
  stages: Stage[]
  metrics: {
    f0_median_hz: number
    f0_range_hz: [number, number]
    noise_type: string
    spectral_flatness: number
    harmonic_integrity_before: number
    harmonic_integrity_after: number
    snr_before_db: number
    snr_after_db: number
    snr_improvement_db: number
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function stageImage(stage: Stage): string | null {
  switch (stage.id) {
    case 'stft':     return stage.image_b64
    case 'classify': return stage.image_b64
    case 'hpss':     return stage.harmonic_image_b64
    case 'shs':      return stage.shs_heatmap_b64
    case 'comb_mask':    return stage.mask_overlay_b64
    case 'reconstruct':  return stage.cleaned_image_b64
    case 'denoise':      return stage.final_image_b64
    default: return null
  }
}

function noiseBadgeColor(noiseType: string): string {
  const map: Record<string, string> = {
    generator: 'var(--orange)',
    car:        'var(--blue)',
    plane:      'var(--purple)',
    mixed:      'var(--text-muted)',
  }
  return map[noiseType] ?? 'var(--text-muted)'
}

// ─── Drop Zone ───────────────────────────────────────────────────────────────

function DropZone({ onFile, disabled }: { onFile: (f: File) => void; disabled: boolean }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) onFile(f)
  }, [onFile])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) onFile(f)
  }, [onFile])

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      style={{
        border: `2px dashed ${dragging ? 'var(--brown)' : 'var(--border-dark)'}`,
        borderRadius: 'var(--radius)',
        padding: '2.5rem 2rem',
        textAlign: 'center',
        cursor: disabled ? 'not-allowed' : 'pointer',
        background: dragging ? 'var(--brown-dim)' : 'var(--bg-warm)',
        transition: 'border-color 0.2s, background 0.2s',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".wav,audio/wav,audio/x-wav"
        style={{ display: 'none' }}
        onChange={handleChange}
        disabled={disabled}
      />
      <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🎵</div>
      <p style={{
        fontFamily: 'var(--font-display)',
        fontSize: '1rem',
        fontWeight: 700,
        color: 'var(--text)',
        marginBottom: '0.35rem',
      }}>
        Drop a WAV file here
      </p>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
        or click to browse  .wav accepted
      </p>
    </div>
  )
}

// ─── Stage Pill ───────────────────────────────────────────────────────────────

function StagePill({
  index, total, active,
}: { index: number; total: number; active: boolean }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: '2rem',
      height: '2rem',
      borderRadius: '50%',
      background: active ? 'var(--brown)' : 'var(--bg-warm)',
      border: `2px solid ${active ? 'var(--brown)' : 'var(--border-dark)'}`,
      color: active ? '#fff' : 'var(--text-muted)',
      fontFamily: 'var(--font-mono)',
      fontSize: '0.72rem',
      fontWeight: 700,
      flexShrink: 0,
      transition: 'background 0.3s, border-color 0.3s',
    }}>
      {index + 1}
    </span>
  )
}

// ─── Stage View ───────────────────────────────────────────────────────────────

function StageView({
  stage,
  stageIndex,
  totalStages,
  isLast,
  result,
  playing,
  onPlayToggle,
}: {
  stage: Stage
  stageIndex: number
  totalStages: number
  isLast: boolean
  result: PipelineResult
  playing: 'original' | 'clean' | null
  onPlayToggle: (which: 'original' | 'clean') => void
}) {
  const [imgVisible, setImgVisible] = useState(false)
  const [computing, setComputing] = useState(true)
  const [computeProgress, setComputeProgress] = useState(0)
  const imgSrc = stageImage(stage)

  // Simulated compute phase: ~900ms of "loading" before revealing the image
  const COMPUTE_MS = 900

  useEffect(() => {
    setImgVisible(false)
    setComputing(true)
    setComputeProgress(0)

    const start = performance.now()
    let raf = 0
    const tick = () => {
      const elapsed = performance.now() - start
      const p = Math.min(1, elapsed / COMPUTE_MS)
      setComputeProgress(p)
      if (p < 1) {
        raf = requestAnimationFrame(tick)
      } else {
        setComputing(false)
        setTimeout(() => setImgVisible(true), 50)
      }
    }
    raf = requestAnimationFrame(tick)

    return () => cancelAnimationFrame(raf)
  }, [stage.id])

  // Stage-specific loading message
  const loadingMessage = (() => {
    switch (stage.id) {
      case 'stft':
        return 'Computing Short-Time Fourier Transform @ n_fft=8192...'
      case 'classify':
        return 'Analyzing spectral flatness of noise gaps...'
      case 'hpss':
        return 'Median filtering harmonic vs percussive components...'
      case 'shs':
        return 'Sweeping f₀ candidates from 8–25 Hz, summing subharmonics...'
      case 'comb_mask':
        return 'Building time-varying bandpass at integer multiples of f₀...'
      case 'reconstruct':
        return 'Applying mask to magnitude, reconstructing via phase-preserved ISTFT...'
      case 'denoise':
        return 'Running residual non-stationary spectral gating...'
      default:
        return `Processing ${(stage as { name: string }).name}...`
    }
  })()

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      overflow: 'hidden',
      boxShadow: 'var(--shadow-md)',
    }}>
      {/* Stage header */}
      <div style={{
        padding: '1rem 1.25rem 0.85rem',
        background: 'var(--bg-warm)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '0.85rem',
      }}>
        <StagePill index={stageIndex} total={totalStages} active />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: 'var(--brown)',
            }}>
              Stage {stageIndex + 1} / {totalStages}
            </span>
            {stage.id === 'classify' && (
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.62rem',
                padding: '0.1rem 0.5rem',
                borderRadius: '100px',
                border: `1px solid ${noiseBadgeColor((stage as StageClassify).noise_type)}`,
                color: noiseBadgeColor((stage as StageClassify).noise_type),
                background: 'transparent',
              }}>
                {(stage as StageClassify).noise_type.toUpperCase()}
              </span>
            )}
          </div>
          <h3 style={{
            fontFamily: 'var(--font-display)',
            fontSize: '1.15rem',
            fontWeight: 700,
            color: 'var(--text)',
            marginBottom: '0.25rem',
          }}>
            {stage.name}
          </h3>
          <p style={{
            fontSize: '0.82rem',
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            lineHeight: 1.55,
          }}>
            {stage.description}
          </p>
        </div>
      </div>

      {/* Stage image with loading overlay */}
      {imgSrc && (
        <div style={{
          background: '#0a0a0a',
          overflow: 'hidden',
          position: 'relative',
          minHeight: '200px',
        }}>
          {/* Blurred placeholder */}
          <img
            src={imgSrc}
            alt=""
            aria-hidden="true"
            style={{
              width: '100%',
              display: 'block',
              opacity: 0.15,
              filter: 'blur(16px) brightness(0.6)',
              transform: 'scale(1.05)',
              position: 'absolute',
              top: 0,
              left: 0,
            }}
          />
          {/* Full-res image (fades in after compute) */}
          <img
            src={imgSrc}
            alt={stage.name}
            style={{
              width: '100%',
              display: 'block',
              opacity: imgVisible ? 1 : 0,
              transform: imgVisible ? 'scale(1)' : 'scale(0.985)',
              transition: 'opacity 0.45s ease, transform 0.45s ease',
              position: 'relative',
            }}
          />
          {/* Loading overlay */}
          {computing && (
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '1rem',
              background: 'rgba(10, 10, 10, 0.55)',
              backdropFilter: 'blur(2px)',
              zIndex: 2,
              pointerEvents: 'none',
            }}>
              {/* Spinner ring */}
              <div style={{
                width: '52px',
                height: '52px',
                border: '3px solid rgba(255, 255, 255, 0.12)',
                borderTopColor: 'var(--orange, #ff7c2a)',
                borderRightColor: 'var(--orange, #ff7c2a)',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
              }} />
              {/* Status text */}
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.78rem',
                color: '#fff',
                textAlign: 'center',
                maxWidth: '80%',
                lineHeight: 1.5,
                textShadow: '0 1px 4px rgba(0,0,0,0.8)',
              }}>
                <div style={{
                  color: 'var(--orange, #ff7c2a)',
                  fontSize: '0.68rem',
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  marginBottom: '0.4rem',
                  fontWeight: 700,
                }}>
                  ⚙ Running stage {stageIndex + 1}/{totalStages}
                </div>
                {loadingMessage}
              </div>
              {/* Progress bar */}
              <div style={{
                width: '55%',
                maxWidth: '340px',
                height: '3px',
                background: 'rgba(255,255,255,0.12)',
                borderRadius: '2px',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${computeProgress * 100}%`,
                  height: '100%',
                  background: 'linear-gradient(90deg, var(--orange, #ff7c2a), #ffb347)',
                  transition: 'width 0.05s linear',
                  boxShadow: '0 0 12px rgba(255, 124, 42, 0.6)',
                }} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* HPSS: show both panels if available */}
      {stage.id === 'hpss' && (
        <div style={{
          padding: '0.75rem 1.25rem',
          background: 'var(--bg-warm)',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          gap: '0.5rem',
          fontSize: '0.72rem',
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-muted)',
        }}>
          <span style={{ color: 'cyan' }}>■ Harmonic</span>
          <span style={{ color: 'var(--orange)' }}>■ Percussive</span>
          <span> combined view shown</span>
        </div>
      )}

      {/* SHS extra info */}
      {stage.id === 'shs' && (() => {
        const s = stage as StageShs
        return (
          <div style={{
            padding: '0.75rem 1.25rem',
            background: 'var(--bg-warm)',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            gap: '1.5rem',
            fontSize: '0.78rem',
            fontFamily: 'var(--font-mono)',
          }}>
            <span>
              <span style={{ color: 'var(--text-muted)' }}>f0 median: </span>
              <strong style={{ color: '#0f0' }}>{s.f0_median_hz.toFixed(1)} Hz</strong>
            </span>
            <span>
              <span style={{ color: 'var(--text-muted)' }}>range: </span>
              <strong style={{ color: '#0f0' }}>
                {s.f0_range_hz[0].toFixed(1)}–{s.f0_range_hz[1].toFixed(1)} Hz
              </strong>
            </span>
          </div>
        )
      })()}

      {/* Comb mask harmonic list */}
      {stage.id === 'comb_mask' && (() => {
        const s = stage as StageCombMask
        const shown = s.harmonic_frequencies_hz.slice(0, 8)
        return (
          <div style={{
            padding: '0.75rem 1.25rem',
            background: 'var(--bg-warm)',
            borderTop: '1px solid var(--border)',
            fontSize: '0.72rem',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
          }}>
            <span style={{ color: 'cyan', marginRight: '0.5rem' }}>Harmonics:</span>
            {shown.map((f, i) => (
              <span key={i} style={{ marginRight: '0.4rem', color: 'var(--text-dim)' }}>
                {f.toFixed(0)}
              </span>
            ))}
            {s.harmonic_frequencies_hz.length > 8 && (
              <span>... ({s.harmonic_frequencies_hz.length} total)</span>
            )}
            <span> Hz</span>
          </div>
        )
      })()}

      {/* Final stage: A/B audio player */}
      {isLast && stage.id === 'denoise' && (() => {
        const s = stage as StageDenoise
        const m = result.metrics
        return (
          <div style={{
            padding: '1rem 1.25rem',
            borderTop: '1px solid var(--border)',
          }}>
            {/* Metrics row */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '0.5rem',
              marginBottom: '1rem',
              padding: '0.75rem',
              background: 'var(--bg-warm)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
            }}>
              {[
                { label: 'SNR Before', val: `${m.snr_before_db.toFixed(1)} dB`, cls: '' },
                { label: 'SNR After', val: `${m.snr_after_db.toFixed(1)} dB`, cls: 'positive' },
                { label: 'SNR Gain', val: `+${m.snr_improvement_db.toFixed(1)} dB`, cls: 'positive' },
                { label: 'HI Before', val: `${m.harmonic_integrity_before.toFixed(0)}%`, cls: '' },
                { label: 'HI After', val: `${m.harmonic_integrity_after.toFixed(0)}%`, cls: 'positive' },
                { label: 'f0 Median', val: `${m.f0_median_hz.toFixed(1)} Hz`, cls: 'cyan' },
              ].map(({ label, val, cls }) => (
                <div key={label} className="metric">
                  <span className="metric-label">{label}</span>
                  <span className={`metric-value ${cls}`}>{val}</span>
                </div>
              ))}
            </div>

            {/* A/B toggle */}
            <p style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.62rem',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--text-muted)',
              marginBottom: '0.5rem',
            }}>
              A/B Audio Toggle
            </p>
            <div className="audio-buttons">
              <button
                className={`audio-btn ${playing === 'original' ? 'active-original' : ''}`}
                onClick={() => onPlayToggle('original')}
              >
                {playing === 'original' && <span className="pulse-dot orange" />}
                {playing === 'original' ? 'Pause' : '▶'} Original
              </button>
              <button
                className={`audio-btn ${playing === 'clean' ? 'active-clean' : ''}`}
                onClick={() => onPlayToggle('clean')}
              >
                {playing === 'clean' && <span className="pulse-dot green" />}
                {playing === 'clean' ? 'Pause' : '▶'} Cleaned
              </button>
            </div>

            {/* Hidden audio elements driven by base64 data URLs */}
            <audio id="pv-original-audio" src={s.original_audio_b64} preload="auto" style={{ display: 'none' }} />
            <audio id="pv-clean-audio"    src={s.final_audio_b64}    preload="auto" style={{ display: 'none' }} />
          </div>
        )
      })()}
    </div>
  )
}

// ─── Step tracker sidebar ─────────────────────────────────────────────────────

function StepTracker({
  stages,
  currentIndex,
  onJump,
}: {
  stages: Stage[]
  currentIndex: number
  onJump: (i: number) => void
}) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '0.4rem',
    }}>
      {stages.map((s, i) => {
        const done = i < currentIndex
        const active = i === currentIndex
        return (
          <button
            key={s.id}
            onClick={() => onJump(i)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem',
              padding: '0.45rem 0.7rem',
              border: `1px solid ${active ? 'var(--brown)' : done ? 'var(--border-dark)' : 'var(--border)'}`,
              borderRadius: 'var(--radius-sm)',
              background: active ? 'var(--brown-dim)' : done ? 'var(--bg-section)' : 'transparent',
              cursor: 'pointer',
              textAlign: 'left',
              transition: 'background 0.2s, border-color 0.2s',
            }}
          >
            <span style={{
              width: '1.4rem',
              height: '1.4rem',
              borderRadius: '50%',
              background: done ? 'var(--green)' : active ? 'var(--brown)' : 'var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: done || active ? '#fff' : 'var(--text-muted)',
              fontSize: '0.6rem',
              fontWeight: 700,
              flexShrink: 0,
              fontFamily: 'var(--font-mono)',
            }}>
              {done ? '✓' : i + 1}
            </span>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.68rem',
              color: active ? 'var(--brown)' : done ? 'var(--text-dim)' : 'var(--text-muted)',
              fontWeight: active ? 700 : 400,
              lineHeight: 1.3,
            }}>
              {s.name}
            </span>
          </button>
        )
      })}
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function PipelineVisualizer() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PipelineResult | null>(null)

  // Animation state
  const [currentStage, setCurrentStage] = useState(0)
  const [paused, setPaused] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Audio playback
  const [playing, setPlaying] = useState<'original' | 'clean' | null>(null)

  // ── Upload handler ────────────────────────────────────────────────────────
  const handleFile = useCallback(async (f: File) => {
    setFile(f)
    setError(null)
    setResult(null)
    setCurrentStage(0)
    setPaused(false)
    setPlaying(null)
    setLoading(true)

    try {
      const fd = new FormData()
      fd.append('file', f)
      const res = await fetch('/api/pipeline/visualize', { method: 'POST', body: fd })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Server error ${res.status}: ${text}`)
      }
      const data: PipelineResult = await res.json()
      setResult(data)
      setCurrentStage(0)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  // ── Auto-advance timer ────────────────────────────────────────────────────
  useEffect(() => {
    if (!result || paused) return
    const stage = result.stages[currentStage]
    if (!stage) return

    // Ensure at least 1800ms so the loading illusion (900ms) + reveal + view (900ms)
    // all get a chance to play even if the backend reports a shorter duration.
    const displayMs = Math.max(stage.duration_ms, 1800)
    timerRef.current = setTimeout(() => {
      if (currentStage < result.stages.length - 1) {
        setCurrentStage(i => i + 1)
      }
    }, displayMs)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [result, currentStage, paused])

  // ── Audio toggle ──────────────────────────────────────────────────────────
  const handlePlayToggle = useCallback((which: 'original' | 'clean') => {
    const origEl = document.getElementById('pv-original-audio') as HTMLAudioElement | null
    const cleanEl = document.getElementById('pv-clean-audio') as HTMLAudioElement | null
    const thisEl = which === 'original' ? origEl : cleanEl
    const otherEl = which === 'original' ? cleanEl : origEl

    if (!thisEl) return

    if (otherEl && !otherEl.paused) {
      otherEl.pause()
      otherEl.currentTime = 0
    }

    if (playing === which) {
      thisEl.pause()
      thisEl.currentTime = 0
      setPlaying(null)
    } else {
      thisEl.play().catch(() => {})
      setPlaying(which)
    }
  }, [playing])

  useEffect(() => {
    const origEl = document.getElementById('pv-original-audio') as HTMLAudioElement | null
    const cleanEl = document.getElementById('pv-clean-audio') as HTMLAudioElement | null
    const handler = () => setPlaying(null)
    origEl?.addEventListener('ended', handler)
    cleanEl?.addEventListener('ended', handler)
    return () => {
      origEl?.removeEventListener('ended', handler)
      cleanEl?.removeEventListener('ended', handler)
    }
  }, [result])

  // ── Jump to stage ─────────────────────────────────────────────────────────
  const jumpTo = useCallback((i: number) => {
    if (!result) return
    if (timerRef.current) clearTimeout(timerRef.current)
    setCurrentStage(i)
    setPaused(true)
  }, [result])

  // ── Progress % ────────────────────────────────────────────────────────────
  const progress = result
    ? Math.round(((currentStage + 1) / result.stages.length) * 100)
    : 0

  const stage = result?.stages[currentStage] ?? null
  const isLast = result ? currentStage === result.stages.length - 1 : false

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ width: '100%' }}>
      {/* Drop zone  only show when not yet loaded */}
      {!result && !loading && (
        <DropZone onFile={handleFile} disabled={loading} />
      )}

      {/* Loading spinner */}
      {loading && (
        <div className="loading-panel" style={{ maxWidth: '100%' }}>
          <div className="spinner" />
          <p style={{ color: 'var(--text-dim)', fontSize: '0.9rem', marginBottom: '0.4rem' }}>
            Running 7-stage pipeline on {file?.name}...
          </p>
          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.72rem',
            color: 'var(--text-muted)',
          }}>
            STFT → classify → HPSS → SHS → comb mask → ISTFT → noisereduce
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          padding: '1.25rem',
          background: '#fff0f0',
          border: '1px solid #ffb3b3',
          borderRadius: 'var(--radius)',
          color: '#c0392b',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.8rem',
        }}>
          Error: {error}
          <button
            onClick={() => { setError(null); setFile(null) }}
            style={{
              marginLeft: '1rem',
              background: 'none',
              border: 'none',
              color: '#c0392b',
              cursor: 'pointer',
              textDecoration: 'underline',
              fontSize: '0.78rem',
            }}
          >
            Try again
          </button>
        </div>
      )}

      {/* Animated pipeline */}
      {result && stage && (
        <>
          {/* Top progress bar */}
          <div style={{
            height: '4px',
            background: 'var(--border)',
            borderRadius: '2px',
            marginBottom: '1.5rem',
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${progress}%`,
              background: 'var(--brown)',
              transition: 'width 0.4s ease',
              borderRadius: '2px',
            }} />
          </div>

          {/* Main layout: sidebar + stage */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '200px 1fr',
            gap: '1.25rem',
            alignItems: 'start',
          }}>
            {/* Left: step tracker */}
            <div>
              <p style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.6rem',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                marginBottom: '0.6rem',
              }}>
                Pipeline Stages
              </p>
              <StepTracker
                stages={result.stages}
                currentIndex={currentStage}
                onJump={jumpTo}
              />

              {/* Controls */}
              <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <button
                  className="btn-secondary"
                  onClick={() => setPaused(p => !p)}
                  style={{ fontSize: '0.78rem', justifyContent: 'center' }}
                >
                  {paused ? '▶ Resume' : 'Pause'}
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setResult(null)
                    setFile(null)
                    setCurrentStage(0)
                    setPaused(false)
                    setPlaying(null)
                    setError(null)
                  }}
                  style={{ fontSize: '0.78rem', justifyContent: 'center' }}
                >
                  Upload New
                </button>
              </div>

              {/* File info */}
              {file && (
                <div style={{
                  marginTop: '0.75rem',
                  padding: '0.5rem 0.6rem',
                  background: 'var(--bg-warm)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.65rem',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  lineHeight: 1.5,
                  wordBreak: 'break-all',
                }}>
                  <strong style={{ color: 'var(--text-dim)', display: 'block' }}>
                    {file.name}
                  </strong>
                  {result.duration_sec.toFixed(1)}s · {(result.sample_rate / 1000).toFixed(0)} kHz
                </div>
              )}
            </div>

            {/* Right: current stage */}
            <StageView
              stage={stage}
              stageIndex={currentStage}
              totalStages={result.stages.length}
              isLast={isLast}
              result={result}
              playing={playing}
              onPlayToggle={handlePlayToggle}
            />
          </div>

          {/* Navigation arrows */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: '1rem',
            paddingTop: '1rem',
            borderTop: '1px solid var(--border)',
          }}>
            <button
              className="btn-secondary"
              onClick={() => jumpTo(Math.max(0, currentStage - 1))}
              disabled={currentStage === 0}
              style={{ fontSize: '0.82rem' }}
            >
              Prev
            </button>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
            }}>
              {currentStage + 1} / {result.stages.length}
              {paused && ' · PAUSED'}
              {!paused && !isLast && ' · AUTO-ADVANCING'}
              {isLast && ' · COMPLETE'}
            </span>
            <button
              className="btn-secondary"
              onClick={() => jumpTo(Math.min(result.stages.length - 1, currentStage + 1))}
              disabled={isLast}
              style={{ fontSize: '0.82rem' }}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}
