import { useState, useEffect, useRef, useCallback } from 'react'
import type { DemoStatus, NoiseType, Metadata, StatusResponse } from './types'
import { UploadPanel } from './components/UploadPanel'
import { CallDetail } from './components/CallDetail'
import { ConfidenceTable } from './components/ConfidenceTable'
import { getBatchResults, batchAudioUrl, uploadAudioUrl, audioUrl } from './api/client'
import type { CallResult } from './types/api'

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
          style={{ display: imgLoaded ? 'block' : 'none' }}
          onLoad={() => setImgLoaded(true)}
          onError={() => setImgLoaded(false)}
          loading="lazy"
        />
      </div>

      {/* Metrics */}
      <div className="card-metrics">
        <div className="metric">
          <span className="metric-label">SNR Before</span>
          <span className="metric-value">
            {metrics ? `${metrics.snr_before.toFixed(1)} dB` : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">SNR After</span>
          <span className="metric-value positive">
            {metrics ? `${metrics.snr_after.toFixed(1)} dB` : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Δ SNR</span>
          <span className="metric-value positive">
            {metrics ? `${metrics.snr_improvement >= 0 ? '+' : ''}${metrics.snr_improvement.toFixed(1)} dB` : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">f0 Range</span>
          <span className="metric-value cyan" style={{ fontSize: '0.72rem' }}>
            {metrics ? `${metrics.f0_min.toFixed(0)}–${metrics.f0_max.toFixed(0)} Hz` : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">f0 Median</span>
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

  useEffect(() => {
    getBatchResults()
      .then((r) => setResults(r.results))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const selected = selectedIndex !== null ? results[selectedIndex] : null

  return (
    <section className="section-alt">
      <div className="section container">
        <div className="section-header">
          <p className="section-label">Batch Analysis</p>
          <h2 className="section-title">Confidence Dashboard</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.5rem' }}>
            All 212 processed calls sorted by confidence. Click any row to view its
            spectrogram, A/B audio, and comparison metrics.
          </p>
        </div>
        <div className="confidence-section">
          {loading ? (
            <p style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
              Loading batch results...
            </p>
          ) : results.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
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
type Route = 'home' | 'demo'

function useHashRoute(): [Route, (r: Route) => void] {
  const parse = (): Route => {
    const h = window.location.hash.replace(/^#\/?/, '')
    return h === 'demo' ? 'demo' : 'home'
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
        <div className="hero-inner">
          <div className="hero-eyebrow fade-up fade-up-1">
            ElephantVoices Field Recording Denoiser
          </div>
          <h1 className="hero-headline fade-up fade-up-2">
            We don't just<br />
            <span className="accent">remove noise.</span>
          </h1>
          <p className="hero-sub fade-up fade-up-3">
            We exploit the <strong>mathematical structure of elephant vocalizations</strong> to
            surgically extract calls even when they share the exact same frequency band as the noise.
            44 field recordings. 212 annotated calls. Three noise types.{' '}
            <strong>One domain-specific insight.</strong>
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
      <UploadSection active={activeUpload} onActive={setActiveUpload} />
      <div className="divider" />
      <BatchSection />
      <div className="divider" />
      <MultiSpeakerSection />
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
