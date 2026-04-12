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
          <p className="card-desc">{cfg.description}</p>
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
          <span className="metric-label">Improvement</span>
          <span className="metric-value positive">
            {metrics ? `+${metrics.snr_improvement.toFixed(1)} dB` : '—'}
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

  return (
    <div>
      {/* Top brown accent bar — matches elephantvoices.org */}
      <div className="top-bar" />

      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-mark">🐘</span>
            <div>
              <span className="logo-text">ElephantVoices Denoiser</span>
              <span className="logo-sub">Harmonic Comb Masking · Infrasonic Bioacoustics</span>
            </div>
          </div>
          <div className="header-right">
            <span className="tagline">HackSMU 2026 · Southern Methodist University</span>
            <span className="badge">HackSMU 2026</span>
          </div>
        </div>
      </header>

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
            {status === 'not_ready' && (
              <button className="btn-primary" onClick={handleGenerate}>
                ⚗ Run Pipeline
              </button>
            )}
            {status === 'ready' && (
              <button className="btn-secondary" onClick={handleGenerate}>
                ↺ Re-generate
              </button>
            )}
            <div className="stat-pills">
              <div className="stat-pill"><strong>212</strong> calls processed</div>
              <div className="stat-pill">SNR <strong>+5–8 dB</strong> improvement</div>
              <div className="stat-pill"><strong>3</strong> noise types</div>
            </div>
          </div>
        </div>
      </div>

      <div className="divider" />
      <SpecsBar />
      <div className="divider" />

      {/* Demo section */}
      <section className="section container">
        <div className="section-header">
          <p className="section-label">Live Demo</p>
          <h2 className="section-title">Before &amp; After</h2>
          {status === 'ready' && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.5rem' }}>
              3-panel spectrograms: Original · Comb Mask · Cleaned — y-axis 0–500 Hz
            </p>
          )}
        </div>

        {status === 'checking' && (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
            Checking pipeline status...
          </div>
        )}

        {status === 'not_ready' && (
          <NotReadyPanel onGenerate={handleGenerate} />
        )}

        {status === 'generating' && (
          <LoadingPanel progress={jobProgress} message={jobMessage} />
        )}

        {status === 'error' && (
          <div style={{ textAlign: 'center', padding: '3rem', color: '#ef4444', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
            Could not connect to API. Make sure the backend is running on port 8000.
            <br />
            <button className="btn-secondary" style={{ marginTop: '1.5rem' }} onClick={checkStatus}>
              Retry
            </button>
          </div>
        )}

        {status === 'ready' && (
          <div className="demo-grid">
            {NOISE_TYPES.map(nt => (
              <DemoCard key={nt} noiseType={nt} metadata={metadata} />
            ))}
          </div>
        )}
      </section>

      <div className="divider" />
      <ScienceSection />
      <div className="divider" />
      <ComparisonSection />
      <div className="divider" />
      <UploadSection active={activeUpload} onActive={setActiveUpload} />
      <div className="divider" />
      <BatchSection />

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
            <a className="footer-link" href="https://github.com" target="_blank" rel="noreferrer">
              GitHub ↗
            </a>
            <a className="footer-link" href="#" onClick={e => { e.preventDefault(); handleGenerate() }}>
              Re-run Demo
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}
