<template>
  <div class="insights space-y-8">
    <!-- Header -->
    <div class="flex items-center justify-between" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.1s backwards;">
      <div class="flex items-center space-x-3">
        <div class="section-icon">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <div>
          <h1 class="text-2xl font-bold">Insights</h1>
          <p class="text-xs mt-1" style="color: #9ca3af;">Duplicates, upgrade opportunities, and deep analysis</p>
        </div>
      </div>
    </div>

    <!-- Tab Navigation -->
    <div class="flex space-x-1 p-1 rounded-xl" style="background: rgba(31, 41, 55, 0.3); border: 1px solid rgba(107, 107, 127, 0.15);">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
      >
        {{ tab.label }}
        <span v-if="tab.count !== undefined" class="tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <!-- Upgrades Tab -->
    <div v-if="activeTab === 'upgrades'" style="animation: fadeInUp 0.4s ease backwards;">
      <div class="space-y-3">
        <div
          v-for="movie in upgradeOpportunities"
          :key="movie.id"
          class="card upgrade-card"
          style="padding: 1.25rem;"
        >
          <div class="flex items-center justify-between">
            <div class="flex-1">
              <div class="flex items-center space-x-3">
                <h3 class="text-base font-semibold" style="color: #f5f5f7;">{{ movie.title }}</h3>
                <span v-if="movie.year" class="text-xs" style="color: #9ca3af;">({{ movie.year }})</span>
              </div>
              <div class="flex items-center space-x-2 mt-2">
                <span class="text-xs px-2 py-0.5 rounded" style="background: rgba(107, 107, 127, 0.2); color: #9ca3af;">
                  {{ movie.current_quality }}
                </span>
                <span class="text-xs" style="color: #9ca3af;">Score: {{ movie.quality_score }}</span>
              </div>
            </div>
            <div class="flex flex-wrap gap-1.5 ml-4">
              <span
                v-for="upgrade in movie.possible_upgrades"
                :key="upgrade"
                class="upgrade-tag"
                :class="upgradeTagClass(upgrade)"
              >
                + {{ upgrade }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="upgradeOpportunities.length === 0 && !store.loading" class="text-center py-12">
          <p class="text-lg font-bold" style="color: #10b981;">Your library is fully optimized</p>
          <p class="text-sm mt-2" style="color: #9ca3af;">Every movie is at the highest available quality tier.</p>
        </div>
      </div>
    </div>

    <!-- Duplicates Tab -->
    <div v-if="activeTab === 'duplicates'" style="animation: fadeInUp 0.4s ease backwards;">
      <div class="space-y-4">
        <div
          v-for="(dup, index) in duplicates"
          :key="index"
          class="card"
          style="padding: 1.25rem;"
        >
          <div class="flex items-center justify-between mb-3">
            <div>
              <h3 class="text-base font-semibold" style="color: #f5f5f7;">{{ dup.title }}</h3>
              <span v-if="dup.year" class="text-xs" style="color: #9ca3af;">({{ dup.year }})</span>
            </div>
            <div class="flex items-center space-x-3">
              <span class="badge badge-hdr" style="font-size: 0.65rem;">{{ dup.version_count }} versions</span>
              <span v-if="dup.total_size_bytes" class="text-xs font-medium" style="color: #9ca3af;">
                {{ formatSize(dup.total_size_bytes) }} total
              </span>
            </div>
          </div>

          <!-- Version comparison table -->
          <div v-if="dup.versions.length > 0" class="overflow-x-auto">
            <table class="w-full">
              <thead>
                <tr class="border-b" style="border-color: rgba(107, 107, 127, 0.15);">
                  <th class="mini-header text-left">Quality</th>
                  <th class="mini-header text-center">Resolution</th>
                  <th class="mini-header text-center">DV</th>
                  <th class="mini-header text-center">FEL</th>
                  <th class="mini-header text-center">Atmos</th>
                  <th class="mini-header text-right">Size</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(ver, vi) in dup.versions" :key="vi" class="border-b" style="border-color: rgba(107, 107, 127, 0.08);">
                  <td class="mini-cell">
                    <span class="text-xs font-medium" style="color: #9bb4ff;">{{ ver.quality || '-' }}</span>
                  </td>
                  <td class="mini-cell text-center text-xs" style="color: #9ca3af;">{{ ver.resolution || '-' }}</td>
                  <td class="mini-cell text-center">
                    <span v-if="ver.dv_profile" class="text-xs font-bold" style="color: #4d7cff;">{{ ver.dv_profile }}</span>
                    <span v-else class="text-xs" style="color: #9ca3af;">-</span>
                  </td>
                  <td class="mini-cell text-center">
                    <span v-if="ver.dv_fel" class="text-xs font-bold" style="color: #4d7cff;">Yes</span>
                    <span v-else class="text-xs" style="color: #9ca3af;">-</span>
                  </td>
                  <td class="mini-cell text-center">
                    <span v-if="ver.has_atmos" class="text-xs font-bold" style="color: #3b82f6;">Yes</span>
                    <span v-else class="text-xs" style="color: #9ca3af;">-</span>
                  </td>
                  <td class="mini-cell text-right text-xs" style="color: #9ca3af;">
                    {{ ver.file_size_bytes ? formatSize(ver.file_size_bytes) : '-' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="duplicates.length === 0 && !store.loading" class="text-center py-12">
          <p class="text-lg font-bold" style="color: #10b981;">No duplicates found</p>
          <p class="text-sm mt-2" style="color: #9ca3af;">Your library has no duplicate movie entries.</p>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading" class="text-center py-20">
      <div class="inline-block w-10 h-10 border-2 border-[#4d7cff] border-t-transparent rounded-full animate-spin"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAnalyticsStore } from '@/stores/analytics'

const store = useAnalyticsStore()
const activeTab = ref('upgrades')

const upgradeOpportunities = computed(() => store.upgradeOpportunities)
const duplicates = computed(() => store.duplicates)

const tabs = computed(() => [
  { key: 'upgrades', label: 'Upgrade Opportunities', count: upgradeOpportunities.value.length },
  { key: 'duplicates', label: 'Duplicates', count: duplicates.value.length },
])

watch(activeTab, (tab) => {
  if (tab === 'upgrades' && upgradeOpportunities.value.length === 0) {
    store.fetchUpgradeOpportunities()
  }
  if (tab === 'duplicates' && duplicates.value.length === 0) {
    store.fetchDuplicates()
  }
})

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(i > 2 ? 1 : 0) + ' ' + units[i]
}

function upgradeTagClass(upgrade: string): string {
  if (upgrade.includes('FEL')) return 'tag-fel'
  if (upgrade.includes('Vision')) return 'tag-dv'
  if (upgrade.includes('Atmos')) return 'tag-atmos'
  if (upgrade.includes('4K')) return 'tag-4k'
  return ''
}

onMounted(() => {
  store.fetchUpgradeOpportunities()
})
</script>

<style scoped>
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

.section-icon {
  width: 48px; height: 48px; border-radius: 12px;
  background: linear-gradient(135deg, rgba(77, 124, 255, 0.2), rgba(77, 124, 255, 0.2));
  border: 1px solid rgba(77, 124, 255, 0.3);
  display: flex; align-items: center; justify-content: center;
  color: #4d7cff; flex-shrink: 0;
}

.tab-btn {
  padding: 0.625rem 1.25rem;
  font-size: 0.8rem; font-weight: 600;
  letter-spacing: 0.03em; text-transform: uppercase;
  color: #9ca3af; border-radius: 0.625rem;
  transition: all 0.3s; display: flex;
  align-items: center; gap: 0.5rem;
}
.tab-btn:hover { color: #f5f5f7; background: rgba(31, 41, 55, 0.5); }
.tab-btn.active {
  color: #4d7cff;
  background: rgba(77, 124, 255, 0.15);
  border: 1px solid rgba(77, 124, 255, 0.3);
}
.tab-count {
  font-size: 0.65rem; padding: 0.125rem 0.375rem;
  border-radius: 999px; background: rgba(107, 107, 127, 0.2);
}
.tab-btn.active .tab-count {
  background: rgba(77, 124, 255, 0.3);
  color: #4d7cff;
}

.upgrade-card { cursor: default; }
.upgrade-card:hover { border-color: rgba(77, 124, 255, 0.3); }

.upgrade-tag {
  font-size: 0.65rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.05em;
  padding: 0.25rem 0.5rem; border-radius: 6px;
}
.tag-fel { background: rgba(77, 124, 255, 0.15); color: #4d7cff; border: 1px solid rgba(77, 124, 255, 0.3); }
.tag-dv { background: rgba(77, 124, 255, 0.15); color: #9bb4ff; border: 1px solid rgba(77, 124, 255, 0.3); }
.tag-atmos { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
.tag-4k { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }

.mini-header {
  padding: 0.5rem 0.5rem; font-size: 0.6rem;
  text-transform: uppercase; letter-spacing: 0.08em;
  color: #9ca3af; font-weight: 600;
}
.mini-cell { padding: 0.5rem 0.5rem; }
</style>
