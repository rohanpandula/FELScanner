import apiClient from './client'
import type { ActivityFeedResponse, ActivityEvent, ActivitySummary } from './types'

export const activityApi = {
  getFeed(params?: {
    limit?: number
    offset?: number
    event_type?: string
    severity?: string
    movie_id?: number
  }): Promise<ActivityFeedResponse> {
    return apiClient.get<ActivityFeedResponse>('/v1/activity', params)
  },

  getSummary(hours?: number): Promise<ActivitySummary> {
    return apiClient.get<ActivitySummary>('/v1/activity/summary', { hours })
  },

  getEventTypeCounts(): Promise<Record<string, number>> {
    return apiClient.get<Record<string, number>>('/v1/activity/types')
  },

  getMovieTimeline(movieId: number): Promise<ActivityEvent[]> {
    return apiClient.get<ActivityEvent[]>(`/v1/activity/movie/${movieId}`)
  },
}
