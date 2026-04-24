import { useEffect, useRef, useCallback, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import cytoscape from 'cytoscape'
import { signalsApi, GraphNode } from '../../api/signals'
import { Spinner } from '../ui/Spinner'

// ── Cytoscape stylesheet ───────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CY_STYLE: any[] = [
  // ── Base node ──
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'font-family': '"Inter", system-ui, sans-serif',
      'font-size': 11,
      color: '#cbd5e1',
      'text-wrap': 'wrap' as const,
      'text-max-width': '110',
      'text-valign': 'bottom' as const,
      'text-margin-y': 10,
      'text-outline-color': '#0f172a',
      'text-outline-width': 2,
      'border-width': 2,
      'border-opacity': 0.4,
      'overlay-padding': '6px',
      'transition-property': 'border-width, border-color, width, height',
      'transition-duration': 200,
    },
  },
  // ── Signal node (diamond, red glow) ──
  {
    selector: 'node[nodeType="signal"]',
    style: {
      'background-color': '#dc2626',
      'border-color': '#f87171',
      shape: 'diamond',
      width: 52,
      height: 52,
      'font-size': 12,
      'font-weight': 600,
      color: '#fca5a5',
      'text-margin-y': 12,
    },
  },
  // ── Cluster node (rounded rect, blue) ──
  {
    selector: 'node[nodeType="cluster"]',
    style: {
      'background-color': '#2563eb',
      'border-color': '#60a5fa',
      shape: 'round-rectangle',
      width: 44,
      height: 44,
      'font-size': 11,
      color: '#93c5fd',
    },
  },
  // ── Content node (circle, slate) ──
  {
    selector: 'node[nodeType="content"]',
    style: {
      'background-color': '#334155',
      'border-color': '#475569',
      shape: 'ellipse',
      width: 28,
      height: 28,
      'font-size': 9,
      color: '#94a3b8',
      'text-max-width': '90',
    },
  },
  // ── Source node (rounded square, green) ──
  {
    selector: 'node[nodeType="source"]',
    style: {
      'background-color': '#059669',
      'border-color': '#34d399',
      shape: 'round-rectangle',
      width: 36,
      height: 36,
      'font-size': 10,
      color: '#6ee7b7',
    },
  },
  // ── Cross-topic signal (diamond, amber) ──
  {
    selector: 'node[nodeType="cross_signal"]',
    style: {
      'background-color': '#d97706',
      'border-color': '#fbbf24',
      shape: 'diamond',
      width: 40,
      height: 40,
      'font-size': 10,
      color: '#fcd34d',
    },
  },
  // ── Hover state ──
  {
    selector: 'node:active, node:grabbed',
    style: {
      'border-width': 4,
      'border-color': '#e2e8f0',
      'overlay-opacity': 0.1,
      'overlay-color': '#3b82f6',
    },
  },
  // ── Base edge ──
  {
    selector: 'edge',
    style: {
      'curve-style': 'bezier' as const,
      'target-arrow-shape': 'triangle' as const,
      'arrow-scale': 0.7,
      opacity: 0.5,
      width: 1.5,
      'line-color': '#334155',
      'target-arrow-color': '#334155',
      'transition-property': 'opacity, width, line-color',
      'transition-duration': 200,
    },
  },
  // ── Edge types ──
  {
    selector: 'edge[edgeType="triggers"]',
    style: { 'line-color': '#dc2626', 'target-arrow-color': '#dc2626', width: 2.5, opacity: 0.7 },
  },
  {
    selector: 'edge[edgeType="contains"]',
    style: { 'line-color': '#475569', 'target-arrow-color': '#475569', width: 1.5 },
  },
  {
    selector: 'edge[edgeType="from_source"]',
    style: {
      'line-color': '#059669', 'target-arrow-color': '#059669',
      'line-style': 'dashed' as const, width: 1.5, 'line-dash-pattern': [6, 4],
    },
  },
  {
    selector: 'edge[edgeType="converges_with"]',
    style: {
      'line-color': '#d97706', 'target-arrow-color': '#d97706',
      'line-style': 'dashed' as const, width: 2, 'line-dash-pattern': [8, 4],
    },
  },
  // ── Highlighted (neighbor of selected) ──
  {
    selector: '.highlighted',
    style: { opacity: 1 },
  },
  {
    selector: '.highlighted-node',
    style: { 'border-width': 4, 'border-color': '#e2e8f0' },
  },
  {
    selector: '.dimmed',
    style: { opacity: 0.15 },
  },
  {
    selector: '.dimmed-node',
    style: { opacity: 0.2 },
  },
]

// ── Detail panel for selected node ─────────────────────────────────────

function NodeDetail({ node, onClose }: { node: GraphNode | null; onClose: () => void }) {
  if (!node) return null

  // Cast data fields for safe rendering
  const d = node.data as Record<string, string | number | null | undefined>

  const typeLabel: Record<string, string> = {
    signal: 'Signal',
    cluster: 'Narrative Cluster',
    content: 'Content Item',
    source: 'Source',
    cross_signal: 'Cross-Topic Signal',
  }

  const typeColor: Record<string, string> = {
    signal: '#dc2626',
    cluster: '#2563eb',
    content: '#475569',
    source: '#059669',
    cross_signal: '#d97706',
  }

  return (
    <div className="absolute bottom-0 left-0 right-0 bg-anveshak-card/95 backdrop-blur-md border-t border-anveshak-border p-4 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span
              className="w-3 h-3 rounded-sm shrink-0"
              style={{ backgroundColor: typeColor[node.type] }}
            />
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              {typeLabel[node.type] || node.type}
            </span>
          </div>
          <p className="text-sm font-medium text-text-primary leading-snug">{node.label}</p>
          {d.summary && (
            <p className="text-xs text-text-secondary mt-1 line-clamp-2">
              {String(d.summary)}
            </p>
          )}
          {d.url && (
            <a
              href={String(d.url)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-anveshak-accent hover:underline mt-1 inline-block"
            >
              {String(d.url).replace(/^https?:\/\/(www\.)?/, '').slice(0, 60)}
            </a>
          )}
          <div className="flex items-center gap-3 mt-1.5 text-[10px] text-text-muted">
            {d.credibility != null && (
              <span>Credibility: <strong className="text-text-secondary">{String(d.credibility)}</strong></span>
            )}
            {d.platform && (
              <span>Platform: <strong className="text-text-secondary">{String(d.platform).toUpperCase()}</strong></span>
            )}
            {d.isc != null && (
              <span>Sources: <strong className="text-text-secondary">{String(d.isc)}</strong></span>
            )}
            {d.captured_at && (
              <span>{new Date(String(d.captured_at)).toLocaleDateString()}</span>
            )}
          </div>
        </div>
        <button onClick={onClose} className="text-text-muted hover:text-text-primary text-sm px-1">✕</button>
      </div>
    </div>
  )
}

// ── Graph Component ────────────────────────────────────────────────────

interface SignalGraphProps {
  signalId: string
  onClose: () => void
}

export function SignalGraph({ signalId, onClose }: SignalGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['signal-connections', signalId],
    queryFn: () => signalsApi.connections(signalId),
    staleTime: 60_000,
  })

  const initGraph = useCallback(() => {
    if (!containerRef.current || !data || data.nodes.length === 0) return

    if (cyRef.current) cyRef.current.destroy()

    const elements: cytoscape.ElementDefinition[] = []

    for (const node of data.nodes) {
      elements.push({
        data: {
          id: node.id,
          label: node.label.length > 35 ? node.label.slice(0, 33) + '…' : node.label,
          fullLabel: node.label,
          nodeType: node.type,
          ...node.data,
        },
      })
    }

    for (const edge of data.edges) {
      elements.push({
        data: { source: edge.source, target: edge.target, edgeType: edge.type },
      })
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: CY_STYLE,
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 600,
        animationEasing: 'ease-out-cubic',
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 120,
        gravity: 0.4,
        numIter: 300,
        padding: 60,
        randomize: false,
      } as cytoscape.CoseLayoutOptions,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      minZoom: 0.3,
      maxZoom: 3,
    })

    // Click node → highlight neighbors + show detail
    cy.on('tap', 'node', (e) => {
      const node = e.target
      const nodeData = data.nodes.find((n) => n.id === node.id())
      setSelectedNode(nodeData || null)

      // Dim everything, highlight selected + neighbors
      cy.elements().addClass('dimmed').addClass('dimmed-node')
      node.removeClass('dimmed').removeClass('dimmed-node').addClass('highlighted-node')
      node.neighborhood().removeClass('dimmed').removeClass('dimmed-node').addClass('highlighted')
      node.connectedEdges().removeClass('dimmed').addClass('highlighted')
    })

    // Click background → reset
    cy.on('tap', (e) => {
      if (e.target === cy) {
        cy.elements().removeClass('dimmed dimmed-node highlighted highlighted-node')
        setSelectedNode(null)
      }
    })

    // Hover glow
    cy.on('mouseover', 'node', (e) => {
      e.target.style('border-width', 4)
      e.target.style('border-color', '#e2e8f0')
      containerRef.current!.style.cursor = 'pointer'
    })
    cy.on('mouseout', 'node', (e) => {
      if (!e.target.hasClass('highlighted-node')) {
        e.target.style('border-width', 2)
        e.target.style('border-color', '')
      }
      containerRef.current!.style.cursor = 'default'
    })

    cyRef.current = cy
  }, [data])

  useEffect(() => {
    initGraph()
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [initGraph])

  // Keyboard: Escape to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-[#0b1120] border border-anveshak-border/50 rounded-xl w-full max-w-5xl h-[80vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-anveshak-border/50 bg-[#0f1729]">
          <div className="flex items-center gap-4">
            <span className="text-sm font-semibold text-text-primary tracking-tight">
              Signal Connection Graph
            </span>
            <div className="flex items-center gap-4 text-[10px] text-text-muted">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 bg-[#dc2626] rotate-45 inline-block" /> Signal
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 bg-[#2563eb] rounded-sm inline-block" /> Cluster
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 bg-[#475569] rounded-full inline-block" /> Content
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 bg-[#059669] rounded-sm inline-block" /> Source
              </span>
            </div>
            {data && (
              <span className="text-[10px] text-text-muted ml-2">
                {data.nodes.length} nodes · {data.edges.length} connections
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => cyRef.current?.fit(undefined, 60)}
              className="text-[10px] text-text-muted hover:text-text-primary px-2 py-1 rounded border border-anveshak-border/50 hover:border-anveshak-border transition-colors"
            >
              Fit
            </button>
            <button
              onClick={onClose}
              className="text-text-muted hover:text-text-primary transition-colors text-lg leading-none px-2 py-1"
              aria-label="Close graph"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Graph container */}
        <div className="flex-1 relative">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <Spinner label="Loading connections…" />
            </div>
          ) : data && data.nodes.length === 0 ? (
            <div className="flex items-center justify-center h-full text-text-muted text-sm">
              No connection data available for this signal.
            </div>
          ) : (
            <>
              <div ref={containerRef} className="w-full h-full" />
              <NodeDetail node={selectedNode} onClose={() => {
                setSelectedNode(null)
                cyRef.current?.elements().removeClass('dimmed dimmed-node highlighted highlighted-node')
              }} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
