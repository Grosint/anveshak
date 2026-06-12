import api from './client'

export interface EntityNode {
  entity: string
  type: string
}

export interface EntityEdge {
  entity_a: string
  type_a: string
  entity_b: string
  type_b: string
  count: number
}

export interface EntityGraph {
  topic_id: string
  nodes: EntityNode[]
  edges: EntityEdge[]
  node_count: number
  edge_count: number
}

export const intelligenceApi = {
  entityGraph: (topicId: string, minCount = 2, limit = 100) =>
    api
      .get<EntityGraph>(`/api/v1/topics/${topicId}/entity-graph`, {
        params: { min_count: minCount, limit },
      })
      .then((r) => r.data),
}
