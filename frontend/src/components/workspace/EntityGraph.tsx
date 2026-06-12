import { useEffect, useRef, useCallback, useState } from 'react'
import { useQuery, useQueries } from '@tanstack/react-query'
import cytoscape from 'cytoscape'
import { intelligenceApi } from '../../api/intelligence'
import { identifiersApi, ClusterDetail } from '../../api/identifiers'
import { Spinner } from '../ui/Spinner'

// ── Visual config ──────────────────────────────────────────────────────

const ID_STYLES: Record<string, { bg: string; border: string; label: string; shape: string }> = {
  PHONE_IN:         { bg: '#22c55e', border: '#86efac', label: 'PHONE',     shape: 'ellipse' },
  UPI:              { bg: '#a855f7', border: '#d8b4fe', label: 'UPI',       shape: 'ellipse' },
  TELEGRAM_HANDLE:  { bg: '#0ea5e9', border: '#7dd3fc', label: 'TELEGRAM',  shape: 'ellipse' },
  CRYPTO_BTC:       { bg: '#f59e0b', border: '#fde68a', label: 'BTC',       shape: 'hexagon' },
  CRYPTO_ETH:       { bg: '#6366f1', border: '#a5b4fc', label: 'ETH',       shape: 'hexagon' },
  EMAIL:            { bg: '#06b6d4', border: '#67e8f9', label: 'EMAIL',     shape: 'ellipse' },
  GSTIN:            { bg: '#f97316', border: '#fdba74', label: 'GSTIN',     shape: 'ellipse' },
  SEBI_REG:         { bg: '#ec4899', border: '#f9a8d4', label: 'SEBI',      shape: 'ellipse' },
  URL_DOMAIN:       { bg: '#8b5cf6', border: '#c4b5fd', label: 'URL',       shape: 'ellipse' },
  INSTAGRAM_HANDLE: { bg: '#e11d48', border: '#fda4af', label: 'INSTA',     shape: 'ellipse' },
}

const SRC_STYLE = { bg: '#059669', border: '#6ee7b7' }

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CY_STYLE: any[] = [
  // ── Base node ──
  { selector: 'node', style: {
    label: 'data(label)', 'font-family': '"Inter",system-ui,sans-serif', 'font-size': 11,
    color: '#cbd5e1', 'text-valign': 'bottom', 'text-margin-y': 10,
    'text-outline-color': '#080e1a', 'text-outline-width': 2,
    'text-wrap': 'wrap', 'text-max-width': '150',
    'border-width': 2.5, 'border-opacity': 0.6,
    width: 'data(nodeSize)', height: 'data(nodeSize)',
    'background-color': '#475569', 'border-color': '#64748b',
    'background-opacity': 0.9,
    'overlay-padding': '6px',
    'transition-property': 'border-width, border-color, border-opacity, background-opacity',
    'transition-duration': 200,
  }},
  // ── Identifier nodes — circles, prominent ──
  ...Object.entries(ID_STYLES).map(([t, s]) => ({
    selector: `node[nodeType="${t}"]`,
    style: {
      'background-color': s.bg, 'border-color': s.border,
      shape: s.shape, 'border-opacity': 0.8,
      'font-size': 13, 'font-weight': 600, color: '#f1f5f9',
    },
  })),
  // ── Source nodes — smaller, subtle, pentagon shape ──
  { selector: 'node[nodeGroup="source"]', style: {
    'background-color': SRC_STYLE.bg, 'border-color': SRC_STYLE.border,
    shape: 'pentagon', 'font-size': 10, color: '#86efac',
    'border-width': 2, 'border-opacity': 0.5, 'background-opacity': 0.7,
  }},
  // ── NLP entity nodes — small circles ──
  { selector: 'node[nodeGroup="entity"]', style: { 'font-size': 9, shape: 'ellipse' }},
  // ── Base edge — subtle ──
  { selector: 'edge', style: {
    width: 1.5, 'line-color': '#1e293b', 'curve-style': 'bezier',
    label: 'data(label)', 'font-size': 9, color: '#475569',
    'text-outline-color': '#080e1a', 'text-outline-width': 1.5,
    'text-rotation': 'autorotate', 'text-margin-y': -8,
    'line-opacity': 0.6,
  }},
  // ── Co-occurrence — RED, thick, solid ──
  { selector: 'edge[edgeType="co_occur"]', style: {
    'line-color': '#dc2626', width: 4, color: '#fca5a5',
    'font-size': 11, 'font-weight': 700, 'line-opacity': 0.9,
  }},
  // ── Seen-in — green dotted ──
  { selector: 'edge[edgeType="seen_in"]', style: {
    'line-color': '#059669', 'line-style': 'dotted', width: 1.5,
    color: '#6ee7b7', 'line-opacity': 0.5,
  }},
  // ── Interaction states ──
  { selector: 'node:active', style: { 'border-width': 4, 'border-color': '#e2e8f0', 'border-opacity': 1 }},
  { selector: '.dimmed', style: { opacity: 0.1 }},
  { selector: '.highlighted', style: { opacity: 1 }},
  { selector: '.highlighted-node', style: { opacity: 1, 'border-width': 4, 'border-color': '#e2e8f0', 'border-opacity': 1, 'background-opacity': 1 }},
]

// ── Component ──────────────────────────────────────────────────────────

interface Props {
  topicId: string
  onClose: () => void
}

export default function EntityGraph({ topicId, onClose }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const [selectedNode, setSelectedNode] = useState<{ label: string; type: string; conns: string } | null>(null)

  const { data: entityGraph, isLoading: l1 } = useQuery({
    queryKey: ['entity-graph', topicId],
    queryFn: () => intelligenceApi.entityGraph(topicId, 1, 200),
    staleTime: 300_000,
  })

  const { data: idClusters = [], isLoading: l2 } = useQuery({
    queryKey: ['identifier-clusters-graph', topicId],
    queryFn: () => identifiersApi.clusters(topicId, undefined, 50),
    staleTime: 300_000,
  })

  const detailQueries = useQueries({
    queries: idClusters.map(c => ({
      queryKey: ['cluster-detail-graph', c.id, topicId] as const,
      queryFn: () => identifiersApi.clusterDetail(c.id, topicId),
      staleTime: 300_000,
      enabled: idClusters.length > 0,
    })),
  })

  const l3 = detailQueries.some(q => q.isLoading)
  const isLoading = l1 || l2 || l3
  const details: ClusterDetail[] = detailQueries.filter(q => q.data).map(q => q.data!)

  const initGraph = useCallback(() => {
    if (!containerRef.current) return
    if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null }

    // Build graph
    const nodes = new Map<string, { id: string; label: string; type: string; group: string; size: number }>()
    const edgeMap = new Map<string, { source: string; target: string; label: string; edgeType: string }>()
    const idToSrc = new Map<string, Map<string, number>>()
    const ciToIds = new Map<string, Set<string>>()

    for (const d of details) {
      const nid = `id:${d.identifier_type}:${d.identifier_value}`
      const lbl = d.identifier_value
      const sz = 50 + Math.min(d.source_count * 10, 30)
      if (!nodes.has(nid)) nodes.set(nid, { id: nid, label: lbl, type: d.identifier_type, group: 'identifier', size: sz })

      for (const item of d.items) {
        const sid = `src:${item.source_name}`
        if (!nodes.has(sid)) nodes.set(sid, { id: sid, label: item.source_name, type: 'source', group: 'source', size: 36 })
        if (!idToSrc.has(nid)) idToSrc.set(nid, new Map())
        const m = idToSrc.get(nid)!; m.set(sid, (m.get(sid) ?? 0) + 1)
        if (!ciToIds.has(item.content_item_id)) ciToIds.set(item.content_item_id, new Set())
        ciToIds.get(item.content_item_id)!.add(nid)
      }
    }

    for (const [nid, sm] of idToSrc)
      for (const [sid, c] of sm)
        edgeMap.set(`e:${nid}-${sid}`, { source: nid, target: sid, label: `${c} msg${c > 1 ? 's' : ''}`, edgeType: 'seen_in' })

    const co = new Map<string, number>()
    for (const [, s] of ciToIds) { const a = [...s]; for (let i = 0; i < a.length; i++) for (let j = i + 1; j < a.length; j++) { const k = [a[i], a[j]].sort().join('|'); co.set(k, (co.get(k) ?? 0) + 1) } }
    for (const [k, c] of co) { const [a, b] = k.split('|'); edgeMap.set(`co:${k}`, { source: a, target: b, label: `co-occur ${c}x`, edgeType: 'co_occur' }) }

    if (entityGraph?.nodes?.length) {
      for (const n of entityGraph.nodes) { const id = `ent:${n.entity}`; if (!nodes.has(id)) nodes.set(id, { id, label: n.entity, type: n.type, group: 'entity', size: 28 }) }
      for (const e of entityGraph.edges) edgeMap.set(`ee:${e.entity_a}-${e.entity_b}`, { source: `ent:${e.entity_a}`, target: `ent:${e.entity_b}`, label: `${e.count}x`, edgeType: 'entity' })
    }

    if (nodes.size === 0) return

    const elements: cytoscape.ElementDefinition[] = [
      ...Array.from(nodes.values()).map(n => ({ data: { id: n.id, label: n.label, nodeType: n.type, nodeGroup: n.group, nodeSize: n.size } })),
      ...Array.from(edgeMap.values()).map((e, i) => ({ data: { id: `edge-${i}`, source: e.source, target: e.target, label: e.label, edgeType: e.edgeType } })),
    ]

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: CY_STYLE,
      layout: { name: 'cose', animate: true, animationDuration: 800, animationEasing: 'ease-out-cubic', nodeRepulsion: () => 12000, idealEdgeLength: () => 200, gravity: 0.3, numIter: 500, padding: 100, nodeDimensionsIncludeLabels: true } as cytoscape.CoseLayoutOptions,
      minZoom: 0.2, maxZoom: 4,
    })

    // Click node — highlight neighbors
    cyRef.current.on('tap', 'node', (evt) => {
      const cy = cyRef.current!
      const node = evt.target
      const d = node.data()
      cy.elements().addClass('dimmed')
      node.removeClass('dimmed').addClass('highlighted-node')
      node.neighborhood().removeClass('dimmed').addClass('highlighted')
      const conns = node.connectedEdges().map((e: cytoscape.EdgeSingular) => e.data('label')).join(', ')
      setSelectedNode({ label: d.label.replace('\n', ': '), type: d.nodeType, conns: conns || 'No connections' })
    })

    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) {
        cyRef.current!.elements().removeClass('dimmed highlighted highlighted-node')
        setSelectedNode(null)
      }
    })

    // Hover
    cyRef.current.on('mouseover', 'node', (e) => { e.target.style('border-width', 5); containerRef.current!.style.cursor = 'pointer' })
    cyRef.current.on('mouseout', 'node', (e) => { if (!e.target.hasClass('highlighted-node')) e.target.style('border-width', 3); containerRef.current!.style.cursor = 'default' })
  }, [details, entityGraph])

  useEffect(() => {
    if (!isLoading && details.length > 0) initGraph()
    return () => { cyRef.current?.destroy(); cyRef.current = null }
  }, [isLoading, initGraph])

  // ESC to close
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 bg-[#080e1a] flex flex-col animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-anveshak-border/30 bg-[#0f1729] shrink-0">
        <div className="flex items-center gap-6">
          <span className="text-sm font-semibold text-text-primary tracking-tight">Intelligence Graph</span>
          <div className="flex items-center gap-4 text-[10px] text-text-muted">
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full inline-block" style={{backgroundColor:'#22c55e'}}/> Phone</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full inline-block" style={{backgroundColor:'#0ea5e9'}}/> Telegram</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full inline-block" style={{backgroundColor:'#a855f7'}}/> UPI</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full inline-block" style={{backgroundColor:'#f59e0b'}}/> Crypto</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 inline-block" style={{backgroundColor:'#059669', clipPath:'polygon(50% 0%, 100% 38%, 82% 100%, 18% 100%, 0% 38%)'}}/> Source</span>
            <span className="text-anveshak-border ml-2">|</span>
            <span className="flex items-center gap-1.5"><span className="w-5 h-0.5 inline-block bg-red-500 rounded"/> Same message</span>
            <span className="flex items-center gap-1.5"><span className="w-5 h-0.5 inline-block border-t-2 border-dashed border-emerald-500"/> Found in</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => cyRef.current?.fit(undefined, 80)} className="text-[10px] text-text-muted hover:text-text-primary px-2.5 py-1 rounded border border-anveshak-border/50 hover:border-anveshak-border transition-colors">Fit</button>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors text-lg px-2 py-1" aria-label="Close">✕</button>
        </div>
      </div>

      {/* Graph */}
      <div className="flex-1 relative">
        {isLoading ? (
          <div className="flex items-center justify-center h-full"><Spinner label="Building intelligence graph..." /></div>
        ) : details.length === 0 && (!entityGraph || entityGraph.node_count === 0) ? (
          <div className="flex items-center justify-center h-full text-text-muted text-sm">No graph data available yet.</div>
        ) : (
          <div ref={containerRef} className="w-full h-full" />
        )}

        {/* Selected node panel */}
        {selectedNode && (
          <div className="absolute bottom-4 left-4 right-4 max-w-md bg-[#0f1729]/95 backdrop-blur-sm border border-anveshak-border/50 rounded-xl px-5 py-4 shadow-2xl">
            <span className="text-[9px] text-text-muted uppercase tracking-widest font-bold">{selectedNode.type.replace(/_/g, ' ')}</span>
            <p className="text-base text-text-primary font-semibold mt-0.5">{selectedNode.label}</p>
            <p className="text-[11px] text-text-muted mt-1">{selectedNode.conns}</p>
          </div>
        )}
      </div>
    </div>
  )
}
