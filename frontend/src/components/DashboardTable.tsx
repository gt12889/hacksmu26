import { useState, useMemo } from 'react'
import type { DashboardRow } from '../types/api'

// ── Brand color tokens for each approach ──────────────────────────────────────
const APPROACH_COLORS: Record<string, string> = {
  baseline: 'var(--orange)',
  sklearn: 'var(--blue)',
  pytorch: 'var(--purple)',
  dsp: 'var(--green)',
}

const APPROACH_LABELS: Record<string, string> = {
  baseline: 'Baseline',
  sklearn: 'ML sklearn',
  pytorch: 'ML PyTorch',
  dsp: 'DSP',
}

type SortKey =
  | 'call_index'
  | 'filename'
  | 'noise_type'
  | 'f0_median_hz'
  | 'hd_baseline'
  | 'hd_sklearn'
  | 'hd_pytorch'
  | 'hd_dsp'
  | 'best_approach'

const NOISE_FILTERS = ['all', 'generator', 'car', 'plane', 'vehicle', 'airplane']

export interface DashboardTableProps {
  rows: DashboardRow[]
  selectedIndex: number | null
  onSelect: (callIndex: number) => void
}

export function DashboardTable({ rows, selectedIndex, onSelect }: DashboardTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('call_index')
  const [sortDesc, setSortDesc] = useState(false)
  const [noiseFilter, setNoiseFilter] = useState('all')
  const [filterText, setFilterText] = useState('')

  // Win counts
  const winCounts = useMemo(() => {
    const counts: Record<string, number> = { baseline: 0, sklearn: 0, pytorch: 0, dsp: 0 }
    for (const r of rows) {
      if (r.best_approach in counts) counts[r.best_approach]++
    }
    return counts
  }, [rows])

  const sortedRows = useMemo(() => {
    let filtered = rows

    // noise type filter
    if (noiseFilter !== 'all') {
      filtered = filtered.filter((r) =>
        r.noise_type.toLowerCase().includes(noiseFilter.toLowerCase()) ||
        r.filename.toLowerCase().includes(noiseFilter.toLowerCase())
      )
    }

    // text filter
    if (filterText.trim()) {
      const q = filterText.toLowerCase()
      filtered = filtered.filter(
        (r) => r.filename.toLowerCase().includes(q) || r.noise_type.toLowerCase().includes(q)
      )
    }

    // sort
    const sorted = [...filtered].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (typeof av === 'number' && typeof bv === 'number') {
        return sortDesc ? bv - av : av - bv
      }
      return sortDesc
        ? String(bv).localeCompare(String(av))
        : String(av).localeCompare(String(bv))
    })
    return sorted
  }, [rows, sortKey, sortDesc, noiseFilter, filterText])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDesc((d) => !d)
    else { setSortKey(key); setSortDesc(key !== 'call_index') }
  }

  const thStyle = (key: SortKey): React.CSSProperties => ({
    cursor: 'pointer',
    userSelect: 'none',
    whiteSpace: 'nowrap',
    padding: '8px 10px',
    textAlign: 'center' as const,
    fontSize: '0.72rem',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.05em',
    borderBottom: '2px solid var(--border)',
    color: sortKey === key ? 'var(--green)' : 'var(--text-muted)',
  })

  const hdCell = (value: number, approach: string, isBest: boolean): React.CSSProperties => ({
    color: APPROACH_COLORS[approach] ?? 'inherit',
    fontWeight: isBest ? 700 : 400,
    background: isBest ? `${APPROACH_COLORS[approach]}18` : undefined,
    borderRadius: isBest ? 4 : undefined,
    padding: '4px 8px',
    textAlign: 'center' as const,
    fontFamily: 'var(--font-mono)',
    fontSize: '0.82rem',
  })

  return (
    <div>
      {/* Summary bar */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '0.5rem',
        padding: '10px 12px',
        borderBottom: '1px solid var(--border)',
        fontSize: '0.78rem',
        fontFamily: 'var(--font-mono)',
        alignItems: 'center',
      }}>
        <span style={{ color: 'var(--text-muted)' }}>{rows.length} calls</span>
        <span style={{ color: 'var(--border)' }}>·</span>
        {(['dsp', 'pytorch', 'sklearn', 'baseline'] as const).map((ap) => (
          <span key={ap} style={{ color: APPROACH_COLORS[ap] }}>
            {APPROACH_LABELS[ap]} wins {winCounts[ap] ?? 0}
          </span>
        ))}
      </div>

      {/* Filters */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '0.5rem',
        padding: '8px 12px',
        borderBottom: '1px solid var(--border)',
        alignItems: 'center',
      }}>
        <input
          placeholder="Filter by filename..."
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          style={{
            padding: '5px 10px',
            fontSize: '0.8rem',
            fontFamily: 'var(--font-mono)',
            background: 'var(--bg-warm)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            color: 'var(--text)',
            width: 220,
          }}
        />
        <div style={{ display: 'flex', gap: '0.3rem' }}>
          {NOISE_FILTERS.map((nf) => (
            <button
              key={nf}
              onClick={() => setNoiseFilter(nf)}
              style={{
                padding: '4px 10px',
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
                borderRadius: 4,
                border: `1px solid ${noiseFilter === nf ? 'var(--green)' : 'var(--border)'}`,
                background: noiseFilter === nf ? 'var(--green)20' : 'var(--bg-warm)',
                color: noiseFilter === nf ? 'var(--green)' : 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              {nf}
            </button>
          ))}
        </div>
        <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {sortedRows.length} / {rows.length} calls shown
        </span>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ position: 'sticky', top: 0, background: 'var(--bg-card, #1a1a2e)', zIndex: 1 }}>
              <th style={thStyle('call_index')} onClick={() => toggleSort('call_index')}>#</th>
              <th style={{ ...thStyle('filename'), textAlign: 'left' }} onClick={() => toggleSort('filename')}>Filename</th>
              <th style={thStyle('noise_type')} onClick={() => toggleSort('noise_type')}>Noise</th>
              <th style={thStyle('f0_median_hz')} onClick={() => toggleSort('f0_median_hz')}>f0 (Hz)</th>
              <th style={{ ...thStyle('hd_baseline'), color: APPROACH_COLORS.baseline }} onClick={() => toggleSort('hd_baseline')}>
                Baseline {sortKey === 'hd_baseline' ? (sortDesc ? ' ▾' : ' ▴') : ''}
              </th>
              <th style={{ ...thStyle('hd_sklearn'), color: APPROACH_COLORS.sklearn }} onClick={() => toggleSort('hd_sklearn')}>
                ML sklearn {sortKey === 'hd_sklearn' ? (sortDesc ? ' ▾' : ' ▴') : ''}
              </th>
              <th style={{ ...thStyle('hd_pytorch'), color: APPROACH_COLORS.pytorch }} onClick={() => toggleSort('hd_pytorch')}>
                ML PyTorch {sortKey === 'hd_pytorch' ? (sortDesc ? ' ▾' : ' ▴') : ''}
              </th>
              <th style={{ ...thStyle('hd_dsp'), color: APPROACH_COLORS.dsp }} onClick={() => toggleSort('hd_dsp')}>
                DSP {sortKey === 'hd_dsp' ? (sortDesc ? ' ▾' : ' ▴') : ''}
              </th>
              <th style={thStyle('best_approach')} onClick={() => toggleSort('best_approach')}>Best</th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((r) => {
              const isSelected = selectedIndex === r.call_index
              return (
                <tr
                  key={r.call_index}
                  onClick={() => onSelect(r.call_index)}
                  style={{
                    background: isSelected ? 'var(--bg-warm)' : undefined,
                    cursor: 'pointer',
                    borderBottom: '1px solid var(--border)',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) (e.currentTarget as HTMLElement).style.background = 'var(--bg-warm)40'
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) (e.currentTarget as HTMLElement).style.background = ''
                  }}
                >
                  <td style={{ padding: '6px 10px', textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {r.call_index + 1}
                  </td>
                  <td style={{ padding: '6px 10px', fontFamily: 'monospace', fontSize: '0.73rem', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.filename}
                  </td>
                  <td style={{ padding: '6px 10px', textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {r.noise_type}
                  </td>
                  <td style={{ padding: '6px 10px', textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
                    {r.f0_median_hz.toFixed(1)}
                  </td>
                  <td style={hdCell(r.hd_baseline, 'baseline', r.best_approach === 'baseline')}>
                    {r.hd_baseline.toFixed(1)}
                  </td>
                  <td style={hdCell(r.hd_sklearn, 'sklearn', r.best_approach === 'sklearn')}>
                    {r.hd_sklearn.toFixed(1)}
                  </td>
                  <td style={hdCell(r.hd_pytorch, 'pytorch', r.best_approach === 'pytorch')}>
                    {r.hd_pytorch.toFixed(1)}
                  </td>
                  <td style={hdCell(r.hd_dsp, 'dsp', r.best_approach === 'dsp')}>
                    {r.hd_dsp.toFixed(1)}
                  </td>
                  <td style={{ padding: '4px 8px', textAlign: 'center' }}>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: '0.72rem',
                      fontFamily: 'var(--font-mono)',
                      background: `${APPROACH_COLORS[r.best_approach]}22`,
                      color: APPROACH_COLORS[r.best_approach],
                      fontWeight: 600,
                    }}>
                      {APPROACH_LABELS[r.best_approach] ?? r.best_approach}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
