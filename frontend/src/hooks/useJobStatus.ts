import { useEffect, useState } from 'react'
import { getStatus } from '../api/client'
import type { StatusResponse } from '../types/api'

export function useJobStatus(jobId: string | null): StatusResponse | null {
  const [status, setStatus] = useState<StatusResponse | null>(null)

  useEffect(() => {
    if (!jobId) {
      setStatus(null)
      return
    }
    let cancelled = false
    const tick = async () => {
      try {
        const s = await getStatus(jobId)
        if (cancelled) return
        setStatus(s)
        if (s.status === 'complete' || s.status === 'failed') {
          clearInterval(id)
        }
      } catch {
        // swallow transient errors; next tick will retry
      }
    }
    const id = setInterval(tick, 2000)
    tick() // fire immediately so UI does not wait 2s for first value
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [jobId])

  return status
}
