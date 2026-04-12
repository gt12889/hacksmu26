import { useEffect, useState } from 'react'
import { uploadFile, startProcessing, getResult } from '../api/client'
import { useJobStatus } from '../hooks/useJobStatus'
import type { CallResult } from '../types/api'

export interface UploadPanelProps {
  onComplete: (args: {
    jobId: string
    fileId: string
    file: File
    results: CallResult[]
  }) => void
}

export function UploadPanel({ onComplete }: UploadPanelProps) {
  const [file, setFile] = useState<File | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [fileId, setFileId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const status = useJobStatus(jobId)

  useEffect(() => {
    if (status?.status === 'complete' && jobId && fileId && file) {
      getResult(jobId)
        .then((r) => {
          onComplete({ jobId, fileId, file, results: r.results })
          setJobId(null)
        })
        .catch((e) => setError(String(e)))
    }
  }, [status?.status, jobId, fileId, file, onComplete])

  const handleUpload = async () => {
    if (!file) return
    setError(null)
    try {
      const up = await uploadFile(file)
      setFileId(up.file_id)
      const proc = await startProcessing(up.file_id)
      setJobId(proc.job_id)
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div style={{ padding: '12px 0', borderBottom: '1px solid #2a2a33' }}>
      <input
        type="file"
        accept="audio/wav,.wav"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <button onClick={handleUpload} disabled={!file || !!jobId}>
        {jobId ? 'Processing...' : 'Upload & Process'}
      </button>
      {status && (
        <span style={{ marginLeft: 12, opacity: 0.7 }}>
          {status.status}  {status.progress}/{status.total}
        </span>
      )}
      {error && <div style={{ color: '#f66' }}>{error}</div>}
    </div>
  )
}
