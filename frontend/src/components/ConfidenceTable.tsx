import { useState, useMemo } from 'react'
import type { CallResult } from '../types/api'

type SortKey = 'confidence' | 'f0_median_hz' | 'snr_before_db' | 'snr_after_db' | 'noise_type' | 'filename'

export interface ConfidenceTableProps {
  results: CallResult[]
  selectedIndex: number | null
  onSelect: (index: number) => void
}

export function ConfidenceTable({ results, selectedIndex, onSelect }: ConfidenceTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('confidence')
  const [sortDesc, setSortDesc] = useState(true)
  const [filterText, setFilterText] = useState('')

  const rows = useMemo(() => {
    const indexed = results.map((r, i) => ({ r, i }))
    const filtered = indexed.filter(({ r }) => {
      if (!filterText) return true
      const q = filterText.toLowerCase()
      return r.filename.toLowerCase().includes(q) || r.noise_type.toLowerCase().includes(q)
    })
    filtered.sort((a, b) => {
      const av = a.r[sortKey] as number | string
      const bv = b.r[sortKey] as number | string
      if (typeof av === 'number' && typeof bv === 'number') {
        return sortDesc ? bv - av : av - bv
      }
      return sortDesc
        ? String(bv).localeCompare(String(av))
        : String(av).localeCompare(String(bv))
    })
    return filtered
  }, [results, sortKey, sortDesc, filterText])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDesc((d) => !d)
    else { setSortKey(key); setSortDesc(true) }
  }

  return (
    <div>
      <div style={{ margin: '8px 0' }}>
        <input
          placeholder="Filter by filename or noise type..."
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          style={{ padding: '6px 10px', width: 300 }}
        />
        <span style={{ marginLeft: 12, opacity: 0.6 }}>
          {rows.length} of {results.length} calls
        </span>
      </div>
      <table>
        <thead>
          <tr>
            <th onClick={() => toggleSort('confidence')}>Confidence %</th>
            <th onClick={() => toggleSort('f0_median_hz')}>f0 (Hz)</th>
            <th onClick={() => toggleSort('snr_before_db')}>SNR Before (dB)</th>
            <th onClick={() => toggleSort('snr_after_db')}>SNR After (dB)</th>
            <th onClick={() => toggleSort('noise_type')}>Noise Type</th>
            <th onClick={() => toggleSort('filename')}>Filename</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ r, i }) => (
            <tr
              key={i}
              onClick={() => onSelect(i)}
              style={{
                background: selectedIndex === i ? '#2a2a40' : undefined,
                cursor: 'pointer',
              }}
            >
              <td>{r.confidence.toFixed(1)}</td>
              <td>{r.f0_median_hz.toFixed(1)}</td>
              <td>{r.snr_before_db.toFixed(1)}</td>
              <td>{r.snr_after_db.toFixed(1)}</td>
              <td>{r.noise_type}</td>
              <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{r.filename}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
