import apiClient from './client'
import type { IPTTorrent, IPTScanResult, TorrentMetadata } from './types'

// Backend response types (different from frontend types)
interface BackendIPTTorrent {
  id: string
  name: string
  link: string
  size: string
  seeders: number
  leechers: number
  added: string
  isNew: boolean
  downloadUrl: string
  timestamp: string
  metadata?: TorrentMetadata
}

interface BackendIPTResponse {
  success: boolean
  timestamp: string
  results: {
    total: number
    new: number
    torrents: BackendIPTTorrent[]
  }
}

// Helper to extract quality from torrent name
function extractQuality(name: string): string {
  if (name.includes('2160p') || name.includes('UHD')) return '2160p'
  if (name.includes('1080p')) return '1080p'
  if (name.includes('720p')) return '720p'
  return 'Unknown'
}

// Helper to extract category from torrent name
function extractCategory(name: string): string {
  if (name.includes('Remux') || name.includes('REMUX')) return 'Remux'
  if (name.includes('BluRay') || name.includes('Blu-ray')) return 'BluRay'
  if (name.includes('WEB')) return 'WEB'
  return 'Other'
}

// Transform backend torrent to frontend format
function transformTorrent(torrent: BackendIPTTorrent): IPTTorrent {
  return {
    title: torrent.name,
    url: torrent.link,
    size: torrent.size,
    seeders: torrent.seeders,
    leechers: torrent.leechers,
    upload_date: torrent.added,
    category: extractCategory(torrent.name),
    quality: extractQuality(torrent.name),
    isNew: torrent.isNew,
    metadata: torrent.metadata,
  }
}

export const iptApi = {
  // Trigger IPT scan
  async triggerScan(): Promise<{ message: string }> {
    const response = await apiClient.post<BackendIPTResponse>('/v1/ipt/scan')
    return { message: 'Scan triggered successfully' }
  },

  // Get latest IPT scan results
  async getResults(): Promise<IPTScanResult> {
    const response = await apiClient.get<BackendIPTResponse>('/v1/ipt/results')
    return {
      total: response.results.total,
      new: response.results.new,
      torrents: response.results.torrents.map(transformTorrent),
    }
  },

  // Get raw results with timestamp
  async getResultsRaw(): Promise<BackendIPTResponse> {
    return await apiClient.get<BackendIPTResponse>('/v1/ipt/results')
  },

  // Get cached torrents
  async getCachedTorrents(): Promise<IPTTorrent[]> {
    const response = await apiClient.get<BackendIPTTorrent[]>('/v1/ipt/cache')
    return response.map(transformTorrent)
  },

  // Clear IPT cache
  clearCache(): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/ipt/cache/clear')
  },

  // Check IPT scraper service health
  checkHealth(): Promise<{ status: string; message: string }> {
    return apiClient.get<{ status: string; message: string }>('/v1/ipt/health')
  },

  // Download torrent via qbitcopy pipeline
  async downloadTorrent(params: {
    title: string
    year?: number
    download_url: string
    in_radarr: boolean
  }): Promise<{ success: boolean; message: string; movie_path?: string; added_to_radarr?: boolean }> {
    return apiClient.post('/v1/ipt/download', params)
  },
}
