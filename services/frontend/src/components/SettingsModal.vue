<template>
  <teleport to="body">
    <transition name="overlay">
      <div
        v-if="isOpen"
        class="overlay"
        @click="close"
      >
        <transition name="modal" appear>
          <div v-if="isOpen" class="modal-shell" @click.stop>
            <!-- Header -->
            <header class="modal-header">
              <div>
                <div class="eyebrow">Configuration</div>
                <h2 class="display text-xl mt-1">Settings</h2>
              </div>
              <button @click="close" class="icon-btn" aria-label="Close">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" class="w-5 h-5">
                  <path stroke-linecap="round" d="M6 6l12 12M18 6l-12 12" />
                </svg>
              </button>
            </header>

            <!-- Tabs -->
            <div class="modal-tabs">
              <button
                v-for="tab in tabs"
                :key="tab.id"
                @click="activeTab = tab.id"
                class="mtab"
                :class="{ 'mtab-active': activeTab === tab.id }"
              >
                {{ tab.label }}
              </button>
            </div>

            <!-- Content -->
            <div v-if="settingsStore.isLoading" class="modal-body text-center py-14">
              <div class="spinner mx-auto"></div>
            </div>

            <div v-else-if="settingsStore.settings" class="modal-body">
              <!-- Plex Tab -->
              <div v-if="activeTab === 'plex'" class="form-stack">
                <div>
                  <label class="label">Plex URL</label>
                  <input v-model="settingsStore.settings.plex_url" type="text" class="input" @input="markChanged" />
                </div>
                <div>
                  <label class="label">Plex Token</label>
                  <input v-model="settingsStore.settings.plex_token" type="password" class="input" @input="markChanged" />
                </div>
                <div>
                  <label class="label">Library Name</label>
                  <input v-model="settingsStore.settings.plex_library_name" type="text" class="input" @input="markChanged" />
                </div>
              </div>

              <!-- Collections Tab -->
              <div v-if="activeTab === 'collections'" class="form-stack">
                <div>
                  <label class="label">DV Profile 7 collection</label>
                  <input v-model="settingsStore.settings.collection_dv_p7" type="text" class="input" @input="markChanged" />
                </div>
                <div>
                  <label class="label">DV FEL collection</label>
                  <input v-model="settingsStore.settings.collection_dv_fel" type="text" class="input" @input="markChanged" />
                </div>
                <div>
                  <label class="label">Atmos collection</label>
                  <input v-model="settingsStore.settings.collection_atmos" type="text" class="input" @input="markChanged" />
                </div>
              </div>

              <!-- Telegram Tab -->
              <div v-if="activeTab === 'telegram'" class="form-stack">
                <label class="toggle">
                  <input v-model="settingsStore.settings.telegram_enabled" type="checkbox" @change="markChanged" />
                  <span class="toggle-box"></span>
                  <span class="toggle-label">Enable Telegram notifications</span>
                </label>
                <div>
                  <label class="label">Bot token</label>
                  <input v-model="settingsStore.settings.telegram_bot_token" type="password" class="input" @input="markChanged" />
                </div>
                <div>
                  <label class="label">Chat ID</label>
                  <input v-model="settingsStore.settings.telegram_chat_id" type="text" class="input" @input="markChanged" />
                </div>
              </div>

              <!-- Notification Rules Tab -->
              <div v-if="activeTab === 'notifications'" class="space-y-7">
                <fieldset class="rule-set">
                  <legend class="eyebrow">FEL notifications</legend>
                  <label class="toggle">
                    <input v-model="settingsStore.settings.notify_fel" type="checkbox" @change="markChanged" />
                    <span class="toggle-box"></span>
                    <span class="toggle-label">Notify on any FEL</span>
                  </label>
                  <label class="toggle">
                    <input v-model="settingsStore.settings.notify_fel_from_p5" type="checkbox" @change="markChanged" />
                    <span class="toggle-box"></span>
                    <span class="toggle-label">Notify on FEL upgrades from P5</span>
                  </label>
                  <label class="toggle">
                    <input v-model="settingsStore.settings.notify_fel_from_hdr" type="checkbox" @change="markChanged" />
                    <span class="toggle-box"></span>
                    <span class="toggle-label">Notify on FEL upgrades from HDR</span>
                  </label>
                  <label class="toggle">
                    <input v-model="settingsStore.settings.notify_fel_duplicates" type="checkbox" @change="markChanged" />
                    <span class="toggle-box"></span>
                    <span class="toggle-label">Notify on FEL duplicates</span>
                  </label>
                </fieldset>

                <fieldset class="rule-set">
                  <legend class="eyebrow">Dolby Vision</legend>
                  <label class="toggle">
                    <input v-model="settingsStore.settings.notify_dv_any" type="checkbox" @change="markChanged" />
                    <span class="toggle-box"></span>
                    <span class="toggle-label">Notify on any DV</span>
                  </label>
                  <label class="toggle">
                    <input v-model="settingsStore.settings.notify_dv_upgrades" type="checkbox" @change="markChanged" />
                    <span class="toggle-box"></span>
                    <span class="toggle-label">Notify on DV profile upgrades</span>
                  </label>
                </fieldset>

                <fieldset class="rule-set">
                  <legend class="eyebrow">Atmos</legend>
                  <label class="toggle">
                    <input v-model="settingsStore.settings.notify_atmos_any" type="checkbox" @change="markChanged" />
                    <span class="toggle-box"></span>
                    <span class="toggle-label">Notify on any Atmos</span>
                  </label>
                  <label class="toggle">
                    <input v-model="settingsStore.settings.notify_atmos_to_dv" type="checkbox" @change="markChanged" />
                    <span class="toggle-box"></span>
                    <span class="toggle-label">Notify on Atmos → DV upgrades</span>
                  </label>
                </fieldset>

                <fieldset class="rule-set">
                  <legend class="eyebrow">Resolution</legend>
                  <label class="toggle">
                    <input v-model="settingsStore.settings.notify_4k_any" type="checkbox" @change="markChanged" />
                    <span class="toggle-box"></span>
                    <span class="toggle-label">Notify on any 4K</span>
                  </label>
                  <label class="toggle">
                    <input v-model="settingsStore.settings.notify_resolution_upgrade" type="checkbox" @change="markChanged" />
                    <span class="toggle-box"></span>
                    <span class="toggle-label">Notify on resolution upgrades</span>
                  </label>
                </fieldset>
              </div>

              <!-- Scan Settings Tab -->
              <div v-if="activeTab === 'scan'" class="form-stack">
                <label class="toggle">
                  <input v-model="settingsStore.settings.scan_schedule_enabled" type="checkbox" @change="markChanged" />
                  <span class="toggle-box"></span>
                  <span class="toggle-label">Enable scheduled scans</span>
                </label>
                <div>
                  <label class="label">Auto-start mode</label>
                  <select v-model="settingsStore.settings.auto_start_mode" class="select" @change="markChanged">
                    <option value="disabled">Disabled</option>
                    <option value="scan">Scan on startup</option>
                    <option value="monitor">Monitor on startup</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Footer -->
            <footer class="modal-footer">
              <button @click="close" class="btn btn-ghost">Cancel</button>
              <button
                @click="saveSettings"
                class="btn btn-primary"
                :disabled="!settingsStore.hasUnsavedChanges"
              >
                Save changes
              </button>
            </footer>
          </div>
        </transition>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'

defineProps<{ isOpen: boolean }>()
const emit = defineEmits<{ close: [] }>()
const settingsStore = useSettingsStore()

const activeTab = ref('plex')
const tabs = [
  { id: 'plex',          label: 'Plex' },
  { id: 'collections',   label: 'Collections' },
  { id: 'telegram',      label: 'Telegram' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'scan',          label: 'Scan' },
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
    if (confirm('You have unsaved changes. Close anyway?')) emit('close')
  } else {
    emit('close')
  }
}
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 80;
  background:
    radial-gradient(ellipse 60% 50% at 50% 30%, rgba(124, 58, 237, 0.22), transparent 70%),
    rgba(4, 4, 9, 0.72);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.modal-shell {
  width: 100%;
  max-width: 56rem;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(rgba(26, 26, 36, 0.94), rgba(26, 26, 36, 0.94)),
    radial-gradient(ellipse 80% 40% at 50% 0%, rgba(212, 175, 55, 0.18), transparent 70%);
  border: 1px solid rgba(212, 175, 55, 0.22);
  border-radius: 18px;
  box-shadow: 0 32px 80px rgba(0, 0, 0, 0.7),
    0 0 0 1px rgba(212, 175, 55, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.3rem 1.75rem 1.1rem;
  border-bottom: 1px solid rgba(107, 107, 127, 0.15);
  background: rgba(10, 10, 15, 0.5);
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  color: var(--cinema-gray);
  border-radius: 8px;
  transition: all 220ms var(--ease-standard);
}
.icon-btn:hover {
  color: var(--cinema-gold);
  background: rgba(212, 175, 55, 0.08);
}

.modal-tabs {
  display: flex;
  gap: 0.25rem;
  padding: 0 1.75rem;
  border-bottom: 1px solid rgba(107, 107, 127, 0.15);
  background: rgba(10, 10, 15, 0.35);
  overflow-x: auto;
}

.mtab {
  position: relative;
  padding: 0.95rem 0.9rem;
  font-family: 'Geist', ui-sans-serif, sans-serif;
  font-size: 0.74rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--cinema-gray);
  white-space: nowrap;
  transition: color 220ms var(--ease-standard);
}

.mtab::after {
  content: '';
  position: absolute;
  left: 0.9rem;
  right: 0.9rem;
  bottom: -1px;
  height: 2px;
  background: var(--cinema-gold);
  border-radius: 2px;
  opacity: 0;
  transition: opacity 220ms var(--ease-standard);
}

.mtab:hover { color: var(--cinema-white); }
.mtab-active { color: var(--cinema-gold); }
.mtab-active::after { opacity: 1; }

.modal-body {
  padding: 1.75rem;
  overflow-y: auto;
  flex: 1;
}

.form-stack { display: flex; flex-direction: column; gap: 1.1rem; }

.rule-set {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 1.1rem 1.25rem;
  border: 1px solid rgba(107, 107, 127, 0.18);
  border-radius: 12px;
  background: rgba(10, 10, 15, 0.4);
}
.rule-set legend { padding: 0 0.4rem; margin-bottom: 0.3rem; }

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.7rem;
  cursor: pointer;
  user-select: none;
}
.toggle input { position: absolute; opacity: 0; pointer-events: none; }

.toggle-box {
  position: relative;
  width: 34px;
  height: 20px;
  border-radius: 999px;
  background: rgba(45, 45, 61, 0.7);
  border: 1px solid rgba(107, 107, 127, 0.3);
  transition: all 260ms var(--ease-standard);
  flex-shrink: 0;
}
.toggle-box::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: rgba(236, 236, 240, 0.75);
  transition: all 260ms var(--ease-standard);
}
.toggle input:checked + .toggle-box {
  background: linear-gradient(135deg, var(--cinema-gold), var(--cinema-gold-dark));
  border-color: rgba(212, 175, 55, 0.6);
  box-shadow: 0 0 14px rgba(212, 175, 55, 0.25);
}
.toggle input:checked + .toggle-box::after {
  left: 16px;
  background: #1a1506;
}

.toggle-label {
  font-size: 0.85rem;
  color: var(--cinema-white);
  letter-spacing: 0.01em;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  padding: 1.1rem 1.75rem;
  border-top: 1px solid rgba(107, 107, 127, 0.15);
  background: rgba(10, 10, 15, 0.5);
}

.spinner {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 2px solid rgba(212, 175, 55, 0.18);
  border-top-color: var(--cinema-gold);
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.overlay-enter-active, .overlay-leave-active { transition: opacity 220ms var(--ease-standard); }
.overlay-enter-from, .overlay-leave-to { opacity: 0; }

.modal-enter-active { transition: all 340ms var(--ease-spring); }
.modal-leave-active { transition: all 200ms var(--ease-standard); }
.modal-enter-from, .modal-leave-to { opacity: 0; transform: translateY(14px) scale(0.97); }
</style>
