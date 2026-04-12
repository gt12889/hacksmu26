export type DemoStatus = 'checking' | 'not_ready' | 'generating' | 'ready' | 'error'
export type NoiseType = 'generator' | 'car' | 'plane'

export interface NoiseMetrics {
  snr_before: number
  snr_after: number
  snr_improvement: number
  f0_min: number
  f0_max: number
  f0_median: number
  duration: number
  source_file?: string
  call_window?: string
  real_data?: boolean
}

export interface Metadata {
  generator: NoiseMetrics
  car: NoiseMetrics
  plane: NoiseMetrics
}

export interface JobStatus {
  status: 'idle' | 'running' | 'done' | 'error'
  progress: number
  message: string
}

export interface StatusResponse {
  ready: boolean
  job: JobStatus
}
