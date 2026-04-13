import type { CallResult } from '../types/api'

export interface ComparisonPanelProps {
  result: CallResult
}

export function ComparisonPanel({ result }: ComparisonPanelProps) {
  const improvement = result.snr_after_db - result.snr_before_db
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr',
        gap: 16,
        margin: '16px 0',
      }}
    >
      <Column
        title="Original"
        snr={result.snr_before_db}
        note="Raw field recording (contaminated)"
      />
      <Column
        title="LALAL.AI"
        snr={null}
        note="Generic ML denoiser — fails on infrasonic content. Trained on speech/music, not elephant rumbles."
        placeholder
      />
      <Column
        title="Our Result (Harmonic Comb)"
        snr={result.snr_after_db}
        note={`SNR improvement: +${improvement.toFixed(1)} dB`}
        highlight
      />
    </div>
  )
}

function Column(props: {
  title: string
  snr: number | null
  note: string
  highlight?: boolean
  placeholder?: boolean
}) {
  return (
    <div
      style={{
        padding: 12,
        background: props.highlight ? '#1a2d1a' : '#16161d',
        borderRadius: 6,
        border: props.placeholder ? '1px dashed #444' : '1px solid #2a2a33',
      }}
    >
      <h3 style={{ marginTop: 0 }}>{props.title}</h3>
      <div style={{ fontSize: 24, fontWeight: 'bold' }}>
        {props.snr !== null ? `${props.snr.toFixed(1)} dB SNR` : 'N/A'}
      </div>
      <p style={{ opacity: 0.7, fontSize: 13 }}>{props.note}</p>
    </div>
  )
}
