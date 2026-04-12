import { Suspense, useRef, useMemo, useEffect, useState, useCallback } from 'react'
import { Canvas, useFrame, useLoader } from '@react-three/fiber'
import { OrbitControls, Environment, ContactShadows, Html } from '@react-three/drei'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import * as THREE from 'three'

function ElephantModel({ audioLevel }: { audioLevel: number }) {
  const obj = useLoader(OBJLoader, '/models/elephant.obj')
  const groupRef = useRef<THREE.Group>(null)

  const prepared = useMemo(() => {
    const clone = obj.clone(true)

    const material = new THREE.MeshStandardMaterial({
      color: new THREE.Color('#8b6f47'),
      roughness: 0.55,
      metalness: 0.05,
      flatShading: false,
    })

    clone.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh
        mesh.material = material
        mesh.castShadow = true
        mesh.receiveShadow = true
        if (mesh.geometry) {
          mesh.geometry.computeVertexNormals()
        }
      }
    })

    const box = new THREE.Box3().setFromObject(clone)
    const size = box.getSize(new THREE.Vector3())
    const center = box.getCenter(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z)
    const scale = 2.8 / maxDim

    clone.position.sub(center)
    clone.scale.setScalar(scale)

    return clone
  }, [obj])

  useFrame((state, delta) => {
    if (!groupRef.current) return
    groupRef.current.rotation.y += delta * 0.35
    const pulse = 1 + audioLevel * 0.04
    groupRef.current.scale.setScalar(pulse)
    groupRef.current.position.y =
      Math.sin(state.clock.elapsedTime * 1.2) * 0.05 + audioLevel * 0.08
  })

  return (
    <group ref={groupRef}>
      <primitive object={prepared} />
    </group>
  )
}

function LoadingFallback() {
  return (
    <Html center>
      <div
        style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: '0.7rem',
          color: '#5d4204',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          opacity: 0.6,
        }}
      >
        Loading mesh...
      </div>
    </Html>
  )
}

function SoundWaveRings({ audioLevel }: { audioLevel: number }) {
  const ring1 = useRef<THREE.Mesh>(null)
  const ring2 = useRef<THREE.Mesh>(null)
  const ring3 = useRef<THREE.Mesh>(null)

  useFrame((state) => {
    const t = state.clock.elapsedTime
    const pulse = 1 + audioLevel * 0.3

    if (ring1.current) {
      const s1 = (1 + Math.sin(t * 1.5) * 0.15) * pulse
      ring1.current.scale.set(s1, s1, 1)
      ;(ring1.current.material as THREE.MeshBasicMaterial).opacity =
        0.25 + Math.sin(t * 1.5) * 0.1
    }
    if (ring2.current) {
      const s2 = (1.4 + Math.sin(t * 1.2 + 1) * 0.15) * pulse
      ring2.current.scale.set(s2, s2, 1)
      ;(ring2.current.material as THREE.MeshBasicMaterial).opacity =
        0.18 + Math.sin(t * 1.2 + 1) * 0.08
    }
    if (ring3.current) {
      const s3 = (1.9 + Math.sin(t * 0.9 + 2) * 0.15) * pulse
      ring3.current.scale.set(s3, s3, 1)
      ;(ring3.current.material as THREE.MeshBasicMaterial).opacity =
        0.1 + Math.sin(t * 0.9 + 2) * 0.05
    }
  })

  return (
    <group position={[0, -1.4, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <mesh ref={ring1}>
        <ringGeometry args={[1.6, 1.68, 64]} />
        <meshBasicMaterial color="#5d4204" transparent opacity={0.25} />
      </mesh>
      <mesh ref={ring2}>
        <ringGeometry args={[1.6, 1.66, 64]} />
        <meshBasicMaterial color="#4a7c3f" transparent opacity={0.18} />
      </mesh>
      <mesh ref={ring3}>
        <ringGeometry args={[1.6, 1.64, 64]} />
        <meshBasicMaterial color="#c9a96e" transparent opacity={0.1} />
      </mesh>
    </group>
  )
}

interface AudioState {
  ctx: AudioContext
  analyser: AnalyserNode
  source: MediaElementAudioSourceNode
  data: Uint8Array
}

export default function ElephantViewer() {
  const [audioLevel, setAudioLevel] = useState(0)
  const [freqBars, setFreqBars] = useState<number[]>(new Array(24).fill(8))
  const [isPlaying, setIsPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement>(null)
  const audioState = useRef<AudioState | null>(null)
  const rafRef = useRef(0)

  const initAudio = useCallback(() => {
    if (audioState.current || !audioRef.current) return

    const ctx = new AudioContext()
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 64
    analyser.smoothingTimeConstant = 0.8

    const source = ctx.createMediaElementSource(audioRef.current)
    source.connect(analyser)
    analyser.connect(ctx.destination)

    const data = new Uint8Array(analyser.frequencyBinCount)
    audioState.current = { ctx, analyser, source, data }
  }, [])

  const tickAudio = useCallback(() => {
    if (!audioState.current) {
      rafRef.current = requestAnimationFrame(tickAudio)
      return
    }

    const { analyser, data } = audioState.current
    analyser.getByteFrequencyData(data as unknown as Uint8Array<ArrayBuffer>)

    const binCount = data.length
    const bars: number[] = []
    const barsNeeded = 24
    const binsPerBar = Math.max(1, Math.floor(binCount / barsNeeded))

    let totalLevel = 0
    for (let i = 0; i < barsNeeded; i++) {
      let sum = 0
      for (let j = 0; j < binsPerBar; j++) {
        const idx = i * binsPerBar + j
        sum += idx < binCount ? data[idx] : 0
      }
      const avg = sum / binsPerBar / 255
      bars.push(avg)
      totalLevel += avg
    }

    setFreqBars(bars.map(v => Math.max(0.06, v)))
    setAudioLevel(totalLevel / barsNeeded)
    rafRef.current = requestAnimationFrame(tickAudio)
  }, [])

  useEffect(() => {
    let idleRaf = 0
    let t = 0
    const idleTick = () => {
      if (!isPlaying) {
        t += 0.03
        const level = Math.abs(Math.sin(t * 0.8)) * 0.15 + Math.abs(Math.sin(t * 2.3)) * 0.1
        setAudioLevel(level)
        setFreqBars(prev => prev.map((_, i) =>
          0.06 + Math.abs(Math.sin(i * 0.7 + t * 1.2)) * 0.15
        ))
      }
      idleRaf = requestAnimationFrame(idleTick)
    }
    idleRaf = requestAnimationFrame(idleTick)
    return () => cancelAnimationFrame(idleRaf)
  }, [isPlaying])

  const togglePlay = useCallback(() => {
    if (!audioRef.current) return

    initAudio()

    if (isPlaying) {
      audioRef.current.pause()
      setIsPlaying(false)
      cancelAnimationFrame(rafRef.current)
    } else {
      if (audioState.current?.ctx.state === 'suspended') {
        audioState.current.ctx.resume()
      }
      audioRef.current.play().catch(() => {})
      setIsPlaying(true)
      rafRef.current = requestAnimationFrame(tickAudio)
    }
  }, [isPlaying, initAudio, tickAudio])

  const handleEnded = useCallback(() => {
    setIsPlaying(false)
    cancelAnimationFrame(rafRef.current)
  }, [])

  useEffect(() => {
    return () => cancelAnimationFrame(rafRef.current)
  }, [])

  return (
    <div className="elephant-viewer">
      <audio
        ref={audioRef}
        src="/models/elephant_rumble.wav"
        preload="auto"
        onEnded={handleEnded}
      />

      <Canvas
        shadows
        camera={{ position: [3.5, 1.8, 4.5], fov: 40 }}
        gl={{ antialias: true, alpha: true }}
      >
        <color attach="background" args={['#fdf8f0']} />
        <fog attach="fog" args={['#fdf8f0', 8, 16]} />

        <ambientLight intensity={0.55} />
        <directionalLight
          position={[5, 6, 3]}
          intensity={1.4}
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
        />
        <directionalLight position={[-4, 3, -2]} intensity={0.4} color="#c9a96e" />
        <pointLight position={[0, 2, 4]} intensity={0.3} color="#4a7c3f" />

        <Suspense fallback={<LoadingFallback />}>
          <ElephantModel audioLevel={audioLevel} />
          <SoundWaveRings audioLevel={audioLevel} />
          <Environment preset="sunset" />
          <ContactShadows
            position={[0, -1.45, 0]}
            opacity={0.45}
            scale={6}
            blur={2.2}
            far={3}
            color="#5d4204"
          />
        </Suspense>

        <OrbitControls
          enablePan={false}
          enableZoom={false}
          minPolarAngle={Math.PI / 3}
          maxPolarAngle={Math.PI / 1.9}
          autoRotate={false}
          rotateSpeed={0.6}
        />
      </Canvas>

      <div className="viewer-overlay-tl">
        <span className="viewer-dot" />
        <span>3D · LIVE</span>
      </div>

      <button
        className={`viewer-play-btn ${isPlaying ? 'playing' : ''}`}
        onClick={togglePlay}
        title={isPlaying ? 'Pause elephant rumble' : 'Play elephant rumble'}
      >
        {isPlaying ? '⏸' : '▶'}
        <span>{isPlaying ? 'PLAYING RUMBLE' : 'PLAY RUMBLE'}</span>
      </button>

      <div className="viewer-overlay-br">
        <span>DRAG TO ROTATE</span>
      </div>

      <div className="viewer-frequency" onClick={togglePlay} style={{ cursor: 'pointer' }}>
        {freqBars.map((v, i) => (
          <span
            key={i}
            className={`freq-bar ${isPlaying ? 'active' : ''}`}
            style={{
              height: `${Math.max(8, v * 100)}%`,
              opacity: isPlaying ? 0.5 + v * 0.5 : 0.25 + v * 0.4,
            }}
          />
        ))}
      </div>
    </div>
  )
}
