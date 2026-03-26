import apiClient from './client'

export const scanApi = {
  // Trigger a full library scan
  triggerScan(force: boolean = false): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/scan/trigger', { force })
  },

  // Trigger verify mode
  triggerVerify(): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/scan/verify')
  },

  // Start monitor mode
  startMonitor(): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/scan/monitor/start')
  },

  // Stop monitor mode
  stopMonitor(): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/scan/monitor/stop')
  },

  // Get monitor status
  getMonitorStatus(): Promise<{ enabled: boolean; last_run: string | null }> {
    return apiClient.get<{ enabled: boolean; last_run: string | null }>('/v1/scan/monitor/status')
  },

  // Cancel current scan
  cancelScan(): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/scan/cancel')
  },
}
