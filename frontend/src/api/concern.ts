import api from './client'

/**
 * Concern taxonomy facet — issue #36.
 *
 * Categories are filters the analyst chooses to apply. They change which
 * narratives appear and never the order of the ones that remain, and the
 * system never surfaces a category unprompted. See ADR 0001.
 */

export interface ConcernCategory {
  id: string
  label: string
  definition: string
}

export interface ConcernTaxonomy {
  version: number
  /** Whose definition of concerning this is. */
  owner: string
  categories: ConcernCategory[]
}

export interface ConcernScopedCluster {
  id: string
  label: string | null
  item_count: number
  independent_source_count: number
  created_at: string
  concern: Record<string, number>
}

export const concernApi = {
  /** Fetched when the analyst opens the filter, never volunteered. */
  taxonomy: () =>
    api.get<ConcernTaxonomy>('/api/v1/concern-taxonomy').then((r) => r.data),

  clustersByConcern: (topicId: string, categories: string[]) =>
    api
      .get<ConcernScopedCluster[]>(`/api/v1/topics/${topicId}/clusters/by-concern`, {
        params: { categories },
        paramsSerializer: {
          indexes: null,
        },
      })
      .then((r) => r.data),
}
