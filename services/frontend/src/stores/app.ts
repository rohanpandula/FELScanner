import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { statusApi, scanApi } from '@/api'
import type { ScanStatus, ConnectionStatus } from '@/api/types'

interface FlashMessage {
  id: number
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
}

export const useAppStore = defineStore('app', () => {
  // State
  const scanStatus = ref<ScanStatus | null>(null)
  const connectionStatus = ref<ConnectionStatus | null>(null)
  const flashMessages = ref<FlashMessage[]>([])
  const isPolling = ref(false)
  const pollingInterval = ref<number | null>(null)
  const flashMessageCounter = ref(0)

  // Dark mode state - initialize from localStorage
  const isDarkMode = ref(localStorage.getItem('darkMode') === 'true')

  // Getters
  const isScanning = computed(() => {
    return scanStatus.value?.state === 'scanning' || scanStatus.value?.state === 'verifying'
  })

  const canTriggerScan = computed(() => {
    return scanStatus.value?.state === 'idle'
  })

  const allConnectionsHealthy = computed(() => {
    if (!connectionStatus.value) return false
    return Object.values(connectionStatus.value).every((service) => service.connected)
  })

  // Actions
  async function fetchScanStatus() {
    try {
      scanStatus.value = await statusApi.getScanStatus()
    } catch (error) {
      console.error('Failed to fetch scan status:', error)
    }
  }

  async function fetchConnectionStatus() {
    try {
      connectionStatus.value = await statusApi.getConnectionStatus()
    } catch (error) {
      console.error('Failed to fetch connection status:', error)
    }
  }

  async function triggerScan(force: boolean = false) {
    try {
      const response = await scanApi.triggerScan(force)
      addFlashMessage('success', response.message || 'Scan started successfully')
      await fetchScanStatus()
    } catch (error: any) {
      addFlashMessage('error', error.response?.data?.detail || 'Failed to start scan')
    }
  }

  async function triggerVerify() {
    try {
      const response = await scanApi.triggerVerify()
      addFlashMessage('success', response.message || 'Verify mode started')
      await fetchScanStatus()
    } catch (error: any) {
      addFlashMessage('error', error.response?.data?.detail || 'Failed to start verify')
    }
  }

  async function startMonitor() {
    try {
      const response = await scanApi.startMonitor()
      addFlashMessage('success', response.message || 'Monitor mode started')
      await fetchScanStatus()
    } catch (error: any) {
      addFlashMessage('error', error.response?.data?.detail || 'Failed to start monitor')
    }
  }

  async function stopMonitor() {
    try {
      const response = await scanApi.stopMonitor()
      addFlashMessage('success', response.message || 'Monitor mode stopped')
      await fetchScanStatus()
    } catch (error: any) {
      addFlashMessage('error', error.response?.data?.detail || 'Failed to stop monitor')
    }
  }

  async function cancelScan() {
    try {
      const response = await scanApi.cancelScan()
      addFlashMessage('success', response.message || 'Scan cancelled')
      await fetchScanStatus()
    } catch (error: any) {
      addFlashMessage('error', error.response?.data?.detail || 'Failed to cancel scan')
    }
  }

  async function checkConnections() {
    try {
      const response = await statusApi.checkConnections()
      addFlashMessage('success', response.message || 'Connection checks triggered')
      await fetchConnectionStatus()
    } catch (error: any) {
      addFlashMessage('error', error.response?.data?.detail || 'Failed to check connections')
    }
  }

  function addFlashMessage(type: FlashMessage['type'], message: string) {
    const id = ++flashMessageCounter.value
    flashMessages.value.push({ id, type, message })

    // Auto-remove after 5 seconds
    setTimeout(() => {
      removeFlashMessage(id)
    }, 5000)
  }

  function removeFlashMessage(id: number) {
    const index = flashMessages.value.findIndex((msg) => msg.id === id)
    if (index !== -1) {
      flashMessages.value.splice(index, 1)
    }
  }

  function startPolling() {
    if (isPolling.value) return

    isPolling.value = true

    // Immediate fetch
    fetchScanStatus()
    fetchConnectionStatus()

    // Poll every 15 seconds
    pollingInterval.value = window.setInterval(() => {
      fetchScanStatus()
      fetchConnectionStatus()
    }, 15000)
  }

  function stopPolling() {
    if (!isPolling.value) return

    isPolling.value = false

    if (pollingInterval.value !== null) {
      clearInterval(pollingInterval.value)
      pollingInterval.value = null
    }
  }

  function toggleDarkMode() {
    isDarkMode.value = !isDarkMode.value
    localStorage.setItem('darkMode', isDarkMode.value.toString())

    // Update the document root class
    if (isDarkMode.value) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  // Initialize dark mode class on store creation
  if (isDarkMode.value) {
    document.documentElement.classList.add('dark')
  }

  return {
    // State
    scanStatus,
    connectionStatus,
    flashMessages,
    isPolling,
    isDarkMode,

    // Getters
    isScanning,
    canTriggerScan,
    allConnectionsHealthy,

    // Actions
    fetchScanStatus,
    fetchConnectionStatus,
    triggerScan,
    triggerVerify,
    startMonitor,
    stopMonitor,
    cancelScan,
    checkConnections,
    addFlashMessage,
    removeFlashMessage,
    startPolling,
    stopPolling,
    toggleDarkMode,
  }
})
