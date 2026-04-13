<template>
  <div class="release-groups space-y-8">
    <!-- Header -->
    <div class="flex items-center justify-between" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.1s backwards;">
      <div class="flex items-center space-x-3">
        <div class="section-icon">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
        </div>
        <div>
          <h1 class="text-2xl font-bold">Release Groups</h1>
          <p class="text-xs mt-1" style="color: #9ca3af;">Track group reputation and set preferences for IPT results</p>
        </div>
      </div>
    </div>

    <!-- Summary Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4" v-if="summary">
      <div class="stat-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.15s backwards;">
        <div class="stat-label">Known Groups</div>
        <div class="stat-value" style="font-size: 2rem;">{{ summary.total_groups }}</div>
        <div class="stat-subtitle">Discovered from IPT</div>
      </div>
      <div class="stat-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s backwards;">
        <div class="stat-label">Preferred</div>
        <div class="stat-value" style="font-size: 2rem; background: linear-gradient(135deg, #10b981, #34d399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
          {{ summary.preferred_count }}
        </div>
        <div class="stat-subtitle">Prioritized groups</div>
      </div>
      <div class="stat-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.25s backwards;">
        <div class="stat-label">Blocked</div>
        <div class="stat-value" style="font-size: 2rem; background: linear-gradient(135deg, #d45473, #8c2f4e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
          {{ summary.blocked_count }}
        </div>
        <div class="stat-subtitle">Excluded groups</div>
      </div>
    </div>

    <!-- Groups Table -->
    <div class="card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.3s backwards;">
      <!-- Filter -->
      <div class="flex items-center space-x-4 mb-6">
        <label class="flex items-center space-x-2 cursor-pointer">
          <input
            type="checkbox"
            v-model="showPreferredOnly"
            class="form-checkbox rounded"
            style="accent-color: #4d7cff;"
          />
          <span class="text-sm" style="color: #9ca3af;">Show preferred only</span>
        </label>
        <select v-model="sortBy" class="input" style="width: auto; padding: 0.5rem 1rem; font-size: 0.8rem;">
          <option value="total_releases_seen">Most Seen</option>
          <option value="avg_quality_score">Quality Score</option>
          <option value="avg_file_size_gb">File Size</option>
          <option value="group_name">Name</option>
        </select>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b" style="border-color: rgba(107, 107, 127, 0.2);">
              <th class="table-header text-left">Group</th>
              <th class="table-header text-center">Status</th>
              <th class="table-header text-right">Releases Seen</th>
              <th class="table-header text-right">Avg Quality</th>
              <th class="table-header text-right">Avg Size</th>
              <th class="table-header text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="group in groups" :key="group.id" class="table-row" :class="{ 'row-preferred': group.is_preferred, 'row-blocked': group.is_blocked }">
              <td class="table-cell">
                <span class="font-semibold" style="color: #f5f5f7;">{{ group.group_name }}</span>
              </td>
              <td class="table-cell text-center">
                <span v-if="group.is_preferred" class="badge badge-4k" style="font-size: 0.65rem;">PREFERRED</span>
                <span v-else-if="group.is_blocked" class="badge" style="background: rgba(212, 84, 115, 0.2); border-color: rgba(212, 84, 115, 0.4); color: #d45473; font-size: 0.65rem;">BLOCKED</span>
                <span v-else class="text-xs" style="color: #9ca3af;">-</span>
              </td>
              <td class="table-cell text-right font-medium" style="color: #4d7cff;">{{ group.total_releases_seen }}</td>
              <td class="table-cell text-right">
                <span v-if="group.avg_quality_score" class="font-medium" style="color: #9bb4ff;">{{ Math.round(group.avg_quality_score) }}</span>
                <span v-else style="color: #9ca3af;">-</span>
              </td>
              <td class="table-cell text-right">
                <span v-if="group.avg_file_size_gb" style="color: #9ca3af;">{{ group.avg_file_size_gb.toFixed(1) }} GB</span>
                <span v-else style="color: #9ca3af;">-</span>
              </td>
              <td class="table-cell text-right">
                <div class="flex items-center justify-end space-x-1">
                  <button
                    @click="togglePreferred(group)"
                    class="action-btn"
                    :class="{ active: group.is_preferred }"
                    :title="group.is_preferred ? 'Remove from preferred' : 'Mark as preferred'"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                    </svg>
                  </button>
                  <button
                    @click="toggleBlocked(group)"
                    class="action-btn block-btn"
                    :class="{ active: group.is_blocked }"
                    :title="group.is_blocked ? 'Unblock' : 'Block'"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="groups.length === 0 && !store.loading" class="text-center py-12">
        <p style="color: #9ca3af;">No release groups discovered yet. Run an IPT scan to populate.</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading && groups.length === 0" class="text-center py-20">
      <div class="inline-block w-10 h-10 border-2 border-[#4d7cff] border-t-transparent rounded-full animate-spin"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useReleaseGroupsStore } from '@/stores/releaseGroups'
import type { ReleaseGroup } from '@/api/types'

const store = useReleaseGroupsStore()
const groups = computed(() => store.groups)
const summary = computed(() => store.summary)

const showPreferredOnly = ref(false)
const sortBy = ref('total_releases_seen')

watch([showPreferredOnly, sortBy], () => {
  store.fetchGroups({
    sort_by: sortBy.value,
    sort_order: sortBy.value === 'group_name' ? 'asc' : 'desc',
    preferred_only: showPreferredOnly.value,
  })
})

async function togglePreferred(group: ReleaseGroup) {
  await store.updatePreference(group.group_name, {
    is_preferred: !group.is_preferred,
  })
}

async function toggleBlocked(group: ReleaseGroup) {
  await store.updatePreference(group.group_name, {
    is_blocked: !group.is_blocked,
  })
}

onMounted(() => {
  store.fetchGroups()
  store.fetchSummary()
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

.table-header {
  padding: 0.75rem 1rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #9ca3af;
  font-weight: 600;
}
.table-row { border-bottom: 1px solid rgba(107, 107, 127, 0.1); transition: background 0.2s; }
.table-row:hover { background: rgba(77, 124, 255, 0.05); }
.table-cell { padding: 0.75rem 1rem; font-size: 0.875rem; }
.row-preferred { background: rgba(16, 185, 129, 0.05); }
.row-blocked { background: rgba(212, 84, 115, 0.05); opacity: 0.7; }

.action-btn {
  padding: 0.375rem; border-radius: 6px;
  color: #9ca3af; transition: all 0.2s;
  background: transparent;
}
.action-btn:hover { color: #4d7cff; background: rgba(77, 124, 255, 0.1); }
.action-btn.active { color: #4d7cff; }
.action-btn.block-btn:hover { color: #d45473; background: rgba(212, 84, 115, 0.1); }
.action-btn.block-btn.active { color: #d45473; }
</style>
