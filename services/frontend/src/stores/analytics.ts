import { defineStore } from 'pinia'
import { ref } from 'vue'
import { analyticsApi } from '@/api/analytics'
import type {
  QualityReport,
  UpgradeOpportunity,
  DuplicateGroup,
  StorageAnalytics,
  ComparisonResult,
} from '@/api/types'

export const useAnalyticsStore = defineStore('analytics', () => {
  const qualityReport = ref<QualityReport | null>(null)
  const upgradeOpportunities = ref<UpgradeOpportunity[]>([])
  const duplicates = ref<DuplicateGroup[]>([])
  const storageAnalytics = ref<StorageAnalytics | null>(null)
  const comparisonResult = ref<ComparisonResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchQualityReport() {
    loading.value = true
    error.value = null
    try {
      qualityReport.value = await analyticsApi.getQualityReport()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch quality report'
    } finally {
      loading.value = false
    }
  }

  async function fetchUpgradeOpportunities() {
    loading.value = true
    error.value = null
    try {
      upgradeOpportunities.value = await analyticsApi.getUpgradeOpportunities()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch upgrade opportunities'
    } finally {
      loading.value = false
    }
  }

  async function fetchDuplicates() {
    loading.value = true
    error.value = null
    try {
      duplicates.value = await analyticsApi.getDuplicates()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch duplicates'
    } finally {
      loading.value = false
    }
  }

  async function fetchStorageAnalytics() {
    loading.value = true
    error.value = null
    try {
      storageAnalytics.value = await analyticsApi.getStorageAnalytics()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch storage analytics'
    } finally {
      loading.value = false
    }
  }

  async function compareMovieWithTorrent(
    movieId: number,
    torrentMetadata: Record<string, any>
  ) {
    loading.value = true
    error.value = null
    try {
      comparisonResult.value = await analyticsApi.compareMovieWithTorrent(
        movieId,
        torrentMetadata
      )
    } catch (e: any) {
      error.value = e.message || 'Failed to compare'
    } finally {
      loading.value = false
    }
  }

  return {
    qualityReport,
    upgradeOpportunities,
    duplicates,
    storageAnalytics,
    comparisonResult,
    loading,
    error,
    fetchQualityReport,
    fetchUpgradeOpportunities,
    fetchDuplicates,
    fetchStorageAnalytics,
    compareMovieWithTorrent,
  }
})
