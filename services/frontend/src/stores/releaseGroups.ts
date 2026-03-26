import { defineStore } from 'pinia'
import { ref } from 'vue'
import { releaseGroupsApi } from '@/api/releaseGroups'
import type { ReleaseGroup, ReleaseGroupSummary } from '@/api/types'

export const useReleaseGroupsStore = defineStore('releaseGroups', () => {
  const groups = ref<ReleaseGroup[]>([])
  const summary = ref<ReleaseGroupSummary | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchGroups(params?: {
    sort_by?: string
    sort_order?: string
    preferred_only?: boolean
  }) {
    loading.value = true
    error.value = null
    try {
      groups.value = await releaseGroupsApi.getAll(params)
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch release groups'
    } finally {
      loading.value = false
    }
  }

  async function fetchSummary() {
    try {
      summary.value = await releaseGroupsApi.getSummary()
    } catch (e: any) {
      error.value = e.message
    }
  }

  async function updatePreference(
    groupName: string,
    updates: {
      is_preferred?: boolean
      is_blocked?: boolean
      priority?: number
      notes?: string
    }
  ) {
    try {
      await releaseGroupsApi.updatePreference(groupName, updates)
      await fetchGroups()
    } catch (e: any) {
      error.value = e.message || 'Failed to update preference'
    }
  }

  return {
    groups,
    summary,
    loading,
    error,
    fetchGroups,
    fetchSummary,
    updatePreference,
  }
})
