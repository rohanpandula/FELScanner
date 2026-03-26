<template>
  <teleport to="body">
    <div
      v-if="isOpen"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      @click="close"
    >
      <div
        class="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
        @click.stop
      >
        <!-- Header -->
        <div class="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 class="text-2xl font-bold">Settings</h2>
          <button @click="close" class="text-gray-500 hover:text-gray-700 text-2xl">
            ×
          </button>
        </div>

        <!-- Tabs -->
        <div class="border-b border-gray-200 px-6">
          <div class="flex space-x-4">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              @click="activeTab = tab.id"
              class="py-3 px-4 font-medium transition-colors"
              :class="activeTab === tab.id ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-600 hover:text-gray-900'"
            >
              {{ tab.label }}
            </button>
          </div>
        </div>

        <!-- Content -->
        <div v-if="settingsStore.isLoading" class="p-6 text-center">
          <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>

        <div v-else-if="settingsStore.settings" class="p-6">
          <!-- Plex Tab -->
          <div v-if="activeTab === 'plex'" class="space-y-4">
            <div>
              <label class="label">Plex URL</label>
              <input
                v-model="settingsStore.settings.plex_url"
                type="text"
                class="input"
                @input="markChanged"
              />
            </div>
            <div>
              <label class="label">Plex Token</label>
              <input
                v-model="settingsStore.settings.plex_token"
                type="password"
                class="input"
                @input="markChanged"
              />
            </div>
            <div>
              <label class="label">Library Name</label>
              <input
                v-model="settingsStore.settings.plex_library_name"
                type="text"
                class="input"
                @input="markChanged"
              />
            </div>
          </div>

          <!-- Collections Tab -->
          <div v-if="activeTab === 'collections'" class="space-y-4">
            <div>
              <label class="label">DV Profile 7 Collection</label>
              <input
                v-model="settingsStore.settings.collection_dv_p7"
                type="text"
                class="input"
                @input="markChanged"
              />
            </div>
            <div>
              <label class="label">DV FEL Collection</label>
              <input
                v-model="settingsStore.settings.collection_dv_fel"
                type="text"
                class="input"
                @input="markChanged"
              />
            </div>
            <div>
              <label class="label">Atmos Collection</label>
              <input
                v-model="settingsStore.settings.collection_atmos"
                type="text"
                class="input"
                @input="markChanged"
              />
            </div>
          </div>

          <!-- Telegram Tab -->
          <div v-if="activeTab === 'telegram'" class="space-y-4">
            <div>
              <label class="flex items-center">
                <input
                  v-model="settingsStore.settings.telegram_enabled"
                  type="checkbox"
                  class="mr-2"
                  @change="markChanged"
                />
                <span class="font-medium">Enable Telegram Notifications</span>
              </label>
            </div>
            <div>
              <label class="label">Bot Token</label>
              <input
                v-model="settingsStore.settings.telegram_bot_token"
                type="password"
                class="input"
                @input="markChanged"
              />
            </div>
            <div>
              <label class="label">Chat ID</label>
              <input
                v-model="settingsStore.settings.telegram_chat_id"
                type="text"
                class="input"
                @input="markChanged"
              />
            </div>
          </div>

          <!-- Notification Rules Tab -->
          <div v-if="activeTab === 'notifications'" class="space-y-3">
            <h3 class="font-semibold mb-2">FEL Notifications</h3>
            <label class="flex items-center">
              <input v-model="settingsStore.settings.notify_fel" type="checkbox" class="mr-2" @change="markChanged" />
              <span>Notify on any FEL</span>
            </label>
            <label class="flex items-center">
              <input v-model="settingsStore.settings.notify_fel_from_p5" type="checkbox" class="mr-2" @change="markChanged" />
              <span>Notify on FEL upgrades from P5</span>
            </label>
            <label class="flex items-center">
              <input v-model="settingsStore.settings.notify_fel_from_hdr" type="checkbox" class="mr-2" @change="markChanged" />
              <span>Notify on FEL upgrades from HDR</span>
            </label>
            <label class="flex items-center">
              <input v-model="settingsStore.settings.notify_fel_duplicates" type="checkbox" class="mr-2" @change="markChanged" />
              <span>Notify on FEL duplicates</span>
            </label>

            <h3 class="font-semibold mb-2 mt-4">Dolby Vision Notifications</h3>
            <label class="flex items-center">
              <input v-model="settingsStore.settings.notify_dv_any" type="checkbox" class="mr-2" @change="markChanged" />
              <span>Notify on any DV</span>
            </label>
            <label class="flex items-center">
              <input v-model="settingsStore.settings.notify_dv_upgrades" type="checkbox" class="mr-2" @change="markChanged" />
              <span>Notify on DV profile upgrades</span>
            </label>

            <h3 class="font-semibold mb-2 mt-4">Atmos Notifications</h3>
            <label class="flex items-center">
              <input v-model="settingsStore.settings.notify_atmos_any" type="checkbox" class="mr-2" @change="markChanged" />
              <span>Notify on any Atmos</span>
            </label>
            <label class="flex items-center">
              <input v-model="settingsStore.settings.notify_atmos_to_dv" type="checkbox" class="mr-2" @change="markChanged" />
              <span>Notify on Atmos to DV upgrades</span>
            </label>

            <h3 class="font-semibold mb-2 mt-4">Resolution Notifications</h3>
            <label class="flex items-center">
              <input v-model="settingsStore.settings.notify_4k_any" type="checkbox" class="mr-2" @change="markChanged" />
              <span>Notify on any 4K</span>
            </label>
            <label class="flex items-center">
              <input v-model="settingsStore.settings.notify_resolution_upgrade" type="checkbox" class="mr-2" @change="markChanged" />
              <span>Notify on resolution upgrades</span>
            </label>
          </div>

          <!-- Scan Settings Tab -->
          <div v-if="activeTab === 'scan'" class="space-y-4">
            <div>
              <label class="flex items-center">
                <input
                  v-model="settingsStore.settings.scan_schedule_enabled"
                  type="checkbox"
                  class="mr-2"
                  @change="markChanged"
                />
                <span class="font-medium">Enable Scheduled Scans</span>
              </label>
            </div>
            <div>
              <label class="label">Auto Start Mode</label>
              <select v-model="settingsStore.settings.auto_start_mode" class="input" @change="markChanged">
                <option value="disabled">Disabled</option>
                <option value="scan">Scan on Startup</option>
                <option value="monitor">Monitor on Startup</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4 flex justify-end space-x-3">
          <button @click="close" class="btn btn-secondary">
            Cancel
          </button>
          <button
            @click="saveSettings"
            class="btn btn-primary"
            :disabled="!settingsStore.hasUnsavedChanges"
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'

defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const settingsStore = useSettingsStore()

const activeTab = ref('plex')
const tabs = [
  { id: 'plex', label: 'Plex' },
  { id: 'collections', label: 'Collections' },
  { id: 'telegram', label: 'Telegram' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'scan', label: 'Scan Settings' },
]

onMounted(async () => {
  await settingsStore.fetchSettings()
})

function markChanged() {
  settingsStore.markAsChanged()
}

async function saveSettings() {
  if (settingsStore.settings) {
    await settingsStore.updateSettings(settingsStore.settings)
    emit('close')
  }
}

function close() {
  if (settingsStore.hasUnsavedChanges) {
    if (confirm('You have unsaved changes. Are you sure you want to close?')) {
      emit('close')
    }
  } else {
    emit('close')
  }
}
</script>
