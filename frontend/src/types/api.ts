export interface UploadResponse {
  file_id: string
  filename: string
  path: string
}

export interface ProcessResponse {
  job_id: string
}

export type JobStatus = 'queued' | 'running' | 'complete' | 'failed'

export interface StatusResponse {
  job_id: string
  status: JobStatus
  progress: number
  total: number
  eta_seconds?: number | null
}

export interface CallResult {
  filename: string
  start: number
  end: number
  f0_median_hz: number
  snr_before_db: number
  snr_after_db: number
  confidence: number
  noise_type: string
  status: string
  clean_wav_path: string
}

export interface ResultResponse {
  job_id: string
  results: CallResult[]
}

export interface BatchSummaryResponse {
  total_jobs: number
  total_calls_processed: number
  average_confidence: number | null
  average_snr_improvement_db: number | null
}
