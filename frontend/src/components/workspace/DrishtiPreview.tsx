/**
 * DrishtiPreview — 3D force-directed entity resolution graph.
 *
 * Shows cross-topic entity connections with bloom/glow, auto-rotation,
 * particle streams on edges, and topic-based coloring.
 * Preview banner clearly labels this as a capability demonstration.
 */
import { useRef, useCallback, useMemo, useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ForceGraph3D, { type ForceGraphMethods } from 'react-force-graph-3d'
import * as THREE from 'three'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { intelligenceApi, type DrishtiNode } from '../../api/intelligence'
import { Spinner } from '../ui/Spinner'

// ── Constants ─────────────────────────────────────────────────────────

const TOPIC_COLORS = [
  '#f59e0b', // amber — home topic
  '#06b6d4', // cyan
  '#a855f7', // purple
  '#22c55e', // green
  '#ec4899', // pink
  '#6366f1', // indigo
]

const CROSS_TOPIC_GLOW = '#ffffff'

// ── Types ─────────────────────────────────────────────────────────────

interface GraphNode {
  id: string
  name: string
  type: string
  topics: { id: string; name: string; mentions: number }[]
  totalMentions: number
  isCrossTopic: boolean
  color: string
  size: number
}

interface GraphLink {
  source: string
  target: string
  weight: number
}

interface Props {
  topicId: string
}

// ── Component ─────────────────────────────────────────────────────────

export default function DrishtiPreview({ topicId }: Props) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<ForceGraphMethods<any, any>>()
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['drishti-preview', topicId],
    queryFn: () => intelligenceApi.drishtiPreview(topicId),
    staleTime: 300_000,
  })

  // Build graph data
  const graphData = useMemo(() => {
    if (!data?.nodes?.length) return { nodes: [], links: [] }

    const topicColorMap = data.topic_colors || {}
    const colorList = Object.values(topicColorMap)

    const nodes: GraphNode[] = data.nodes.map((n: DrishtiNode) => {
      // Color: cross-topic nodes get brighter, single-topic get topic color
      const primaryTopicId = n.topics[0]?.id
      const baseColor = topicColorMap[primaryTopicId] || colorList[0] || TOPIC_COLORS[0]

      return {
        id: n.id,
        name: n.name,
        type: n.type,
        topics: n.topics,
        totalMentions: n.total_mentions,
        isCrossTopic: n.is_cross_topic,
        color: n.is_cross_topic ? CROSS_TOPIC_GLOW : baseColor,
        size: Math.max(3, Math.min(12, 3 + Math.sqrt(n.total_mentions) * 2)),
      }
    })

    const nodeIds = new Set(nodes.map(n => n.id))
    const links: GraphLink[] = data.edges
      .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
      .map(e => ({
        source: e.source,
        target: e.target,
        weight: e.weight,
      }))

    return { nodes, links }
  }, [data])

  // Apply bloom + auto-rotation after graph mounts
  const bloomApplied = useRef(false)
  useEffect(() => {
    if (!fgRef.current || bloomApplied.current || !graphData.nodes.length) return
    const fg = fgRef.current
    const timer = setTimeout(() => {
      try {
        const scene = fg.scene()
        scene.background = new THREE.Color('#050a15')
        scene.fog = new THREE.FogExp2('#050a15', 0.002)

        const bloomPass = new UnrealBloomPass(
          new THREE.Vector2(window.innerWidth, window.innerHeight),
          1.5, 0.4, 0.2,
        )
        const composer = fg.postProcessingComposer()
        composer.addPass(bloomPass)

        const controls = fg.controls() as unknown as { autoRotate: boolean; autoRotateSpeed: number }
        if (controls) {
          controls.autoRotate = true
          controls.autoRotateSpeed = 0.5
        }

        const ambientLight = new THREE.AmbientLight('#1a1a3e', 0.3)
        scene.add(ambientLight)
        bloomApplied.current = true
      } catch {
        // graph not ready yet — will retry on next render
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [graphData.nodes.length])

  // Custom node rendering — glowing spheres with labels
  const nodeThreeObject = useCallback((node: object) => {
    const n = node as GraphNode
    const group = new THREE.Group()
    const sz = n.size || 5

    // Core sphere
    const geometry = new THREE.SphereGeometry(sz * 0.5, 16, 16)
    const color = new THREE.Color(n.color || '#6366f1')
    const material = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: n.isCrossTopic ? 0.6 : 0.3,
      transparent: true,
      opacity: 0.9,
      roughness: 0.3,
      metalness: 0.7,
    })
    const mesh = new THREE.Mesh(geometry, material)
    group.add(mesh)

    // Outer glow for cross-topic nodes
    if (n.isCrossTopic) {
      const glowGeo = new THREE.SphereGeometry(sz * 0.8, 16, 16)
      const glowMat = new THREE.MeshBasicMaterial({
        color: new THREE.Color('#a855f7'),
        transparent: true,
        opacity: 0.12,
      })
      group.add(new THREE.Mesh(glowGeo, glowMat))
    }

    // Label sprite
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')!
    canvas.width = 256
    canvas.height = 64
    ctx.font = `${n.isCrossTopic ? 'bold ' : ''}18px Inter, system-ui, sans-serif`
    ctx.fillStyle = n.isCrossTopic ? '#ffffff' : '#94a3b8'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    const label = (n.name || '').length > 22 ? (n.name || '').slice(0, 21) + '…' : (n.name || '')
    ctx.fillText(label, 128, 32)

    const texture = new THREE.CanvasTexture(canvas)
    const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true })
    const sprite = new THREE.Sprite(spriteMat)
    sprite.scale.set(20, 5, 1)
    sprite.position.set(0, sz + 3, 0)
    group.add(sprite)

    return group
  }, [])

  // Click handler
  const handleNodeClick = useCallback((nodeObj: object) => {
    const node = nodeObj as GraphNode
    setSelectedNode(prev => prev?.id === node.id ? null : node)

    // Zoom to node
    const fg = fgRef.current
    if (fg) {
      const distance = 80
      const pos = node as unknown as { x: number; y: number; z: number }
      fg.cameraPosition(
        { x: pos.x + distance, y: pos.y + distance / 2, z: pos.z + distance },
        { x: pos.x, y: pos.y, z: pos.z },
        1000,
      )
    }
  }, [])

  // Link styling
  const linkColor = useCallback(() => 'rgba(100, 116, 139, 0.3)', [])
  const linkWidth = useCallback((link: object) => {
    const l = link as GraphLink
    return Math.max(0.5, Math.min(3, (l.weight || 1) * 0.5))
  }, [])

  // ── Render ──

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full bg-[#050a15]">
        <Spinner label="Loading entity resolution preview..." />
      </div>
    )
  }

  if (!data?.has_cross_topic_data) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-[#050a15] text-text-muted gap-4">
        <div className="text-5xl opacity-30">🔮</div>
        <p className="text-sm">Entity resolution for this topic — coming with Drishti.</p>
      </div>
    )
  }

  const crossTopicCount = graphData.nodes.filter(n => n.isCrossTopic).length
  const topicNames = [...new Set(graphData.nodes.flatMap(n => n.topics.map(t => t.name)))]

  return (
    <div className="flex h-full bg-[#050a15]">
      {/* Graph area */}
      <div className="flex-1 relative" ref={containerRef}>
        {/* Preview banner */}
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 bg-purple-500/20 backdrop-blur-md border border-purple-500/40 rounded-lg px-4 py-2 pointer-events-none">
          <div className="flex items-center gap-2 text-xs text-purple-300">
            <span className="text-sm">🔮</span>
            <span className="font-medium">Preview — What Drishti entity resolution would surface from this data</span>
          </div>
        </div>

        {/* Stats overlay */}
        <div className="absolute bottom-3 left-3 z-10 bg-[#0f1729]/80 backdrop-blur-sm border border-anveshak-border/30 rounded-lg px-3 py-2 pointer-events-none">
          <div className="flex flex-col gap-1 text-[10px] text-text-muted">
            <span>{graphData.nodes.length} entities · {graphData.links.length} connections</span>
            <span className="text-purple-400">{crossTopicCount} cross-topic entities resolved</span>
            <div className="flex flex-wrap gap-2 mt-1">
              {topicNames.map((name, i) => (
                <span key={name} className="flex items-center gap-1">
                  <span
                    className="w-2 h-2 rounded-full inline-block"
                    style={{ backgroundColor: TOPIC_COLORS[i % TOPIC_COLORS.length] }}
                  />
                  <span className="truncate max-w-[120px]">{name}</span>
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="absolute bottom-3 right-3 z-10 bg-[#0f1729]/80 backdrop-blur-sm border border-anveshak-border/30 rounded-lg px-3 py-2 pointer-events-none">
          <div className="flex flex-col gap-1.5 text-[10px] text-text-muted">
            <span className="text-text-secondary font-semibold mb-0.5">Entity Types</span>
            <span className="flex items-center gap-1.5">● Person</span>
            <span className="flex items-center gap-1.5">■ Organization</span>
            <span className="flex items-center gap-1.5">◆ Facility</span>
            <span className="flex items-center gap-1.5">⬟ Location</span>
            <span className="border-t border-anveshak-border/30 pt-1 mt-0.5 text-purple-400">
              ✦ Glowing = cross-topic
            </span>
          </div>
        </div>

        <div ref={containerRef} style={{ position: 'absolute', inset: 0 }}>
          <ForceGraph3D
            ref={fgRef}
            graphData={graphData}
            nodeThreeObject={nodeThreeObject}
            nodeThreeObjectExtend={false}
            onNodeClick={handleNodeClick}
            linkColor={linkColor}
            linkWidth={linkWidth}
            linkDirectionalParticles={3}
            linkDirectionalParticleWidth={1.2}
            linkDirectionalParticleSpeed={0.003}
            linkDirectionalParticleColor={() => 'rgba(168, 85, 247, 0.6)'}
            linkCurvature={0.15}
            linkOpacity={0.3}
            backgroundColor="#050a15"
            showNavInfo={false}
            onEngineStop={() => {
              fgRef.current?.zoomToFit(800, 50)
            }}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            warmupTicks={50}
            cooldownTicks={100}
          />
        </div>
      </div>

      {/* Detail panel */}
      {selectedNode && (
        <div className="w-80 border-l border-anveshak-border/30 bg-[#0f1729] flex flex-col shrink-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-anveshak-border/20">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="w-3 h-3 rounded-full inline-block shrink-0"
                style={{ backgroundColor: selectedNode.color }}
              />
              <span className="text-[10px] text-text-muted uppercase tracking-wider font-bold">
                {selectedNode.type}
              </span>
              {selectedNode.isCrossTopic && (
                <span className="text-[9px] bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded-full font-medium">
                  CROSS-TOPIC
                </span>
              )}
            </div>
            <p className="text-sm text-text-primary font-semibold break-all">{selectedNode.name}</p>
            <p className="text-[10px] text-text-muted mt-1">{selectedNode.totalMentions} total mentions</p>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3">
            <h4 className="text-[10px] text-text-muted uppercase tracking-wider font-bold mb-2">
              Appears in ({selectedNode.topics.length} topic{selectedNode.topics.length > 1 ? 's' : ''})
            </h4>
            <div className="space-y-2">
              {selectedNode.topics.map((t, i) => (
                <div key={t.id} className="flex items-center gap-2 py-1.5 px-2 rounded bg-anveshak-muted/10 text-xs">
                  <span
                    className="w-2.5 h-2.5 rounded-full inline-block shrink-0"
                    style={{ backgroundColor: data?.topic_colors?.[t.id] || TOPIC_COLORS[i % TOPIC_COLORS.length] }}
                  />
                  <span className="text-text-primary flex-1 truncate">{t.name}</span>
                  <span className="text-text-muted shrink-0">{t.mentions}×</span>
                </div>
              ))}
            </div>

            {selectedNode.isCrossTopic && (
              <div className="mt-4 p-2.5 bg-purple-500/10 border border-purple-500/20 rounded-lg">
                <p className="text-[10px] text-purple-300 leading-relaxed">
                  Drishti would resolve this entity across all topics,
                  linking variant spellings and cross-referencing with
                  structured intelligence feeds.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
