import apiClient from './client'
import type { ReleaseGroup, ReleaseGroupSummary } from './types'

export const releaseGroupsApi = {
  getAll(params?: {
    sort_by?: string
    sort_order?: string
    preferred_only?: boolean
  }): Promise<ReleaseGroup[]> {
    return apiClient.get<ReleaseGroup[]>('/v1/release-groups', params)
  },

  getSummary(): Promise<ReleaseGroupSummary> {
    return apiClient.get<ReleaseGroupSummary>('/v1/release-groups/summary')
  },

  getPreferred(): Promise<string[]> {
    return apiClient.get<string[]>('/v1/release-groups/preferred')
  },

  getBlocked(): Promise<string[]> {
    return apiClient.get<string[]>('/v1/release-groups/blocked')
  },

  getGroup(groupName: string): Promise<ReleaseGroup> {
    return apiClient.get<ReleaseGroup>(`/v1/release-groups/${groupName}`)
  },

  updatePreference(
    groupName: string,
    updates: {
      is_preferred?: boolean
      is_blocked?: boolean
      priority?: number
      notes?: string
    }
  ): Promise<ReleaseGroup> {
    return apiClient.patch<ReleaseGroup>(`/v1/release-groups/${groupName}`, updates)
  },
}
