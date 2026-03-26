import { defineStore } from 'pinia'
import { ref } from 'vue'
import { activityApi } from '@/api/activity'
import type { ActivityEvent, ActivitySummary } from '@/api/types'

export const useActivityStore = defineStore('activity', () => {
  const events = ref<ActivityEvent[]>([])
  const total = ref(0)
  const summary = ref<ActivitySummary | null>(null)
  const eventTypeCounts = ref<Record<string, number>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchFeed(params?: {
    limit?: number
    offset?: number
    event_type?: string
    severity?: string
    movie_id?: number
  }) {
    loading.value = true
    error.value = null
    try {
      const response = await activityApi.getFeed(params)
      events.value = response.events
      total.value = response.total
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch activity feed'
    } finally {
      loading.value = false
    }
  }

  async function fetchSummary(hours?: number) {
    try {
      summary.value = await activityApi.getSummary(hours)
    } catch (e: any) {
      error.value = e.message
    }
  }

  async function fetchEventTypeCounts() {
    try {
      eventTypeCounts.value = await activityApi.getEventTypeCounts()
    } catch (e: any) {
      error.value = e.message
    }
  }

  return {
    events,
    total,
    summary,
    eventTypeCounts,
    loading,
    error,
    fetchFeed,
    fetchSummary,
    fetchEventTypeCounts,
  }
})
