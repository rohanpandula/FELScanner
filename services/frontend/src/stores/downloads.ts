import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { downloadsApi } from '@/api'
import type { PendingDownload, ActiveTorrent, DownloadHistory } from '@/api/types'
import { useAppStore } from './app'

export const useDownloadsStore = defineStore('downloads', () => {
  // State
  const pendingDownloads = ref<PendingDownload[]>([])
  const activeTorrents = ref<ActiveTorrent[]>([])
  const downloadHistory = ref<DownloadHistory[]>([])
  const isLoading = ref(false)

  // Getters
  const hasPendingDownloads = computed(() => pendingDownloads.value.length > 0)
  const hasActiveTorrents = computed(() => activeTorrents.value.length > 0)
  const pendingCount = computed(() => pendingDownloads.value.length)
  const activeCount = computed(() => activeTorrents.value.length)

  const downloadingTorrents = computed(() => {
    return activeTorrents.value.filter((t) => t.state === 'downloading' || t.state === 'metaDL')
  })

  const seedingTorrents = computed(() => {
    return activeTorrents.value.filter((t) => t.state === 'uploading' || t.state === 'stalledUP')
  })

  const completedTorrents = computed(() => {
    return activeTorrents.value.filter((t) => t.state === 'pausedUP')
  })

  // Actions
  async function fetchPendingDownloads() {
    isLoading.value = true
    try {
      pendingDownloads.value = await downloadsApi.getPendingDownloads()
    } catch (error) {
      console.error('Failed to fetch pending downloads:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchActiveTorrents() {
    isLoading.value = true
    try {
      activeTorrents.value = await downloadsApi.getActiveTorrents()
    } catch (error) {
      console.error('Failed to fetch active torrents:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchDownloadHistory(limit: number = 50) {
    isLoading.value = true
    try {
      downloadHistory.value = await downloadsApi.getDownloadHistory(limit)
    } catch (error) {
      console.error('Failed to fetch download history:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function approveDownload(downloadId: number) {
    const appStore = useAppStore()
    try {
      const response = await downloadsApi.approveDownload(downloadId)
      appStore.addFlashMessage('success', response.message || 'Download approved')

      // Remove from pending list
      const index = pendingDownloads.value.findIndex((d) => d.id === downloadId)
      if (index !== -1) {
        pendingDownloads.value.splice(index, 1)
      }

      // Refresh active torrents
      await fetchActiveTorrents()
    } catch (error: any) {
      appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to approve download')
      throw error
    }
  }

  async function declineDownload(downloadId: number) {
    const appStore = useAppStore()
    try {
      const response = await downloadsApi.declineDownload(downloadId)
      appStore.addFlashMessage('success', response.message || 'Download declined')

      // Remove from pending list
      const index = pendingDownloads.value.findIndex((d) => d.id === downloadId)
      if (index !== -1) {
        pendingDownloads.value.splice(index, 1)
      }
    } catch (error: any) {
      appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to decline download')
      throw error
    }
  }

  async function cleanupExpired() {
    const appStore = useAppStore()
    try {
      const response = await downloadsApi.cleanupExpired()
      appStore.addFlashMessage('success', `${response.count} expired downloads cleaned up`)
      await fetchPendingDownloads()
    } catch (error: any) {
      appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to cleanup expired downloads')
    }
  }

  async function clearHistory() {
    const appStore = useAppStore()
    try {
      const response = await downloadsApi.clearHistory()
      appStore.addFlashMessage('success', response.message || 'History cleared')
      downloadHistory.value = []
    } catch (error: any) {
      appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to clear history')
    }
  }

  function reset() {
    pendingDownloads.value = []
    activeTorrents.value = []
    downloadHistory.value = []
  }

  return {
    // State
    pendingDownloads,
    activeTorrents,
    downloadHistory,
    isLoading,

    // Getters
    hasPendingDownloads,
    hasActiveTorrents,
    pendingCount,
    activeCount,
    downloadingTorrents,
    seedingTorrents,
    completedTorrents,

    // Actions
    fetchPendingDownloads,
    fetchActiveTorrents,
    fetchDownloadHistory,
    approveDownload,
    declineDownload,
    cleanupExpired,
    clearHistory,
    reset,
  }
})
