import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { settingsApi } from '@/api'
import type { Settings } from '@/api/types'
import { useAppStore } from './app'

export const useSettingsStore = defineStore('settings', () => {
  // State
  const settings = ref<Settings | null>(null)
  const isLoading = ref(false)
  const hasUnsavedChanges = ref(false)

  // Getters
  const hasSettings = computed(() => settings.value !== null)

  const plexSettings = computed(() => {
    if (!settings.value) return null
    return {
      plex_url: settings.value.plex_url,
      plex_token: settings.value.plex_token,
      plex_library_name: settings.value.plex_library_name,
    }
  })

  const collectionSettings = computed(() => {
    if (!settings.value) return null
    return {
      collection_dv_p7: settings.value.collection_dv_p7,
      collection_dv_fel: settings.value.collection_dv_fel,
      collection_atmos: settings.value.collection_atmos,
    }
  })

  const qbittorrentSettings = computed(() => {
    if (!settings.value) return null
    return {
      qbittorrent_url: settings.value.qbittorrent_url,
      qbittorrent_username: settings.value.qbittorrent_username,
      qbittorrent_password: settings.value.qbittorrent_password,
    }
  })

  const radarrSettings = computed(() => {
    if (!settings.value) return null
    return {
      radarr_url: settings.value.radarr_url,
      radarr_api_key: settings.value.radarr_api_key,
    }
  })

  const telegramSettings = computed(() => {
    if (!settings.value) return null
    return {
      telegram_enabled: settings.value.telegram_enabled,
      telegram_bot_token: settings.value.telegram_bot_token,
      telegram_chat_id: settings.value.telegram_chat_id,
    }
  })

  const iptSettings = computed(() => {
    if (!settings.value) return null
    return {
      ipt_enabled: settings.value.ipt_enabled,
      ipt_url: settings.value.ipt_url,
      ipt_uid: settings.value.ipt_uid,
      ipt_pass: settings.value.ipt_pass,
    }
  })

  const scanSettings = computed(() => {
    if (!settings.value) return null
    return {
      scan_schedule_enabled: settings.value.scan_schedule_enabled,
      scan_schedule_hours: settings.value.scan_schedule_hours,
      auto_start_mode: settings.value.auto_start_mode,
    }
  })

  const monitorSettings = computed(() => {
    if (!settings.value) return null
    return {
      monitor_enabled: settings.value.monitor_enabled,
      monitor_interval_minutes: settings.value.monitor_interval_minutes,
    }
  })

  const notificationSettings = computed(() => {
    if (!settings.value) return null
    return {
      notify_fel: settings.value.notify_fel,
      notify_fel_from_p5: settings.value.notify_fel_from_p5,
      notify_fel_from_hdr: settings.value.notify_fel_from_hdr,
      notify_fel_duplicates: settings.value.notify_fel_duplicates,
      notify_p5: settings.value.notify_p5,
      notify_p5_from_hdr: settings.value.notify_p5_from_hdr,
      notify_p5_duplicates: settings.value.notify_p5_duplicates,
      notify_dv_any: settings.value.notify_dv_any,
      notify_dv_upgrades: settings.value.notify_dv_upgrades,
      notify_hdr_from_sdr: settings.value.notify_hdr_from_sdr,
      notify_atmos_any: settings.value.notify_atmos_any,
      notify_atmos_to_dv: settings.value.notify_atmos_to_dv,
      notify_resolution_upgrade: settings.value.notify_resolution_upgrade,
      notify_4k_any: settings.value.notify_4k_any,
      notify_1080p_from_lower: settings.value.notify_1080p_from_lower,
    }
  })

  const downloadSettings = computed(() => {
    if (!settings.value) return null
    return {
      download_approval_expires_hours: settings.value.download_approval_expires_hours,
      download_category_fel: settings.value.download_category_fel,
      download_category_dv: settings.value.download_category_dv,
      download_category_hdr: settings.value.download_category_hdr,
    }
  })

  // Actions
  async function fetchSettings() {
    isLoading.value = true
    try {
      settings.value = await settingsApi.getSettings()
      hasUnsavedChanges.value = false
    } catch (error) {
      console.error('Failed to fetch settings:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function updateSettings(partialSettings: Partial<Settings>) {
    const appStore = useAppStore()
    isLoading.value = true
    try {
      const response = await settingsApi.updateSettings(partialSettings)
      appStore.addFlashMessage('success', response.message || 'Settings saved successfully')
      await fetchSettings()
      hasUnsavedChanges.value = false
    } catch (error: any) {
      appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to save settings')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function updateSetting(key: string, value: any) {
    const appStore = useAppStore()
    try {
      const response = await settingsApi.updateSetting(key, value)
      appStore.addFlashMessage('success', response.message || 'Setting updated')
      await fetchSettings()
    } catch (error: any) {
      appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to update setting')
      throw error
    }
  }

  async function resetSettings() {
    const appStore = useAppStore()
    isLoading.value = true
    try {
      const response = await settingsApi.resetSettings()
      appStore.addFlashMessage('success', response.message || 'Settings reset to defaults')
      await fetchSettings()
      hasUnsavedChanges.value = false
    } catch (error: any) {
      appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to reset settings')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  function markAsChanged() {
    hasUnsavedChanges.value = true
  }

  function reset() {
    settings.value = null
    hasUnsavedChanges.value = false
  }

  return {
    // State
    settings,
    isLoading,
    hasUnsavedChanges,

    // Getters
    hasSettings,
    plexSettings,
    collectionSettings,
    qbittorrentSettings,
    radarrSettings,
    telegramSettings,
    iptSettings,
    scanSettings,
    monitorSettings,
    notificationSettings,
    downloadSettings,

    // Actions
    fetchSettings,
    updateSettings,
    updateSetting,
    resetSettings,
    markAsChanged,
    reset,
  }
})
