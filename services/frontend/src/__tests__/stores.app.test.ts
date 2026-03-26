import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from '@/stores/app'

// Mock API
vi.mock('@/api', () => ({
  statusApi: {
    getScanStatus: vi.fn(() => Promise.resolve({
      state: 'idle',
      progress: 0,
      current_movie: null,
      total_movies: 0,
      scanned_count: 0,
      message: null,
      start_time: null,
      elapsed_time: 0,
    })),
    getConnectionStatus: vi.fn(() => Promise.resolve({
      plex: { connected: true, message: null, last_check: null },
      qbittorrent: { connected: true, message: null, last_check: null },
      radarr: { connected: true, message: null, last_check: null },
      telegram: { connected: false, message: null, last_check: null },
      flaresolverr: { connected: true, message: null, last_check: null },
      ipt_scraper: { connected: true, message: null, last_check: null },
    })),
    checkConnections: vi.fn(() => Promise.resolve({ message: 'Connections checked' })),
  },
  scanApi: {
    triggerScan: vi.fn(() => Promise.resolve({ message: 'Scan started' })),
    triggerVerify: vi.fn(() => Promise.resolve({ message: 'Verify started' })),
    startMonitor: vi.fn(() => Promise.resolve({ message: 'Monitor started' })),
    stopMonitor: vi.fn(() => Promise.resolve({ message: 'Monitor stopped' })),
    cancelScan: vi.fn(() => Promise.resolve({ message: 'Scan cancelled' })),
  },
}))

describe('App Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with default state', () => {
    const store = useAppStore()

    expect(store.scanStatus).toBeNull()
    expect(store.connectionStatus).toBeNull()
    expect(store.flashMessages).toEqual([])
    expect(store.isPolling).toBe(false)
  })

  it('can add flash messages', () => {
    const store = useAppStore()

    store.addFlashMessage('success', 'Test message')

    expect(store.flashMessages.length).toBe(1)
    expect(store.flashMessages[0].type).toBe('success')
    expect(store.flashMessages[0].message).toBe('Test message')
  })

  it('can remove flash messages', () => {
    const store = useAppStore()

    store.addFlashMessage('success', 'Test message')
    const messageId = store.flashMessages[0].id

    store.removeFlashMessage(messageId)

    expect(store.flashMessages.length).toBe(0)
  })

  it('fetches scan status', async () => {
    const store = useAppStore()

    await store.fetchScanStatus()

    expect(store.scanStatus).not.toBeNull()
    expect(store.scanStatus?.state).toBe('idle')
  })

  it('fetches connection status', async () => {
    const store = useAppStore()

    await store.fetchConnectionStatus()

    expect(store.connectionStatus).not.toBeNull()
    expect(store.connectionStatus?.plex.connected).toBe(true)
  })

  it('computes isScanning correctly', async () => {
    const store = useAppStore()

    await store.fetchScanStatus()
    expect(store.isScanning).toBe(false)

    // Simulate scanning state
    store.scanStatus = {
      state: 'scanning',
      progress: 50,
      current_movie: 'Test Movie',
      total_movies: 100,
      scanned_count: 50,
      message: null,
      start_time: new Date().toISOString(),
      elapsed_time: 60,
    }

    expect(store.isScanning).toBe(true)
  })

  it('computes canTriggerScan correctly', async () => {
    const store = useAppStore()

    await store.fetchScanStatus()
    expect(store.canTriggerScan).toBe(true)

    store.scanStatus = {
      state: 'scanning',
      progress: 50,
      current_movie: 'Test Movie',
      total_movies: 100,
      scanned_count: 50,
      message: null,
      start_time: new Date().toISOString(),
      elapsed_time: 60,
    }

    expect(store.canTriggerScan).toBe(false)
  })
})
