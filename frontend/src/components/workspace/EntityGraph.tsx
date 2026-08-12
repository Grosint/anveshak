import { useEffect, useRef, useCallback, useState, useMemo, lazy, Suspense } from 'react'
import { useQuery, useQueries } from '@tanstack/react-query'
import cytoscape from 'cytoscape'
import { intelligenceApi } from '../../api/intelligence'
import { identifiersApi, ClusterDetail } from '../../api/identifiers'
import { Spinner } from '../ui/Spinner'

const DrishtiPreview = lazy(() => import('./DrishtiPreview'))

// ── Visual config ──────────────────────────────────────────────────────

const ID_STYLES: Record<string, { bg: string; border: string; label: string; shape: string }> = {
  PHONE_IN:         { bg: '#22c55e', border: '#86efac', label: 'Phone',      shape: 'ellipse' },
  PHONE_INTL:       { bg: '#14b8a6', border: '#5eead4', label: 'Intl Phone', shape: 'ellipse' },
  UPI:              { bg: '#a855f7', border: '#d8b4fe', label: 'UPI',        shape: 'ellipse' },
  TELEGRAM_HANDLE:  { bg: '#0ea5e9', border: '#7dd3fc', label: 'Telegram',   shape: 'ellipse' },
  CRYPTO_BTC:       { bg: '#f59e0b', border: '#fde68a', label: 'BTC',        shape: 'hexagon' },
  CRYPTO_ETH:       { bg: '#6366f1', border: '#a5b4fc', label: 'ETH',        shape: 'hexagon' },
  EMAIL:            { bg: '#06b6d4', border: '#67e8f9', label: 'Email',      shape: 'ellipse' },
  GSTIN:            { bg: '#f97316', border: '#fdba74', label: 'GSTIN',      shape: 'ellipse' },
  SEBI_REG:         { bg: '#ec4899', border: '#f9a8d4', label: 'SEBI',       shape: 'ellipse' },
  URL_DOMAIN:       { bg: '#8b5cf6', border: '#c4b5fd', label: 'URL',        shape: 'ellipse' },
  INSTAGRAM_HANDLE: { bg: '#e11d48', border: '#fda4af', label: 'Instagram',  shape: 'ellipse' },
  FACEBOOK_HANDLE:  { bg: '#3b82f6', border: '#93c5fd', label: 'Facebook',   shape: 'ellipse' },
  X_HANDLE:         { bg: '#64748b', border: '#94a3b8', label: 'X',          shape: 'ellipse' },
}

const SRC_STYLE = { bg: '#059669', border: '#6ee7b7' }

// ── Story views ────────────────────────────────────────────────────────

interface StoryView {
  id: string
  title: string
  subtitle: string
  icon: string
  idTypes: Set<string>
  showSources: boolean
  showEntities: boolean
  entityTypes: Set<string>
  color: string
}

const VIEWS: StoryView[] = [
  {
    id: 'money', title: 'Money Trail', subtitle: 'How funds move between accounts', icon: '💰',
    idTypes: new Set(['PHONE_IN', 'PHONE_INTL', 'UPI', 'CRYPTO_BTC', 'CRYPTO_ETH', 'GSTIN', 'SEBI_REG']),
    showSources: true, showEntities: false, entityTypes: new Set(), color: '#22c55e',
  },
  {
    id: 'social', title: 'Social Network', subtitle: 'Who communicates with whom', icon: '🔗',
    idTypes: new Set(['TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE', 'FACEBOOK_HANDLE', 'X_HANDLE', 'EMAIL']),
    showSources: true, showEntities: false, entityTypes: new Set(), color: '#0ea5e9',
  },
  {
    id: 'footprint', title: 'Digital Footprint', subtitle: 'Where identifiers were found', icon: '🌐',
    idTypes: new Set(['URL_DOMAIN']),
    showSources: true, showEntities: false, entityTypes: new Set(), color: '#8b5cf6',
  },
  {
    id: 'actors', title: 'Key Players', subtitle: 'People and organizations mentioned', icon: '👤',
    idTypes: new Set(), showSources: false, showEntities: true, entityTypes: new Set(['PERSON', 'ORG']),
    color: '#f59e0b',
  },
  {
    id: 'full', title: 'Full Picture', subtitle: 'All layers combined', icon: '🔍',
    idTypes: new Set(), showSources: true, showEntities: true, entityTypes: new Set(), color: '#3b82f6',
  },
  {
    id: 'drishti', title: 'Drishti Preview', subtitle: 'Cross-topic entity resolution', icon: '🔮',
    idTypes: new Set(), showSources: false, showEntities: false, entityTypes: new Set(), color: '#a855f7',
  },
]

// ── Helpers ────────────────────────────────────────────────────────────

function truncateLabel(text: string, max: number = 24): string {
  if (text.length <= max) return text
  return text.slice(0, max - 1) + '…'
}

// Common infrastructure domains that appear in every article — hub noise, not intelligence
const NOISE_DOMAINS = new Set([
  'google.com', 'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
  'bit.ly', 't.co', 'apple.co', 'apple.com', 'linkedin.com', 'whatsapp.com',
  'tiktok.com', 'pinterest.com', 'reddit.com', 'wikipedia.org', 'amazon.com',
  'googleapis.com', 'gstatic.com', 'cloudflare.com', 'cdn.ampproject.org',
  'play.google.com', 'apps.apple.com', 'wa.me',
])

function isNoiseDomain(value: string): boolean {
  const v = value.toLowerCase().trim()
  return NOISE_DOMAINS.has(v)
}

function isNoiseEntity(value: string): boolean {
  // HTML artifacts leaking through NER
  return /[<>=]/.test(value) || value.startsWith('href') || value.startsWith('http') || value.length < 2
}

interface GraphNode {
  id: string; label: string; fullLabel: string; type: string
  group: 'identifier' | 'source' | 'entity'; size: number; degree: number
}

interface GraphEdge {
  id: string; source: string; target: string; label: string
  edgeType: 'seen_in' | 'co_occur' | 'entity'; weight: number
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CY_STYLE: any[] = [
  { selector: 'node', style: {
    label: 'data(label)', 'font-family': '"Inter",system-ui,sans-serif', 'font-size': 11,
    color: '#cbd5e1', 'text-valign': 'bottom', 'text-margin-y': 10,
    'text-outline-color': '#080e1a', 'text-outline-width': 2,
    'text-wrap': 'wrap', 'text-max-width': '150',
    'border-width': 2.5, 'border-opacity': 0.6,
    width: 'data(nodeSize)', height: 'data(nodeSize)',
    'background-color': '#475569', 'border-color': '#64748b',
    'background-opacity': 0.9, 'overlay-padding': '6px',
    'transition-property': 'border-width, border-color, border-opacity, background-opacity',
    'transition-duration': 200,
  }},
  ...Object.entries(ID_STYLES).map(([t, s]) => ({
    selector: `node[nodeType="${t}"]`,
    style: { 'background-color': s.bg, 'border-color': s.border, shape: s.shape, 'border-opacity': 0.8, 'font-size': 13, 'font-weight': 600, color: '#f1f5f9' },
  })),
  { selector: 'node[nodeGroup="source"]', style: {
    'background-color': SRC_STYLE.bg, 'border-color': SRC_STYLE.border, shape: 'pentagon',
    'font-size': 10, color: '#86efac', 'border-width': 2, 'border-opacity': 0.5, 'background-opacity': 0.7,
  }},
  { selector: 'node[nodeGroup="entity"]', style: { 'font-size': 10, shape: 'round-rectangle', 'background-color': '#475569', 'border-color': '#94a3b8' }},
  { selector: 'node[nodeType="PERSON"]', style: { 'background-color': '#f59e0b', 'border-color': '#fde68a', shape: 'ellipse', 'font-weight': 600 }},
  { selector: 'node[nodeType="ORG"]', style: { 'background-color': '#6366f1', 'border-color': '#a5b4fc', shape: 'round-rectangle', 'font-weight': 600 }},
  { selector: 'edge', style: {
    width: 'data(edgeWidth)', 'line-color': '#1e293b', 'curve-style': 'bezier',
    label: 'data(label)', 'font-size': 9, color: '#475569',
    'text-outline-color': '#080e1a', 'text-outline-width': 1.5,
    'text-rotation': 'autorotate', 'text-margin-y': -8, 'line-opacity': 0.6,
  }},
  { selector: 'edge[edgeType="co_occur"]', style: { 'line-color': '#dc2626', color: '#fca5a5', 'font-size': 11, 'font-weight': 700, 'line-opacity': 0.9 }},
  { selector: 'edge[edgeType="seen_in"]', style: { 'line-color': '#059669', 'line-style': 'dotted', color: '#6ee7b7', 'line-opacity': 0.5 }},
  { selector: 'edge[edgeType="entity"]', style: { 'line-color': '#475569', color: '#94a3b8', 'line-opacity': 0.4 }},
  { selector: 'node:active', style: { 'border-width': 4, 'border-color': '#e2e8f0', 'border-opacity': 1 }},
  { selector: '.dimmed', style: { opacity: 0.08 }},
  { selector: '.highlighted', style: { opacity: 1 }},
  { selector: '.highlighted-node', style: { opacity: 1, 'border-width': 5, 'border-color': '#f1f5f9', 'border-opacity': 1, 'background-opacity': 1 }},
]

// ── Component ──────────────────────────────────────────────────────────

interface Props { topicId: string; onClose: () => void }

interface SelectedNodeInfo {
  label: string; fullLabel: string; type: string; group: string
  neighbors: { label: string; type: string; via: string }[]
}

export default function EntityGraph({ topicId, onClose }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const [activeView, setActiveView] = useState('money')
  const [selectedNode, setSelectedNode] = useState<SelectedNodeInfo | null>(null)

  const { data: entityGraph, isLoading: l1 } = useQuery({
    queryKey: ['entity-graph', topicId],
    queryFn: () => intelligenceApi.entityGraph(topicId, 2, 150),
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

  // ── Build full graph data once ──
  const { allNodes, allEdges } = useMemo(() => {
    const nodes = new Map<string, GraphNode>()
    const edges = new Map<string, GraphEdge>()
    const idToSrc = new Map<string, Map<string, number>>()
    const ciToIds = new Map<string, Set<string>>()

    for (const d of details) {
      // Skip noise domains (google.com, facebook.com etc.) — they connect to everything
      if (d.identifier_type === 'URL_DOMAIN' && isNoiseDomain(d.identifier_value)) continue
      const nid = `id:${d.identifier_type}:${d.identifier_value}`
      if (!nodes.has(nid)) nodes.set(nid, { id: nid, label: truncateLabel(d.identifier_value), fullLabel: d.identifier_value, type: d.identifier_type, group: 'identifier', size: 50, degree: 0 })
      for (const item of d.items) {
        const sid = `src:${item.source_name}`
        if (!nodes.has(sid)) nodes.set(sid, { id: sid, label: truncateLabel(item.source_name, 20), fullLabel: item.source_name, type: 'source', group: 'source', size: 36, degree: 0 })
        if (!idToSrc.has(nid)) idToSrc.set(nid, new Map())
        const m = idToSrc.get(nid)!; m.set(sid, (m.get(sid) ?? 0) + 1)
        if (!ciToIds.has(item.content_item_id)) ciToIds.set(item.content_item_id, new Set())
        ciToIds.get(item.content_item_id)!.add(nid)
      }
    }

    for (const [nid, sm] of idToSrc)
      for (const [sid, c] of sm)
        edges.set(`e:${nid}-${sid}`, { id: `e:${nid}-${sid}`, source: nid, target: sid, label: `${c}×`, edgeType: 'seen_in', weight: c })

    const co = new Map<string, number>()
    for (const [, s] of ciToIds) { const a = [...s]; for (let i = 0; i < a.length; i++) for (let j = i + 1; j < a.length; j++) { const k = [a[i], a[j]].sort().join('|'); co.set(k, (co.get(k) ?? 0) + 1) } }
    for (const [k, c] of co) { const [a, b] = k.split('|'); edges.set(`co:${k}`, { id: `co:${k}`, source: a, target: b, label: `${c}×`, edgeType: 'co_occur', weight: c }) }

    if (entityGraph?.nodes?.length) {
      for (const n of entityGraph.nodes) {
        if (isNoiseEntity(n.entity)) continue
        const id = `ent:${n.entity}`
        if (!nodes.has(id)) nodes.set(id, { id, label: truncateLabel(n.entity), fullLabel: n.entity, type: n.type, group: 'entity', size: 32, degree: 0 })
      }
      for (const e of entityGraph.edges) {
        if (isNoiseEntity(e.entity_a) || isNoiseEntity(e.entity_b)) continue
        const srcId = `ent:${e.entity_a}`, tgtId = `ent:${e.entity_b}`
        if (nodes.has(srcId) && nodes.has(tgtId)) {
          edges.set(`ee:${e.entity_a}-${e.entity_b}`, { id: `ee:${e.entity_a}-${e.entity_b}`, source: srcId, target: tgtId, label: `${e.count}×`, edgeType: 'entity', weight: e.count })
        }
      }
    }

    for (const e of edges.values()) { const s = nodes.get(e.source); const t = nodes.get(e.target); if (s) s.degree++; if (t) t.degree++ }
    return { allNodes: nodes, allEdges: edges }
  }, [details, entityGraph])

  const view = useMemo(() => VIEWS.find(v => v.id === activeView) ?? VIEWS[0], [activeView])

  // ── Filter for active view ──
  const filteredElements = useMemo(() => {
    const visibleNodeIds = new Set<string>()
    for (const [id, n] of allNodes) {
      if (n.group === 'identifier') { if (view.idTypes.size === 0 || view.idTypes.has(n.type)) visibleNodeIds.add(id) }
      else if (n.group === 'source' && view.showSources) visibleNodeIds.add(id)
      else if (n.group === 'entity' && view.showEntities) { if (view.entityTypes.size === 0 || view.entityTypes.has(n.type)) visibleNodeIds.add(id) }
    }

    // Remove orphan sources
    if (view.showSources && view.id !== 'footprint') {
      const connSrc = new Set<string>()
      for (const e of allEdges.values()) if (e.edgeType === 'seen_in' && visibleNodeIds.has(e.source)) connSrc.add(e.target)
      for (const id of [...visibleNodeIds]) { const n = allNodes.get(id); if (n?.group === 'source' && !connSrc.has(id)) visibleNodeIds.delete(id) }
    }

    const visibleEdges: GraphEdge[] = []
    for (const e of allEdges.values()) if (visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)) visibleEdges.push(e)

    const deg = new Map<string, number>()
    for (const e of visibleEdges) { deg.set(e.source, (deg.get(e.source) ?? 0) + 1); deg.set(e.target, (deg.get(e.target) ?? 0) + 1) }

    const nodeEls: cytoscape.ElementDefinition[] = []
    for (const id of visibleNodeIds) {
      const n = allNodes.get(id)!
      const d = deg.get(id) ?? 0
      const sz = n.group === 'source' ? 30 + Math.min(d * 4, 20) : n.group === 'entity' ? 28 + Math.min(d * 3, 24) : 40 + Math.min(d * 6, 40)
      // In Full Picture, hide labels on low-degree nodes to reduce clutter
      const showLabel = view.id !== 'full' || d >= 2 || n.group === 'identifier'
      nodeEls.push({ data: { id: n.id, label: showLabel ? n.label : '', fullLabel: n.fullLabel, nodeType: n.type, nodeGroup: n.group, nodeSize: sz } })
    }

    const edgeEls: cytoscape.ElementDefinition[] = visibleEdges.map((e, i) => ({
      data: { id: `edge-${i}`, source: e.source, target: e.target, label: e.label, edgeType: e.edgeType, edgeWidth: Math.min(1.5 + e.weight * 1.5, 8) },
    }))

    return [...nodeEls, ...edgeEls]
  }, [allNodes, allEdges, view])

  const viewStats = useMemo(() => {
    let nc = 0, ec = 0
    for (const el of filteredElements) { if (el.data.source) ec++; else nc++ }
    return { nodeCount: nc, edgeCount: ec }
  }, [filteredElements])

  const viewHasData = useMemo(() => {
    const r: Record<string, boolean> = {}
    for (const v of VIEWS) {
      if (v.id === 'drishti') { r[v.id] = true; continue }
      let has = false
      for (const n of allNodes.values()) {
        if (n.group === 'identifier' && (v.idTypes.size === 0 || v.idTypes.has(n.type))) { has = true; break }
        if (n.group === 'entity' && v.showEntities && (v.entityTypes.size === 0 || v.entityTypes.has(n.type))) { has = true; break }
      }
      r[v.id] = has
    }
    return r
  }, [allNodes])

  // ── Render graph ──
  const renderGraph = useCallback(() => {
    if (!containerRef.current) return
    if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null }
    setSelectedNode(null)
    if (filteredElements.length === 0) return

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements: filteredElements,
      style: CY_STYLE,
      layout: {
        name: 'cose', animate: true, animationDuration: 600, animationEasing: 'ease-out-cubic',
        nodeRepulsion: () => view.id === 'full' ? 32000 : 18000,
        idealEdgeLength: () => view.id === 'full' ? 250 : 180,
        gravity: view.id === 'full' ? 0.15 : 0.25,
        numIter: 800, padding: 80, nodeDimensionsIncludeLabels: true,
      } as cytoscape.CoseLayoutOptions,
      minZoom: 0.15, maxZoom: 4,
    })

    cyRef.current.on('tap', 'node', (evt) => {
      const cy = cyRef.current!; const node = evt.target; const d = node.data()
      cy.elements().addClass('dimmed'); node.removeClass('dimmed').addClass('highlighted-node'); node.neighborhood().removeClass('dimmed').addClass('highlighted')
      const neighbors: SelectedNodeInfo['neighbors'] = []
      node.connectedEdges().forEach((edge: cytoscape.EdgeSingular) => {
        const other = edge.source().id() === node.id() ? edge.target() : edge.source()
        neighbors.push({ label: other.data('fullLabel') || other.data('label'), type: other.data('nodeType'), via: edge.data('label') })
      })
      setSelectedNode({ label: d.label, fullLabel: d.fullLabel || d.label, type: d.nodeType, group: d.nodeGroup, neighbors })
    })

    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) { cyRef.current!.elements().removeClass('dimmed highlighted highlighted-node'); setSelectedNode(null) }
    })

    cyRef.current.on('mouseover', 'node', (e) => { e.target.style('border-width', 5); containerRef.current!.style.cursor = 'pointer' })
    cyRef.current.on('mouseout', 'node', (e) => { if (!e.target.hasClass('highlighted-node')) e.target.style('border-width', 3); containerRef.current!.style.cursor = 'default' })
  }, [filteredElements, view])

  useEffect(() => {
    if (!isLoading && filteredElements.length > 0) renderGraph()
    return () => { cyRef.current?.destroy(); cyRef.current = null }
  }, [isLoading, renderGraph])

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  const hasData = allNodes.size > 0

  const legendItems = useMemo(() => {
    const items: { color: string; label: string }[] = []; const seen = new Set<string>()
    for (const el of filteredElements) {
      const t = el.data.nodeType as string; if (!t || seen.has(t) || el.data.source) continue; seen.add(t)
      const s = ID_STYLES[t]; if (s) items.push({ color: s.bg, label: s.label })
      else if (t === 'source') items.push({ color: SRC_STYLE.bg, label: 'Source' })
      else if (t === 'PERSON') items.push({ color: '#f59e0b', label: 'Person' })
      else if (t === 'ORG') items.push({ color: '#6366f1', label: 'Organization' })
      else if (t === 'FAC') items.push({ color: '#475569', label: 'Facility' })
    }
    return items
  }, [filteredElements])

  return (
    <div className="fixed inset-0 z-50 bg-[#080e1a] flex flex-col animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-2.5 border-b border-anveshak-border/30 bg-[#0f1729] shrink-0">
        <div className="flex items-center gap-4">
          <span className="text-sm font-semibold text-text-primary tracking-tight">Intelligence Graph</span>
          <span className="text-xs text-text-muted">{viewStats.nodeCount} nodes · {viewStats.edgeCount} edges</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => cyRef.current?.fit(undefined, 60)} className="text-[10px] text-text-muted hover:text-text-primary px-2 py-1 rounded border border-anveshak-border/50 hover:border-anveshak-border transition-colors">Fit</button>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors text-lg px-2 py-1" aria-label="Close">✕</button>
        </div>
      </div>

      {/* Story view tabs */}
      <div className="flex items-center gap-1 px-5 py-2 border-b border-anveshak-border/20 bg-[#0c1220] shrink-0 overflow-x-auto">
        {VIEWS.map((v) => {
          const active = activeView === v.id
          const hasItems = viewHasData[v.id]
          return (
            <button
              key={v.id}
              onClick={() => setActiveView(v.id)}
              disabled={!hasItems}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                active ? 'text-white shadow-lg' : hasItems ? 'text-text-muted hover:text-text-secondary hover:bg-anveshak-muted/30' : 'text-text-muted/30 cursor-not-allowed'
              }`}
              style={active ? { backgroundColor: v.color + '20', color: v.color, borderBottom: `2px solid ${v.color}` } : undefined}
              aria-pressed={active}
            >
              <span className="text-sm">{v.icon}</span>
              <div className="text-left">
                <div className="font-semibold">{v.title}</div>
                {active && <div className="text-[10px] opacity-70 mt-0.5">{v.subtitle}</div>}
              </div>
            </button>
          )
        })}
      </div>

      {/* Graph + detail */}
      <div className="flex-1 flex min-h-0">
        {activeView === 'drishti' ? (
          <Suspense fallback={<div className="flex-1 flex items-center justify-center bg-[#050a15]"><Spinner label="Loading Drishti Preview..." /></div>}>
            <DrishtiPreview topicId={topicId} />
          </Suspense>
        ) : (
        <>
        <div className="flex-1 relative min-w-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-full"><Spinner label="Building intelligence graph..." /></div>
          ) : !hasData ? (
            <div className="flex items-center justify-center h-full text-text-muted text-sm">No graph data available yet.</div>
          ) : filteredElements.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
              <span className="text-3xl">{view.icon}</span>
              <span className="text-sm">No {view.title.toLowerCase()} data in this topic</span>
            </div>
          ) : (
            <div ref={containerRef} className="w-full h-full" />
          )}

          {legendItems.length > 0 && (
            <div className="absolute bottom-3 left-3 bg-[#0f1729]/90 backdrop-blur-sm border border-anveshak-border/40 rounded-lg px-3 py-2 pointer-events-none">
              <div className="flex flex-wrap items-center gap-3 text-[10px] text-text-muted">
                {legendItems.map((item) => (
                  <span key={item.label} className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: item.color }} />
                    {item.label}
                  </span>
                ))}
                <span className="text-anveshak-border">|</span>
                <span className="flex items-center gap-1"><span className="w-4 h-0.5 inline-block bg-red-500 rounded" /> Co-occurs</span>
                <span className="flex items-center gap-1"><span className="w-4 h-0.5 inline-block border-t-2 border-dashed border-emerald-500" /> Found in</span>
              </div>
            </div>
          )}
        </div>

        {selectedNode && (
          <div className="w-80 border-l border-anveshak-border/30 bg-[#0f1729] flex flex-col shrink-0 overflow-hidden">
            <div className="px-4 py-3 border-b border-anveshak-border/20">
              <div className="flex items-center gap-2 mb-1">
                <span className="w-3 h-3 rounded-full inline-block shrink-0" style={{ backgroundColor: ID_STYLES[selectedNode.type]?.bg ?? '#475569' }} />
                <span className="text-[10px] text-text-muted uppercase tracking-wider font-bold">
                  {ID_STYLES[selectedNode.type]?.label ?? selectedNode.type.replace(/_/g, ' ')}
                </span>
              </div>
              <p className="text-sm text-text-primary font-semibold break-all">{selectedNode.fullLabel}</p>
            </div>
            <div className="flex-1 overflow-y-auto px-4 py-3">
              <h4 className="text-[10px] text-text-muted uppercase tracking-wider font-bold mb-2">Connected to ({selectedNode.neighbors.length})</h4>
              {selectedNode.neighbors.length === 0 ? (
                <p className="text-xs text-text-muted">No connections</p>
              ) : (
                <div className="space-y-1.5">
                  {selectedNode.neighbors.map((nb, i) => (
                    <div key={i} className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-anveshak-muted/20 text-xs">
                      <span className="w-2 h-2 rounded-full inline-block shrink-0" style={{ backgroundColor: ID_STYLES[nb.type]?.bg ?? (nb.type === 'source' ? SRC_STYLE.bg : '#475569') }} />
                      <span className="text-text-primary truncate flex-1">{nb.label}</span>
                      <span className="text-text-muted shrink-0">{nb.via}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
        </>
        )}
      </div>
    </div>
  )
}
