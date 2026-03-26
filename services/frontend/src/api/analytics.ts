import apiClient from './client'
import type {
  QualityReport,
  UpgradeOpportunity,
  DuplicateGroup,
  StorageAnalytics,
  ComparisonResult,
} from './types'

export const analyticsApi = {
  getQualityReport(): Promise<QualityReport> {
    return apiClient.get<QualityReport>('/v1/analytics/quality-report')
  },

  getUpgradeOpportunities(): Promise<UpgradeOpportunity[]> {
    return apiClient.get<UpgradeOpportunity[]>('/v1/analytics/upgrade-opportunities')
  },

  getDuplicates(): Promise<DuplicateGroup[]> {
    return apiClient.get<DuplicateGroup[]>('/v1/analytics/duplicates')
  },

  getStorageAnalytics(): Promise<StorageAnalytics> {
    return apiClient.get<StorageAnalytics>('/v1/analytics/storage')
  },

  compareMovieWithTorrent(
    movieId: number,
    torrentMetadata: Record<string, any>
  ): Promise<ComparisonResult> {
    return apiClient.post<ComparisonResult>(`/v1/analytics/compare/${movieId}`, {
      torrent_metadata: torrentMetadata,
    })
  },
}
