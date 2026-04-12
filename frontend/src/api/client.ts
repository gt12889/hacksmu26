import axios from 'axios'
import type {
  UploadResponse,
  ProcessResponse,
  StatusResponse,
  ResultResponse,
  DashboardResponse,
} from '../types/api'

export async function uploadFile(file: File): Promise<UploadResponse> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await axios.post<UploadResponse>('/api/upload', fd)
  return res.data
}

export async function startProcessing(fileId: string): Promise<ProcessResponse> {
  // file_id is a query parameter, not a JSON body (see api/routes/process.py)
  const res = await axios.post<ProcessResponse>(
    `/api/process?file_id=${encodeURIComponent(fileId)}`
  )
  return res.data
}

export async function getStatus(jobId: string): Promise<StatusResponse> {
  const res = await axios.get<StatusResponse>(`/api/status/${jobId}`)
  return res.data
}

export async function getResult(jobId: string): Promise<ResultResponse> {
  const res = await axios.get<ResultResponse>(`/api/result/${jobId}`)
  return res.data
}

export async function getBatchResults(): Promise<ResultResponse> {
  const res = await axios.get<ResultResponse>('/api/batch/results')
  return res.data
}

export function audioUrl(jobId: string, callIndex: number): string {
  return `/api/result/${jobId}/audio/${callIndex}`
}

export function uploadAudioUrl(fileId: string): string {
  return `/api/upload/${fileId}/audio`
}

/** URL for fetching a batch-disk clean WAV by its absolute path.
 *  Used by App.tsx when source.kind === 'batch' to populate cleanUrl for SpectrogramView.
 *  The server enforces an allowlist (data/outputs/ and cleaned/) so arbitrary paths are rejected. */
export async function getDashboardRows(): Promise<DashboardResponse> {
  try {
    const res = await axios.get<DashboardResponse>('/api/batch/dashboard')
    return res.data
  } catch {
    // Fallback: fetch static CSV from /static/demo/dashboard_scores.csv
    const csvRes = await fetch('/static/demo/dashboard_scores.csv')
    if (!csvRes.ok) throw new Error('dashboard_scores.csv not available')
    const text = await csvRes.text()
    const rows = parseDashboardCsv(text)
    return { rows }
  }
}

function parseDashboardCsv(text: string): import('../types/api').DashboardRow[] {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []
  const header = lines[0].split(',')
  const idx = (col: string) => header.indexOf(col)
  return lines.slice(1).map((line) => {
    const cols = line.split(',')
    const g = (col: string) => cols[idx(col)] ?? ''
    const n = (col: string) => parseFloat(g(col)) || 0
    return {
      filename: g('filename'),
      call_index: parseInt(g('call_index')) || 0,
      noise_type: g('noise_type'),
      f0_median_hz: n('f0_median_hz'),
      duration_s: n('duration_s'),
      hd_baseline: n('hd_baseline'),
      hd_sklearn: n('hd_sklearn'),
      hd_pytorch: n('hd_pytorch'),
      hd_dsp: n('hd_dsp'),
      best_approach: (g('best_approach') || 'dsp') as import('../types/api').DashboardRow['best_approach'],
      best_hd: n('best_hd'),
    }
  })
}

export function batchAudioUrl(path: string): string {
  return `/api/batch/audio?path=${encodeURIComponent(path)}`
}
