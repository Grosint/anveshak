import { useEffect, useRef, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import cytoscape from 'cytoscape'
import { provenanceApi, type FlowNode, type FlowEdge } from '../../api/provenance'
import { Spinner } from '../ui/Spinner'
import { EmptyState } from '../ui/EmptyState'

const PLATFORM_COLORS: Record<string, string> = {
  web: '#8b5cf6',
  rss: '#f59e0b',
  telegram: '#0ea5e9',
  reddit: '#f97316',
  bluesky: '#3b82f6',
  x: '#64748b',
  youtube: '#ef4444',
}

function platformColor(platform: string): string {
  return PLATFORM_COLORS[platform.toLowerCase()] ?? '#6b7280'
}

function buildElements(
  nodes: FlowNode[],
  temporalEdges: FlowEdge[],
  sharedEdges: FlowEdge[],
) {
  const cyNodes = nodes.map((n) => ({
    data: {
      id: n.id,
      label: `${n.platform.toUpperCase()}\n${n.name.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}`,
      platform: n.platform,
      itemCount: n.item_count,
      bg: platformColor(n.platform),
    },
  }))

  const cyEdges = [
    // Only add temporal edges between consecutive sources (not all pairs)
    ...temporalEdges
      .filter((e) => e.time_delta_hours != null && e.time_delta_hours <= 168) // within 1 week
      .map((e, i) => ({
        data: {
          id: `t-${i}`,
          source: e.source,
          target: e.target,
          label: e.time_delta_hours! < 1
            ? `${Math.round(e.time_delta_hours! * 60)}m`
            : `${e.time_delta_hours!.toFixed(0)}h`,
          edgeType: 'temporal',
        },
      })),
    ...sharedEdges.map((e, i) => ({
      data: {
        id: `s-${i}`,
        source: e.source,
        target: e.target,
        label: `${e.shared_count} shared`,
        edgeType: 'shared',
      },
    })),
  ]

  return [...cyNodes, ...cyEdges]
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CY_STYLE: any[] = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(bg)',
      label: 'data(label)',
      'text-wrap': 'wrap' as const,
      'text-valign': 'bottom' as const,
      'text-halign': 'center' as const,
      'font-size': '9px',
      color: '#94a3b8',
      width: 'mapData(itemCount, 1, 20, 24, 48)',
      height: 'mapData(itemCount, 1, 20, 24, 48)',
      'border-width': 2,
      'border-color': '#1e293b',
    },
  },
  {
    selector: 'edge[edgeType="temporal"]',
    style: {
      'line-color': '#3b82f6',
      'target-arrow-color': '#3b82f6',
      'target-arrow-shape': 'triangle' as const,
      'curve-style': 'bezier' as const,
      width: 2,
      opacity: 0.7,
      label: 'data(label)',
      'font-size': '8px',
      color: '#64748b',
      'text-rotation': 'autorotate' as const,
      'text-background-color': '#0b1222',
      'text-background-opacity': 0.8,
      'text-background-padding': '2px' as unknown as number,
    },
  },
  {
    selector: 'edge[edgeType="shared"]',
    style: {
      'line-color': '#f59e0b',
      'line-style': 'dotted' as const,
      'curve-style': 'bezier' as const,
      width: 1.5,
      opacity: 0.5,
      label: 'data(label)',
      'font-size': '7px',
      color: '#92400e',
      'text-rotation': 'autorotate' as const,
      'text-background-color': '#0b1222',
      'text-background-opacity': 0.8,
      'text-background-padding': '2px' as unknown as number,
    },
  },
]

interface FlowGraphProps {
  clusterId: string
  topicId: string
}

export default function FlowGraph({ clusterId, topicId }: FlowGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['cluster-flow', clusterId, topicId],
    queryFn: () => provenanceApi.clusterFlow(clusterId, topicId),
    enabled: !!clusterId && !!topicId,
  })

  const elements = useMemo(() => {
    if (!data) return []
    return buildElements(data.nodes, data.temporal_edges, data.shared_identifier_edges)
  }, [data])

  useEffect(() => {
    if (!containerRef.current || elements.length === 0) return

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: CY_STYLE,
      layout: {
        name: 'breadthfirst',
        directed: true,
        spacingFactor: 1.5,
        animate: false,
      },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    })

    cyRef.current = cy

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [elements])

  if (isLoading) return <Spinner label="Loading flow..." />

  if (!data || data.nodes.length === 0) {
    return <EmptyState icon="🔗" title="No flow data" description="Not enough sources to show propagation." />
  }

  return (
    <div>
      <div
        ref={containerRef}
        className="w-full h-[300px] bg-[#080e1a] rounded border border-anveshak-border/30"
      />
      {/* Legend */}
      <div className="flex items-center gap-3 mt-2 text-[9px] text-text-muted">
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-blue-500 inline-block" /> temporal flow
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-amber-500 inline-block border-dotted" style={{ borderTop: '2px dotted #f59e0b', height: 0, background: 'none' }} /> shared identifiers
        </span>
      </div>
    </div>
  )
}
