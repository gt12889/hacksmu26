import { useState, useEffect, useRef, useCallback } from 'react'
import type { DemoStatus, NoiseType, Metadata, StatusResponse } from './types'
import { UploadPanel } from './components/UploadPanel'
import { PipelineVisualizer } from './components/PipelineVisualizer'
import { CallDetail } from './components/CallDetail'
import { ConfidenceTable } from './components/ConfidenceTable'
import { getBatchResults, batchAudioUrl, uploadAudioUrl, audioUrl } from './api/client'
import type { CallResult } from './types/api'
import ElephantViewer from './ElephantViewer'

// ─── Noise type config ──────────────────────────────────────────────────────
const NOISE_CONFIG = {
  generator: {
    label: 'GENERATOR',
    color: 'var(--orange)',
    dimColor: 'var(--orange-dim)',
    borderColor: 'rgba(255, 124, 42, 0.3)',
    icon: '⚡',
    description: 'Constant 30 Hz tonal hum — engine fundamentals overlap directly with elephant f0 range.',
    detail: 'Generator noise produces a steady harmonic series at ~30 Hz. Because elephant rumbles also have fundamentals at 10–25 Hz, the 2nd harmonic of a generator (60 Hz) lands squarely on elephant 4f0. Generic tools trained on speech mistakenly preserve the engine tone. Our stationary noisereduce profile mode eliminates it cleanly.',
  },
  car: {
    label: 'CAR ENGINE',
    color: 'var(--blue)',
    dimColor: 'var(--blue-dim)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    icon: '🚗',
    description: 'Transient broadband burst — engine startup and idle spread energy across the full infrasonic band.',
    detail: 'Car engine noise is non-stationary: it sweeps rapidly as RPM changes, contaminating wide frequency bands in short bursts. We use adaptive non-stationary spectral gating after comb masking to clean the residual. The comb mask already removed most car harmonics that overlapped elephant content.',
  },
  plane: {
    label: 'AIRCRAFT',
    color: 'var(--purple)',
    dimColor: 'var(--purple-dim)',
    borderColor: 'rgba(168, 85, 247, 0.3)',
    icon: '✈️',
    description: 'Slow-sweep harmonic drone — aircraft flyover sweeps through the entire elephant frequency range.',
    detail: 'Aircraft noise is the hardest case: the engine drone slowly sweeps from below elephant f0 through its harmonic range and out the other side. Our time-varying comb mask tracks elephant f0 frame-by-frame, so even as plane noise sweeps through, the mask stays locked on elephant harmonics and rejects everything else.',
  },
} as const

const NOISE_TYPES: NoiseType[] = ['generator', 'car', 'plane']

// ─── Audio player hook ──────────────────────────────────────────────────────
function useAudioPlayer(noiseType: NoiseType) {
  const origRef = useRef<HTMLAudioElement>(null)
  const cleanRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState<'original' | 'clean' | null>(null)

  const toggle = useCallback((which: 'original' | 'clean') => {
    const thisRef  = which === 'original' ? origRef  : cleanRef
    const otherRef = which === 'original' ? cleanRef : origRef

    if (!thisRef.current) return

    // Pause the other one
    if (otherRef.current && !otherRef.current.paused) {
      otherRef.current.pause()
      otherRef.current.currentTime = 0
    }

    if (playing === which) {
      thisRef.current.pause()
      thisRef.current.currentTime = 0
      setPlaying(null)
    } else {
      thisRef.current.play().catch(() => {})
      setPlaying(which)
    }
  }, [playing])

  const handleEnded = useCallback(() => setPlaying(null), [])

  return { origRef, cleanRef, playing, toggle, handleEnded }
}

// ─── Demo Card ──────────────────────────────────────────────────────────────
function DemoCard({ noiseType, metadata }: { noiseType: NoiseType; metadata: Metadata | null }) {
  const cfg = NOISE_CONFIG[noiseType]
  const metrics = metadata?.[noiseType]
  const [detailOpen, setDetailOpen] = useState(false)
  const [imgLoaded, setImgLoaded] = useState(false)
  const { origRef, cleanRef, playing, toggle, handleEnded } = useAudioPlayer(noiseType)

  return (
    <div className="demo-card">
      {/* Header */}
      <div className="card-header">
        <div>
          <span
            className="noise-badge"
            style={{
              color: cfg.color,
              background: cfg.dimColor,
              border: `1px solid ${cfg.borderColor}`,
            }}
          >
            <span>{cfg.icon}</span>
            {cfg.label}
          </span>
          {metrics?.real_data && (
            <span
              style={{
                marginLeft: '0.5rem',
                display: 'inline-block',
                padding: '0.15rem 0.5rem',
                background: 'rgba(0, 200, 100, 0.12)',
                color: '#00c864',
                border: '1px solid rgba(0, 200, 100, 0.3)',
                borderRadius: '4px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.65rem',
                fontWeight: 700,
                letterSpacing: '0.05em',
                verticalAlign: 'middle',
              }}
            >
              ● REAL DATA
            </span>
          )}
          <p className="card-desc">{cfg.description}</p>
          {metrics?.source_file && (
            <p style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.65rem',
              color: 'var(--text-muted)',
              marginTop: '0.25rem',
            }}>
              {metrics.source_file} · {metrics.call_window}
            </p>
          )}
        </div>
      </div>

      {/* Spectrogram */}
      <div className="spectrogram-wrap">
        {!imgLoaded && (
          <div className="spectrogram-placeholder">
            <span>Loading spectrogram...</span>
          </div>
        )}
        <img
          src={`/static/demo/${noiseType}_demo.png`}
          alt={`${noiseType} noise — before/after spectrogram`}
          style={{
            display: 'block',
            opacity: imgLoaded ? 1 : 0,
            transition: 'opacity 0.3s ease',
          }}
          onLoad={() => setImgLoaded(true)}
          onError={() => setImgLoaded(false)}
        />
      </div>

      {/* Metrics */}
      <div className="card-metrics">
        <div className="metric">
          <span className="metric-label">Harmonic (Baseline)</span>
          <span className="metric-value">
            {metrics?.harmonic_dominance_baseline !== undefined
              ? `${metrics.harmonic_dominance_baseline.toFixed(1)}%`
              : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Harmonic (Ours)</span>
          <span className="metric-value positive">
            {metrics?.harmonic_dominance_ours !== undefined
              ? `${metrics.harmonic_dominance_ours.toFixed(1)}%`
              : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">vs Baseline</span>
          <span className="metric-value positive">
            {metrics?.harmonic_dominance_delta !== undefined
              ? `${metrics.harmonic_dominance_delta >= 0 ? '+' : ''}${metrics.harmonic_dominance_delta.toFixed(1)}%`
              : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">f₀ Range</span>
          <span className="metric-value cyan" style={{ fontSize: '0.72rem' }}>
            {metrics ? `${metrics.f0_min.toFixed(0)}–${metrics.f0_max.toFixed(0)} Hz` : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">f₀ Median</span>
          <span className="metric-value cyan">
            {metrics ? `${metrics.f0_median.toFixed(1)} Hz` : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Duration</span>
          <span className="metric-value">
            {metrics ? `${metrics.duration.toFixed(1)}s` : '—'}
          </span>
        </div>
      </div>

      {/* Audio player */}
      <div className="audio-player">
        <span className="audio-label">A/B Audio Toggle</span>
        <div className="audio-buttons">
          <button
            className={`audio-btn ${playing === 'original' ? 'active-original' : ''}`}
            onClick={() => toggle('original')}
            title="Play noisy original"
          >
            {playing === 'original' && <span className="pulse-dot orange" />}
            {playing === 'original' ? '⏸' : '▶'} Original
          </button>
          <button
            className={`audio-btn ${playing === 'clean' ? 'active-clean' : ''}`}
            onClick={() => toggle('clean')}
            title="Play denoised output"
          >
            {playing === 'clean' && <span className="pulse-dot green" />}
            {playing === 'clean' ? '⏸' : '▶'} Cleaned
          </button>
        </div>

        {/* Hidden audio elements */}
        <audio
          ref={origRef}
          src={`/static/demo/${noiseType}_original.wav`}
          onEnded={handleEnded}
          preload="none"
        />
        <audio
          ref={cleanRef}
          src={`/static/demo/${noiseType}_clean.wav`}
          onEnded={handleEnded}
          preload="none"
        />
      </div>

      {/* Expandable detail */}
      <div className="card-detail">
        <button className="detail-toggle" onClick={() => setDetailOpen(o => !o)}>
          <span>How it works</span>
          <span>{detailOpen ? '▲' : '▼'}</span>
        </button>
        {detailOpen && (
          <div className="detail-body">{cfg.detail}</div>
        )}
      </div>
    </div>
  )
}

// ─── Loading panel ──────────────────────────────────────────────────────────
function LoadingPanel({ progress, message }: { progress: number; message: string }) {
  return (
    <div className="loading-panel">
      <div className="spinner" />
      <p style={{ color: 'var(--text-dim)', marginBottom: '0.5rem', fontSize: '0.95rem' }}>
        Running pipeline...
      </p>
      <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
        {message || 'Initializing...'}
      </p>
      <div className="progress-bar-track">
        <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
      </div>
      <div className="progress-label">{progress}% complete</div>
    </div>
  )
}

// ─── Not-ready panel ────────────────────────────────────────────────────────
function NotReadyPanel({ onGenerate }: { onGenerate: () => void }) {
  return (
    <div className="not-ready-panel">
      <h3>Demo Not Yet Generated</h3>
      <p>
        Click below to run the full denoising pipeline on synthetic test audio —
        generator, car, and aircraft noise types.
        Processing takes ~30–90 seconds.
      </p>
      <button className="btn-primary" onClick={onGenerate}>
        <span>⚗</span> Generate Demo
      </button>
      <p style={{ marginTop: '1.5rem', fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
        Uses synthetic harmonic test audio (f0 = 14 Hz, 6s per call)
      </p>
    </div>
  )
}

// ─── Science section ─────────────────────────────────────────────────────────
function ScienceSection() {
  return (
    <section className="section-alt">
      <div className="section container">
      <div className="section-header">
        <p className="section-label">Methodology</p>
        <h2 className="section-title">The Science</h2>
      </div>
      <div className="science-grid">
        <div className="science-card green-top">
          <span className="science-icon">〰</span>
          <h3 className="science-title">Harmonic Structure</h3>
          <p className="science-body">
            Elephant rumbles produce energy at <strong>exact integer multiples</strong> of a
            fundamental frequency (f0 = 8–25 Hz, harmonics up to 1 kHz).
            Critically, the <strong>2nd harmonic is stronger than the fundamental</strong> — so
            we detect f0 via subharmonic summation (NSSH), not direct peak picking.
          </p>
          <div className="science-formula">
            NSSH(f0) = Σ power(k·f0) / N<br/>
            k = 1…N, k·f0 ≤ 1000 Hz
          </div>
        </div>

        <div className="science-card cyan">
          <span className="science-icon">⧈</span>
          <h3 className="science-title">Comb Masking</h3>
          <p className="science-body">
            A <strong>time-varying soft comb filter</strong> is built at each detected f0 frame.
            It passes only frequencies at kf0 (±5 Hz bandwidth), rejecting everything else.
            Engine noise at 30 Hz, 60 Hz, 90 Hz — <strong>eliminated</strong>, even when it
            directly overlaps elephant harmonics.
          </p>
          <div className="science-formula">
            mask[b, t] = triangular window<br/>
            centered at round(k·f0 / hz_per_bin)<br/>
            n_fft=8192 → 5.4 Hz / bin
          </div>
        </div>

        <div className="science-card brown-top">
          <span className="science-icon">✕</span>
          <h3 className="science-title">vs Generic AI</h3>
          <p className="science-body">
            LALAL.AI and media.io are trained on <strong>speech and music (100–8000 Hz)</strong>.
            They have no concept of infrasonic content. Our method exploits the
            <strong> mathematical structure unique to elephant vocalizations</strong> —
            30% higher precision/recall than spectrogram cross-correlation at low SNR.
          </p>
          <div className="science-formula">
            Generic AI: trained on speech/music<br/>
            → fails below 50 Hz<br/>
            Ours: domain-specific NSSH + comb
          </div>
        </div>
      </div>
      </div>
    </section>
  )
}

// ─── Comparison section ──────────────────────────────────────────────────────
function ComparisonSection() {
  return (
    <section className="section container">
      <div className="section-header">
        <p className="section-label">Head-to-Head</p>
        <h2 className="section-title">Us vs LALAL.AI</h2>
      </div>
      <div className="comparison-grid">
        <div className="compare-card">
          <h3 className="compare-title">LALAL.AI / Generic AI Tools</h3>
          <ul className="compare-list">
            <li><span className="cross">✗</span> Trained on speech (300–3400 Hz) and music — no infrasonic knowledge</li>
            <li><span className="cross">✗</span> Cannot resolve 5 Hz frequency differences at 44.1 kHz with n_fft=1024</li>
            <li><span className="cross">✗</span> Treats engine harmonics at 30/60/90 Hz as "signal to preserve"</li>
            <li><span className="cross">✗</span> No awareness of elephant harmonic structure</li>
            <li><span className="cross">✗</span> Outputs are either over-suppressed (artifacts) or under-suppressed (noise retained)</li>
          </ul>
        </div>
        <div className="compare-card ours">
          <h3 className="compare-title">ElephantVoices Denoiser</h3>
          <ul className="compare-list">
            <li><span className="check">✓</span> n_fft=8192 → 5.4 Hz / bin — resolves individual elephant harmonics</li>
            <li><span className="check">✓</span> NSSH detects f0 even when the fundamental is fully masked by noise</li>
            <li><span className="check">✓</span> Time-varying comb mask tracks f0 glides across each call</li>
            <li><span className="check">✓</span> Noise type adaptive: stationary profile for generators, non-stationary for car/plane</li>
            <li><span className="check">✓</span> Per-call confidence scores — 212 calls ranked for researcher prioritization</li>
          </ul>
        </div>
      </div>
    </section>
  )
}

// ─── Specs bar ───────────────────────────────────────────────────────────────
function SpecsBar() {
  const specs = [
    { key: 'n_fft', val: '8192' },
    { key: 'resolution', val: '~5.4 Hz/bin' },
    { key: 'sample rate', val: '44.1 kHz' },
    { key: 'f0 range', val: '8–25 Hz' },
    { key: 'harmonics', val: 'up to 1000 Hz' },
    { key: 'method', val: 'NSSH + comb' },
    { key: 'reference', val: 'Zeppelzauer et al.' },
    { key: 'stack', val: 'Python + librosa' },
  ]
  return (
    <div className="specs-bar">
      <div className="specs-inner">
        {specs.map(s => (
          <div className="spec-item" key={s.key}>
            <span className="spec-key">{s.key}</span>
            <span style={{ color: 'var(--border)' }}>/</span>
            <span className="spec-val">{s.val}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Active result state type ─────────────────────────────────────────────────
interface ActiveResult {
  result: CallResult
  noisyUrl: string | null
  cleanUrl: string | null
}

// ─── Pipeline Visualizer Section ─────────────────────────────────────────────
function PipelineVisualizerSection() {
  return (
    <section className="section container">
      <div className="section-header">
        <p className="section-label">Interactive Pipeline</p>
        <h2 className="section-title">Animated Pipeline Visualizer</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.5rem', maxWidth: '60ch', marginLeft: 'auto', marginRight: 'auto' }}>
          Upload any WAV file and watch the full 7-stage denoising pipeline animate in real time —
          STFT, noise classification, HPSS, SHS f0 detection, comb masking, ISTFT reconstruction,
          and residual spectral gating.
        </p>
      </div>
      <PipelineVisualizer />
    </section>
  )
}

// ─── Upload section ───────────────────────────────────────────────────────────
function UploadSection({
  active,
  onActive,
}: {
  active: ActiveResult | null
  onActive: (a: ActiveResult) => void
}) {
  const handleComplete = useCallback(
    ({
      jobId,
      fileId,
      results,
    }: {
      jobId: string
      fileId: string
      file: File
      results: CallResult[]
    }) => {
      if (results.length === 0) return
      const r = results[0]
      // noisyUrl: serve the original uploaded audio from the API
      const noisyU = uploadAudioUrl(fileId)
      // cleanUrl: serve the cleaned result audio
      const cleanU = audioUrl(jobId, 0)
      onActive({ result: r, noisyUrl: noisyU, cleanUrl: cleanU })
    },
    [onActive],
  )

  return (
    <section className="section container">
      <div className="section-header">
        <p className="section-label">Upload Your Recording</p>
        <h2 className="section-title">Process a Field Recording</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.5rem' }}>
          Upload a WAV file — the pipeline will denoise it using harmonic comb masking
          and return spectrograms, SNR metrics, and A/B audio.
        </p>
      </div>
      <div className="upload-section">
        <UploadPanel onComplete={handleComplete} />
      </div>
      {active && (
        <div className="call-detail-section">
          <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '1rem', color: 'var(--brown)' }}>
            Result: {active.result.filename}
          </h3>
          <CallDetail
            result={active.result}
            noisyUrl={active.noisyUrl}
            cleanUrl={active.cleanUrl}
          />
        </div>
      )}
    </section>
  )
}

// ─── Batch results section ────────────────────────────────────────────────────
function BatchSection() {
  const [results, setResults] = useState<CallResult[]>([])
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    getBatchResults()
      .then((r) => setResults(r.results))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const selected = selectedIndex !== null ? results[selectedIndex] : null
  const rowCount = results.length

  return (
    <section className="section-alt">
      <div className="section container">
        {/* Collapsible header — clickable */}
        <button
          type="button"
          onClick={() => setExpanded(e => !e)}
          style={{
            width: '100%',
            background: 'transparent',
            border: 'none',
            padding: '0.5rem 0',
            cursor: 'pointer',
            textAlign: 'left',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem',
          }}
          aria-expanded={expanded}
        >
          <div style={{ flex: 1 }}>
            <p className="section-label" style={{ margin: 0 }}>Batch Analysis</p>
            <h2 className="section-title" style={{ margin: 0 }}>
              Confidence Dashboard
              {!loading && rowCount > 0 && (
                <span style={{
                  marginLeft: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.7rem',
                  fontWeight: 400,
                  color: 'var(--text-muted)',
                  letterSpacing: '0.05em',
                }}>
                  · {rowCount} calls
                </span>
              )}
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginTop: '0.4rem', marginBottom: 0 }}>
              {expanded
                ? 'Click any row to view its spectrogram, A/B audio, and comparison metrics.'
                : `${rowCount || 212} processed calls sorted by confidence. Click to expand.`}
            </p>
          </div>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '2.25rem',
              height: '2.25rem',
              borderRadius: '50%',
              background: 'var(--bg-warm)',
              border: '1px solid var(--border)',
              color: 'var(--brown)',
              fontSize: '1rem',
              fontFamily: 'var(--font-mono)',
              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.3s ease',
              flexShrink: 0,
            }}
            aria-hidden="true"
          >
            ▾
          </span>
        </button>

        {/* Collapsible body */}
        {expanded && (
          <div style={{ marginTop: '1.25rem' }}>
            <div className="confidence-section" style={{
              maxHeight: '60vh',
              overflowY: 'auto',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius, 8px)',
              background: 'var(--bg-card, #fff)',
            }}>
              {loading ? (
                <p style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', padding: '1rem' }}>
                  Loading batch results...
                </p>
              ) : results.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '1rem' }}>
                  No batch results yet. Run <code>python scripts/batch_process.py</code> to populate.
                </p>
              ) : (
                <ConfidenceTable
                  results={results}
                  selectedIndex={selectedIndex}
                  onSelect={setSelectedIndex}
                />
              )}
            </div>
            {selected && (
              <div className="call-detail-section" style={{ marginTop: '2rem' }}>
                <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '1rem', color: 'var(--brown)' }}>
                  Call Detail: {selected.filename}
                </h3>
                <CallDetail
                  result={selected}
                  noisyUrl={null}
                  cleanUrl={batchAudioUrl(selected.clean_wav_path)}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}

// ─── Multi-Speaker Section ──────────────────────────────────────────────────
function MultiSpeakerSection() {
  return (
    <section className="section container">
      <div className="section-header">
        <p className="section-label">Stretch Goal</p>
        <h2 className="section-title">Multi-Speaker Separation</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.5rem', maxWidth: '70ch' }}>
          When two elephants vocalize simultaneously, their harmonic series are independent —
          their trajectories may cross in the time-frequency plane. We detect multiple f<sub>0</sub>{' '}
          tracks via top-K subharmonic summation, then link them across time with a greedy
          pitch-continuity algorithm. Validated on a synthetic 14 Hz + 18 Hz two-caller mixture.
        </p>
      </div>
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '1.5rem',
        marginTop: '1rem'
      }}>
        <img
          src="/static/demo/multi_speaker_demo.png"
          alt="Multi-speaker separation spectrogram"
          style={{ width: '100%', maxWidth: '1200px', display: 'block', margin: '0 auto' }}
        />
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '1rem',
          marginTop: '1.5rem',
          maxWidth: '800px',
          marginLeft: 'auto',
          marginRight: 'auto'
        }}>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#FF4444', marginBottom: '0.25rem' }}>
              CALLER 1 · f₀ ≈ 14 Hz
            </div>
            <audio controls src="/static/demo/demo_caller_1.wav" style={{ width: '100%' }} />
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#4488FF', marginBottom: '0.25rem' }}>
              CALLER 2 · f₀ ≈ 18 Hz
            </div>
            <audio controls src="/static/demo/demo_caller_2.wav" style={{ width: '100%' }} />
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── Simple hash router ──────────────────────────────────────────────────────
type Route = 'home' | 'demo' | 'ml'

function useHashRoute(): [Route, (r: Route) => void] {
  const parse = (): Route => {
    const h = window.location.hash.replace(/^#\/?/, '')
    if (h === 'demo') return 'demo'
    if (h === 'ml') return 'ml'
    return 'home'
  }
  const [route, setRoute] = useState<Route>(parse())
  useEffect(() => {
    const handler = () => setRoute(parse())
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])
  const navigate = useCallback((r: Route) => {
    window.location.hash = r === 'home' ? '/' : `/${r}`
  }, [])
  return [route, navigate]
}

// ─── Header (shared) ─────────────────────────────────────────────────────────
function AppHeader({ route, navigate }: { route: Route; navigate: (r: Route) => void }) {
  return (
    <>
      <div className="top-bar" />
      <header className="header">
        <div className="header-inner">
          <a
            href="#/"
            className="logo"
            onClick={(e) => { e.preventDefault(); navigate('home') }}
            style={{ textDecoration: 'none', cursor: 'pointer' }}
          >
            <span className="logo-mark">🐘</span>
            <div>
              <span className="logo-text">ElephantVoices Denoiser</span>
              <span className="logo-sub">Harmonic Comb Masking · Infrasonic Bioacoustics</span>
            </div>
          </a>
          <div className="header-right">
            <nav style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', marginRight: '1.5rem' }}>
              <a
                href="#/"
                onClick={(e) => { e.preventDefault(); navigate('home') }}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: route === 'home' ? 'var(--orange)' : 'var(--text-muted)',
                  textDecoration: 'none',
                  cursor: 'pointer',
                  borderBottom: route === 'home' ? '2px solid var(--orange)' : '2px solid transparent',
                  paddingBottom: '2px',
                }}
              >
                Home
              </a>
              <a
                href="#/demo"
                onClick={(e) => { e.preventDefault(); navigate('demo') }}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: route === 'demo' ? 'var(--orange)' : 'var(--text-muted)',
                  textDecoration: 'none',
                  cursor: 'pointer',
                  borderBottom: route === 'demo' ? '2px solid var(--orange)' : '2px solid transparent',
                  paddingBottom: '2px',
                }}
              >
                Demo
              </a>
              <a
                href="#/ml"
                onClick={(e) => { e.preventDefault(); navigate('ml') }}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: route === 'ml' ? 'var(--orange)' : 'var(--text-muted)',
                  textDecoration: 'none',
                  cursor: 'pointer',
                  borderBottom: route === 'ml' ? '2px solid var(--orange)' : '2px solid transparent',
                  paddingBottom: '2px',
                }}
              >
                ML vs Ours
              </a>
            </nav>
            <span className="tagline">HackSMU 2026 · Southern Methodist University</span>
            <span className="badge">HackSMU 2026</span>
          </div>
        </div>
      </header>
    </>
  )
}

// ─── Home Page ───────────────────────────────────────────────────────────────
function HomePage({ navigate }: { navigate: (r: Route) => void }) {
  return (
    <>
      {/* Hero */}
      <div className="hero">
        <div className="hero-inner hero-split">
          <div className="hero-text">
            <div className="hero-eyebrow fade-up fade-up-1">
              ElephantVoices Field Recording Denoiser
            </div>
            <h1 className="hero-headline fade-up fade-up-2">
              We don't just<br />
              <span className="accent">remove noise.</span>
            </h1>
            <p className="hero-sub fade-up fade-up-3">
              Extracting elephant calls from noisy field recordings using their unique harmonic structure.
            </p>
            <div className="hero-actions fade-up fade-up-4">
              <button className="btn-primary" onClick={() => navigate('demo')}>
                ⚗ Launch Demo →
              </button>
              <div className="stat-pills">
                <div className="stat-pill"><strong>212</strong> calls processed</div>
                <div className="stat-pill"><strong>174</strong> tests passing</div>
                <div className="stat-pill"><strong>3</strong> noise types</div>
              </div>
            </div>
          </div>

          {/* 3D Elephant Model */}
          <div className="elephant-viewer-wrapper fade-up fade-up-4">
            <ElephantViewer />
          </div>
        </div>
      </div>

      <div className="divider" />
      <SpecsBar />
      <div className="divider" />
      <ScienceSection />
      <div className="divider" />
      <ComparisonSection />
      <div className="divider" />

      {/* Call-to-action */}
      <section className="section container" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
        <div className="section-header">
          <p className="section-label">Interactive Demo</p>
          <h2 className="section-title">See It In Action</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginTop: '0.75rem', maxWidth: '60ch', marginLeft: 'auto', marginRight: 'auto' }}>
            Before/after spectrograms from real ElephantVoices recordings, upload your own WAV,
            browse all 212 processed calls, and watch multi-speaker separation on overlapping rumbles.
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={() => navigate('demo')}
          style={{ marginTop: '2rem', fontSize: '1rem', padding: '0.9rem 2rem' }}
        >
          Open the Demo →
        </button>
      </section>
    </>
  )
}

// ─── Demo Page ───────────────────────────────────────────────────────────────
function DemoPage({
  status, jobProgress, jobMessage, metadata,
  activeUpload, setActiveUpload, handleGenerate,
}: {
  status: DemoStatus
  jobProgress: number
  jobMessage: string
  metadata: Metadata | null
  activeUpload: ActiveResult | null
  setActiveUpload: (v: ActiveResult | null) => void
  handleGenerate: () => void
}) {
  return (
    <>
      {/* Compact demo hero */}
      <div className="hero" style={{ minHeight: 'auto', padding: '3rem 2rem 2rem' }}>
        <div className="hero-inner">
          <div className="hero-eyebrow fade-up fade-up-1">Live Demo</div>
          <h1 className="hero-headline fade-up fade-up-2" style={{ fontSize: '2.5rem' }}>
            Interactive <span className="accent">Spectrograms</span>
          </h1>
          <p className="hero-sub fade-up fade-up-3" style={{ maxWidth: '60ch' }}>
            Real ElephantVoices recordings. Real denoising. Upload your own, browse all 212,
            or watch multi-speaker separation.
          </p>
        </div>
      </div>

      <div className="divider" />

      {/* Demo section */}
      <section className="section container">
        <div className="section-header">
          <p className="section-label">Before &amp; After · Real Data</p>
          <h2 className="section-title">Three Noise Types</h2>
          {status === 'ready' && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.5rem' }}>
              3-panel spectrograms: Original · Comb Mask · Cleaned — y-axis 0–500 Hz
            </p>
          )}
        </div>
        {status === 'checking' && (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            Checking demo status...
          </div>
        )}
        {status === 'not_ready' && (
          <div style={{ padding: '3rem', textAlign: 'center' }}>
            <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Demo assets not yet generated.
            </p>
            <button className="btn-primary" onClick={handleGenerate}>
              ⚗ Generate Demo Now
            </button>
          </div>
        )}
        {status === 'generating' && (
          <div style={{ padding: '3rem', textAlign: 'center' }}>
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', marginBottom: '1rem' }}>
              {jobMessage || 'Generating...'} ({jobProgress}%)
            </p>
            <div style={{
              width: '100%', maxWidth: '400px', margin: '0 auto',
              height: '4px', background: 'var(--border)', borderRadius: '2px', overflow: 'hidden',
            }}>
              <div style={{
                width: `${jobProgress}%`, height: '100%',
                background: 'var(--orange)', transition: 'width 0.3s',
              }} />
            </div>
          </div>
        )}
        {status === 'ready' && (
          <div className="demo-grid">
            {NOISE_TYPES.map((nt) => (
              <DemoCard key={nt} noiseType={nt} metadata={metadata} />
            ))}
          </div>
        )}
        {status === 'error' && (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#ff6b6b' }}>
            Error loading demo. Check that backend is running at /api/demo/status.
          </div>
        )}
      </section>

      <div className="divider" />
      <PipelineVisualizerSection />
      <div className="divider" />
      <BatchSection />
      <div className="divider" />
      <MultiSpeakerSection />
    </>
  )
}

// ─── ML Comparison Page ──────────────────────────────────────────────────────
type MLMetrics = {
  [key in NoiseType]?: {
    baseline: { harmonic_dominance: number; approach: string }
    ml_finetuned?: { harmonic_dominance: number; approach: string }
    ours: { harmonic_dominance: number; approach: string }
    improvement_pct: number
    f0_median_hz: number
    engine_hz_estimate: number
  }
}

function MLComparePage() {
  const [metrics, setMetrics] = useState<MLMetrics | null>(null)

  useEffect(() => {
    fetch('/static/demo/ml_comparison_metrics.json')
      .then(r => r.ok ? r.json() : null)
      .then(setMetrics)
      .catch(() => {})
  }, [])

  return (
    <>
      {/* Hero */}
      <div className="hero" style={{ minHeight: 'auto', padding: '3rem 2rem 2rem' }}>
        <div className="hero-inner">
          <div className="hero-eyebrow fade-up fade-up-1">Scientific Comparison</div>
          <h1 className="hero-headline fade-up fade-up-2" style={{ fontSize: '2.5rem' }}>
            Generic ML vs <span className="accent">Domain Priors</span>
          </h1>
          <p className="hero-sub fade-up fade-up-3" style={{ maxWidth: '72ch' }}>
            What happens when you throw a generic spectral-gating denoiser at an elephant rumble,
            compared to our approach that knows elephants have a <strong>strict integer-multiple harmonic series</strong>?
            Both run on the <strong>same real ElephantVoices recording</strong>. Same input, different priors,
            different outputs.
          </p>
        </div>
      </div>

      <div className="divider" />

      {/* The pitch bar — 3 approaches */}
      <section className="section container">
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '1rem',
          marginBottom: '2rem',
        }}>
          <div style={{
            padding: '1.5rem',
            background: 'rgba(255, 124, 42, 0.08)',
            border: '1px solid rgba(255, 124, 42, 0.3)',
            borderRadius: '8px',
          }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Generic baseline
            </div>
            <div style={{ fontWeight: 700, color: 'var(--orange)', fontSize: '1.05rem', marginBottom: '0.5rem' }}>
              noisereduce (stationary)
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
              Generic spectral-gating. Zero domain knowledge. What 99% of bioacoustic
              projects use. Preserves any strong harmonic structure — including engines.
            </p>
          </div>
          <div style={{
            padding: '1.5rem',
            background: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            borderRadius: '8px',
          }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Fine-tuned ML
            </div>
            <div style={{ fontWeight: 700, color: 'var(--blue)', fontSize: '1.05rem', marginBottom: '0.5rem' }}>
              sklearn MLP (128·64)
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
              Real ML model — MLPRegressor trained on 80 real ElephantVoices rumbles (16 k
              frames) to predict our comb mask. Learns an approximation of the harmonic prior
              from data.
            </p>
          </div>
          <div style={{
            padding: '1.5rem',
            background: 'rgba(0, 200, 100, 0.08)',
            border: '1px solid rgba(0, 200, 100, 0.3)',
            borderRadius: '8px',
          }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Our approach
            </div>
            <div style={{ fontWeight: 700, color: '#00c864', fontSize: '1.05rem', marginBottom: '0.5rem' }}>
              HPSS + SHS + Comb + noisereduce
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
              Domain-specific classical DSP. Detects elephant f₀ via subharmonic summation,
              builds a narrow comb mask at k·f₀ — encodes the harmonic prior explicitly.
            </p>
          </div>
        </div>
        <div style={{
          padding: '1rem 1.25rem',
          background: 'var(--bg-warm)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          marginBottom: '2rem',
        }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.68rem',
            color: 'var(--text-muted)',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
          }}>
            Metric
          </span>
          <span style={{ margin: '0 0.75rem', color: 'var(--text-muted)' }}>·</span>
          <strong style={{ fontSize: '0.88rem' }}>Harmonic Dominance</strong>
          <span style={{ marginLeft: '0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Fraction of 0–500 Hz energy sitting on k·f₀ peaks (higher = cleaner harmonic extraction)
          </span>
        </div>
      </section>

      {/* Comparison rows */}
      {(['generator', 'car', 'plane'] as NoiseType[]).map((nt) => {
        const cfg = NOISE_CONFIG[nt]
        const m = metrics?.[nt]
        return (
          <section key={nt} className="section container" style={{ paddingTop: '1rem' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              marginBottom: '1rem',
            }}>
              <span
                className="noise-badge"
                style={{
                  color: cfg.color,
                  background: cfg.dimColor,
                  border: `1px solid ${cfg.borderColor}`,
                }}
              >
                <span>{cfg.icon}</span>
                {cfg.label}
              </span>
              {m && (
                <div style={{ display: 'flex', gap: '1.25rem', marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '0.76rem', flexWrap: 'wrap' }}>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Baseline: </span>
                    <strong style={{ color: 'var(--orange)' }}>{(m.baseline.harmonic_dominance * 100).toFixed(1)}%</strong>
                  </div>
                  {m.ml_finetuned && (
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>ML: </span>
                      <strong style={{ color: 'var(--blue)' }}>{(m.ml_finetuned.harmonic_dominance * 100).toFixed(1)}%</strong>
                    </div>
                  )}
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Ours: </span>
                    <strong style={{ color: '#00c864' }}>{(m.ours.harmonic_dominance * 100).toFixed(1)}%</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Δ vs baseline: </span>
                    <strong style={{ color: '#00c864' }}>+{m.improvement_pct}%</strong>
                  </div>
                </div>
              )}
            </div>
            <div style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              padding: '1rem',
            }}>
              <img
                src={`/static/demo/ml_comparison_${nt}.png`}
                alt={`${nt} ML comparison`}
                style={{ width: '100%', display: 'block', borderRadius: '4px' }}
              />
              {m && (
                <p style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.72rem',
                  color: 'var(--text-muted)',
                  marginTop: '0.75rem',
                  marginBottom: 0,
                }}>
                  Baseline preserves <strong style={{ color: 'var(--orange)' }}>~{m.engine_hz_estimate.toFixed(1)} Hz engine noise</strong>.
                  Our approach preserves only elephant harmonics at <strong style={{ color: '#00c864' }}>k·f₀ = k·{m.f0_median_hz.toFixed(1)} Hz</strong>.
                </p>
              )}
            </div>
          </section>
        )
      })}

      {/* Summary */}
      {/* Aggregate results table */}
      <section className="section container" style={{ marginTop: '2rem' }}>
        <div className="section-header" style={{ marginBottom: '1rem' }}>
          <p className="section-label">Results</p>
          <h2 className="section-title" style={{ fontSize: '1.5rem' }}>Aggregate Metrics</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.4rem' }}>
            Harmonic dominance (%) on the same three real ElephantVoices recordings used above.
            Higher = cleaner harmonic extraction.
          </p>
        </div>
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          overflow: 'hidden',
        }}>
          <table style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.85rem',
          }}>
            <thead>
              <tr style={{ background: 'var(--bg-warm)', borderBottom: '1px solid var(--border)' }}>
                <th style={{ padding: '0.8rem 1rem', textAlign: 'left', fontSize: '0.7rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Noise Type</th>
                <th style={{ padding: '0.8rem 1rem', textAlign: 'right', fontSize: '0.7rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--orange)' }}>Baseline</th>
                <th style={{ padding: '0.8rem 1rem', textAlign: 'right', fontSize: '0.7rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--blue)' }}>ML (fine-tuned)</th>
                <th style={{ padding: '0.8rem 1rem', textAlign: 'right', fontSize: '0.7rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: '#00c864' }}>Ours</th>
                <th style={{ padding: '0.8rem 1rem', textAlign: 'right', fontSize: '0.7rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Δ vs Baseline</th>
                <th style={{ padding: '0.8rem 1rem', textAlign: 'right', fontSize: '0.7rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Winner</th>
              </tr>
            </thead>
            <tbody>
              {(['generator', 'car', 'plane'] as NoiseType[]).map((nt) => {
                const m = metrics?.[nt]
                const cfg = NOISE_CONFIG[nt]
                if (!m) return null
                const baseline = m.baseline.harmonic_dominance * 100
                const ours = m.ours.harmonic_dominance * 100
                const ml = m.ml_finetuned ? m.ml_finetuned.harmonic_dominance * 100 : null
                const best = Math.max(baseline, ours, ml ?? 0)
                const winnerLabel = best === ours ? 'Ours' : best === (ml ?? -1) ? 'ML' : 'Baseline'
                const winnerColor = winnerLabel === 'Ours' ? '#00c864' : winnerLabel === 'ML' ? 'var(--blue)' : 'var(--orange)'
                return (
                  <tr key={nt} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '0.85rem 1rem' }}>
                      <span style={{ color: cfg.color, fontWeight: 700 }}>{cfg.icon} {cfg.label}</span>
                    </td>
                    <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: 'var(--orange)' }}>
                      {baseline.toFixed(1)}%
                    </td>
                    <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: 'var(--blue)' }}>
                      {ml !== null ? `${ml.toFixed(1)}%` : '—'}
                    </td>
                    <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#00c864', fontWeight: 700 }}>
                      {ours.toFixed(1)}%
                    </td>
                    <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#00c864' }}>
                      +{(ours - baseline).toFixed(1)}%
                    </td>
                    <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: winnerColor, fontWeight: 700 }}>
                      {winnerLabel}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Honest result — the interesting finding */}
      <section className="section container" style={{ marginTop: '1.5rem' }}>
        <div style={{
          padding: '1.5rem 1.75rem',
          background: 'rgba(59, 130, 246, 0.05)',
          border: '1px solid rgba(59, 130, 246, 0.25)',
          borderLeft: '4px solid var(--blue)',
          borderRadius: '8px',
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            color: 'var(--blue)',
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            marginBottom: '0.6rem',
            fontWeight: 700,
          }}>
            ⚡ Honest result
          </div>
          <p style={{ fontSize: '0.92rem', color: 'var(--text)', lineHeight: 1.65, marginBottom: '0.75rem' }}>
            The fine-tuned sklearn MLPRegressor <strong style={{ color: 'var(--blue)' }}>matches or slightly beats</strong> our
            explicit approach on <strong>car</strong> and <strong>plane</strong> noise after training on 80 real rumbles
            (16k frames) for ~2 minutes. It learns an approximation of the comb mask from the data.
          </p>
          <p style={{ fontSize: '0.92rem', color: 'var(--text)', lineHeight: 1.65, marginBottom: '0.75rem' }}>
            But this is the <strong>pitch point</strong>, not a defeat:
          </p>
          <ul style={{ fontSize: '0.88rem', color: 'var(--text)', lineHeight: 1.7, paddingLeft: '1.25rem', marginBottom: '0.75rem' }}>
            <li>
              Our classical approach <strong style={{ color: '#00c864' }}>wins on generator noise</strong> — the case where
              engine harmonics directly overlap elephant harmonics and the mathematical prior matters most.
            </li>
            <li>
              Our approach needs <strong>zero training data</strong>. It works on any species with a harmonic series
              (whales, dolphins, birds) by tuning 3 parameters (f₀ range, harmonic count, comb bandwidth).
            </li>
            <li>
              The ML model needs <strong>80 labeled rumbles per species</strong> and a 2-minute fit. Try that on
              an endangered species with 10 recordings.
            </li>
            <li>
              The ML model still <strong style={{ color: 'var(--blue)' }}>imitates</strong> our comb mask — it was
              trained with our output as the target. When the explicit approach is already correct, the learned
              approximation approaches its ceiling. The ML model cannot exceed the algorithm it was distilled from.
            </li>
          </ul>
          <p style={{ fontSize: '0.92rem', color: 'var(--text)', lineHeight: 1.65, fontWeight: 700, marginBottom: 0 }}>
            Domain priors give you the ceiling for free. ML gives you an expensive approximation that only gets
            there with enough data.
          </p>
        </div>
      </section>

      {/* Final takeaway */}
      <section className="section container" style={{ marginTop: '1.5rem' }}>
        <div style={{
          padding: '2rem',
          background: 'rgba(0, 200, 100, 0.05)',
          border: '1px solid rgba(0, 200, 100, 0.2)',
          borderRadius: '8px',
          textAlign: 'center',
        }}>
          <h3 style={{ fontFamily: 'var(--font-display)', color: '#00c864', marginBottom: '0.75rem' }}>
            The takeaway
          </h3>
          <p style={{ fontSize: '0.95rem', color: 'var(--text)', maxWidth: '72ch', margin: '0 auto' }}>
            Generic spectral gating is the default because it's easy. But it has no idea
            what an elephant sounds like, and it keeps any strong harmonic structure — including
            engine noise. Our approach knows that elephant rumbles live on a strict k·f₀ series
            anchored at 10–25 Hz, so we build a mask around exactly those bins and throw everything
            else away.
          </p>
          <p style={{
            fontSize: '0.95rem',
            color: 'var(--text)',
            maxWidth: '72ch',
            margin: '1rem auto 0',
            fontWeight: 700,
          }}>
            Same input. Same compute. Different priors. Measurably cleaner output.
          </p>
        </div>
      </section>
    </>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [status, setStatus] = useState<DemoStatus>('checking')
  const [jobProgress, setJobProgress] = useState(0)
  const [jobMessage, setJobMessage] = useState('')
  const [metadata, setMetadata] = useState<Metadata | null>(null)
  const [activeUpload, setActiveUpload] = useState<ActiveResult | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const fetchMetadata = useCallback(async () => {
    try {
      const res = await fetch('/api/demo/metadata')
      if (res.ok) setMetadata(await res.json())
    } catch {}
  }, [])

  const checkStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/demo/status')
      if (!res.ok) { setStatus('error'); return }
      const data: StatusResponse = await res.json()

      setJobProgress(data.job.progress)
      setJobMessage(data.job.message)

      if (data.ready) {
        stopPolling()
        setStatus('ready')
        fetchMetadata()
      } else if (data.job.status === 'running') {
        setStatus('generating')
      } else if (data.job.status === 'error') {
        stopPolling()
        setStatus('error')
      } else {
        setStatus('not_ready')
      }
    } catch {
      setStatus('error')
    }
  }, [stopPolling, fetchMetadata])

  useEffect(() => {
    checkStatus()
    return stopPolling
  }, [checkStatus, stopPolling])

  const handleGenerate = useCallback(async () => {
    setStatus('generating')
    setJobProgress(0)
    setJobMessage('Starting...')
    try {
      await fetch('/api/demo/generate', { method: 'POST' })
      pollRef.current = setInterval(checkStatus, 2000)
    } catch {
      setStatus('error')
    }
  }, [checkStatus])

  const [route, navigate] = useHashRoute()

  return (
    <div>
      <AppHeader route={route} navigate={navigate} />

      {route === 'home' && <HomePage navigate={navigate} />}
      {route === 'ml' && <MLComparePage />}
      {route === 'demo' && (
        <DemoPage
          status={status}
          jobProgress={jobProgress}
          jobMessage={jobMessage}
          metadata={metadata}
          activeUpload={activeUpload}
          setActiveUpload={setActiveUpload}
          handleGenerate={handleGenerate}
        />
      )}

      {/* Footer */}
      <footer className="footer">
        <div className="footer-inner">
          <div className="footer-left">
            Built at <strong>HackSMU 2026</strong> · Southern Methodist University ·{' '}
            <span style={{ color: 'var(--green)', fontFamily: 'var(--font-mono)', fontSize: '0.72rem' }}>
              🐘 ElephantVoices Denoiser
            </span>
          </div>
          <div className="footer-links">
            <a className="footer-link" href="https://github.com/gt12889/hacksmu26" target="_blank" rel="noreferrer">
              GitHub ↗
            </a>
            <a
              className="footer-link"
              href="#/demo"
              onClick={(e) => { e.preventDefault(); navigate('demo') }}
            >
              Launch Demo
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}
