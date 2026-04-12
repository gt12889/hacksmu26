import axios from 'axios'
import type {
  UploadResponse,
  ProcessResponse,
  StatusResponse,
  ResultResponse,
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
export function batchAudioUrl(path: string): string {
  return `/api/batch/audio?path=${encodeURIComponent(path)}`
}
