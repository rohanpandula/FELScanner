import apiClient from './client'
import type { PendingDownload, ActiveTorrent, DownloadHistory } from './types'

export const downloadsApi = {
  // Get pending downloads awaiting approval
  getPendingDownloads(): Promise<PendingDownload[]> {
    return apiClient.get<PendingDownload[]>('/v1/downloads/pending')
  },

  // Approve a download
  approveDownload(downloadId: number): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>(`/v1/downloads/${downloadId}/approve`)
  },

  // Decline a download
  declineDownload(downloadId: number): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>(`/v1/downloads/${downloadId}/decline`)
  },

  // Get active torrents from qBittorrent
  getActiveTorrents(): Promise<ActiveTorrent[]> {
    return apiClient.get<ActiveTorrent[]>('/v1/downloads/active')
  },

  // Get download history
  getDownloadHistory(limit: number = 50): Promise<DownloadHistory[]> {
    return apiClient.get<DownloadHistory[]>('/v1/downloads/history', { limit })
  },

  // Clear download history
  clearHistory(): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/downloads/history/clear')
  },

  // Cleanup expired downloads
  cleanupExpired(): Promise<{ message: string; count: number }> {
    return apiClient.post<{ message: string; count: number }>('/v1/downloads/cleanup')
  },
}
