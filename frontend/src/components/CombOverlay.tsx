import { useEffect, useRef } from 'react'

export interface CombOverlayProps {
  f0Hz: number
  width: number
  height: number
  frequencyMax?: number   // default 1000
  bandwidthHz?: number    // default 5
}

export function CombOverlay({
  f0Hz,
  width,
  height,
  frequencyMax = 1000,
  bandwidthHz = 5,
}: CombOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, width, height)

    // Guard: skip drawing if f0 is invalid
    if (f0Hz <= 0) return

    ctx.fillStyle = 'rgba(255, 100, 0, 0.35)'

    for (let k = 1; k * f0Hz <= frequencyMax; k++) {
      const centerHz = k * f0Hz
      // Y=0 is top of canvas. Spectrogram convention: low freq at bottom, high at top.
      // Invert so higher frequencies map to smaller y values.
      const centerY = height - (centerHz / frequencyMax) * height
      const halfPx = Math.max(1, (bandwidthHz / frequencyMax) * height)
      ctx.fillRect(0, centerY - halfPx, width, halfPx * 2)
    }
  }, [f0Hz, frequencyMax, bandwidthHz, width, height])

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        pointerEvents: 'none',
        zIndex: 5, // above SpectrogramPlugin canvas (z-index 4)
      }}
    />
  )
}
