import apiClient from './client'
import type { Settings } from './types'

export const settingsApi = {
  // Get all settings
  getSettings(): Promise<Settings> {
    return apiClient.get<Settings>('/v1/settings')
  },

  // Update settings
  updateSettings(settings: Partial<Settings>): Promise<{ message: string }> {
    return apiClient.put<{ message: string }>('/v1/settings', settings)
  },

  // Get specific setting
  getSetting(key: string): Promise<{ value: any }> {
    return apiClient.get<{ value: any }>(`/v1/settings/${key}`)
  },

  // Update specific setting
  updateSetting(key: string, value: any): Promise<{ message: string }> {
    return apiClient.put<{ message: string }>(`/v1/settings/${key}`, { value })
  },

  // Reset settings to defaults
  resetSettings(): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/settings/reset')
  },
}
