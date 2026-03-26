import apiClient from './client'
import type { ScanStatus, ConnectionStatus } from './types'

export const statusApi = {
  // Get current scan status
  getScanStatus(): Promise<ScanStatus> {
    return apiClient.get<ScanStatus>('/v1/scan/status')
  },

  // Get connection status for all services
  getConnectionStatus(): Promise<ConnectionStatus> {
    return apiClient.get<ConnectionStatus>('/v1/connections/status')
  },

  // Trigger connection checks
  checkConnections(): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/connections/check')
  },
}
