/**
 * CurvedLoop — marquee text that follows a curved SVG path.
 *
 * Adapted from react-bits CurvedLoop-JS-CSS (MIT). Standalone implementation
 * so we don't need Tailwind / shadcn.
 *
 * Usage:
 *   <CurvedLoop
 *     marqueeText="ELEPHANT RUMBLES · HARMONIC COMB · ·"
 *     speed={2}
 *     curveAmount={400}
 *     direction="left"
 *     interactive
 *   />
 */
import { useRef, useEffect, useState, useMemo, type CSSProperties } from 'react'

interface CurvedLoopProps {
  marqueeText: string
  speed?: number          // pixels per frame scroll speed
  className?: string
  curveAmount?: number    // curve depth of the bezier path (pixels)
  direction?: 'left' | 'right'
  interactive?: boolean   // allow drag-to-scrub
}

export default function CurvedLoop({
  marqueeText,
  speed = 2,
  className,
  curveAmount = 400,
  direction = 'left',
  interactive = true,
}: CurvedLoopProps) {
  const text = useMemo(() => {
    const hasTrailingSpace = /\s|\u00A0$/.test(marqueeText)
    return hasTrailingSpace ? marqueeText : marqueeText + '\u00A0'
  }, [marqueeText])

  const measureRef = useRef<SVGTextElement | null>(null)
  const textPathRef = useRef<SVGTextPathElement | null>(null)
  const pathRef = useRef<SVGPathElement | null>(null)
  const [spacing, setSpacing] = useState(0)
  const [offset, setOffset] = useState(0)
  const [uid] = useState(() => `curve-path-${Math.floor(Math.random() * 1e9)}`)

  const pathLength = 1600
  const pathD = `M -100,40 Q ${pathLength / 2},${40 + curveAmount} ${pathLength + 100},40`

  const dragRef = useRef(false)
  const lastXRef = useRef(0)
  const dirRef = useRef<'left' | 'right'>(direction)
  const velRef = useRef(0)

  const textLength = spacing
  const totalText = textLength
    ? Array(Math.ceil(1800 / textLength) + 2).fill(text).join('')
    : text

  // Measure text width so we can tile enough copies to fill the path
  useEffect(() => {
    if (measureRef.current) {
      setSpacing(measureRef.current.getComputedTextLength())
    }
  }, [text, className])

  // Animation loop
  useEffect(() => {
    if (!spacing) return
    let raf = 0
    const step = () => {
      if (!dragRef.current && textPathRef.current) {
        const delta = dirRef.current === 'right' ? speed : -speed
        const currentOffset = parseFloat(
          textPathRef.current.getAttribute('startOffset') || '0',
        )
        let newOffset = currentOffset + delta
        const wrapPoint = spacing
        if (newOffset <= -wrapPoint) newOffset += wrapPoint
        if (newOffset > 0) newOffset -= wrapPoint
        textPathRef.current.setAttribute('startOffset', newOffset + 'px')
        setOffset(newOffset)
      }
      raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [spacing, speed])

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!interactive) return
    dragRef.current = true
    lastXRef.current = e.clientX
    velRef.current = 0
    ;(e.target as SVGSVGElement).setPointerCapture?.(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!interactive || !dragRef.current || !textPathRef.current) return
    const dx = e.clientX - lastXRef.current
    lastXRef.current = e.clientX
    velRef.current = dx
    const current = parseFloat(textPathRef.current.getAttribute('startOffset') || '0')
    let next = current + dx
    const wrapPoint = spacing
    if (next <= -wrapPoint) next += wrapPoint
    if (next > 0) next -= wrapPoint
    textPathRef.current.setAttribute('startOffset', next + 'px')
    setOffset(next)
  }
  const onPointerUp = () => {
    if (!interactive) return
    dragRef.current = false
    if (velRef.current > 0.5) dirRef.current = 'right'
    else if (velRef.current < -0.5) dirRef.current = 'left'
  }

  const wrapperStyle: CSSProperties = {
    visibility: spacing ? 'visible' : 'hidden',
    minHeight: curveAmount + 100,
    width: '100%',
    cursor: interactive ? (dragRef.current ? 'grabbing' : 'grab') : 'default',
    overflow: 'hidden',
    userSelect: 'none',
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        visibility: spacing ? 'visible' : 'hidden',
        width: '100%',
      }}
    >
      <svg
        className={className}
        viewBox={`0 0 ${pathLength} ${curveAmount + 100}`}
        preserveAspectRatio="xMidYMid slice"
        style={wrapperStyle}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        {/* Hidden text node to measure string width */}
        <text
          ref={measureRef}
          xmlSpace="preserve"
          style={{ visibility: 'hidden', opacity: 0, pointerEvents: 'none' }}
        >
          {text}
        </text>
        <defs>
          <path ref={pathRef} id={uid} d={pathD} />
        </defs>
        {spacing > 0 && (
          <text
            fill="currentColor"
            xmlSpace="preserve"
            style={{
              fontFamily: 'inherit',
              fontSize: '6rem',
              fontWeight: 900,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            <textPath
              ref={textPathRef}
              href={`#${uid}`}
              startOffset={offset + 'px'}
              xmlSpace="preserve"
            >
              {totalText}
            </textPath>
          </text>
        )}
      </svg>
    </div>
  )
}
