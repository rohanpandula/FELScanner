<template>
  <div class="storage-analytics space-y-8">
    <!-- Summary Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6" v-if="storage">
      <div class="stat-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.1s backwards;">
        <div class="stat-label">Total Storage</div>
        <div class="stat-value" style="font-size: 2rem;">{{ formatSize(storage.total_bytes) }}</div>
        <div class="stat-subtitle">{{ storage.total_movies }} movies</div>
      </div>
      <div class="stat-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.15s backwards;">
        <div class="stat-label">Average File Size</div>
        <div class="stat-value" style="font-size: 2rem; background: linear-gradient(135deg, #7c3aed, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
          {{ formatSize(storage.avg_file_size_bytes) }}
        </div>
        <div class="stat-subtitle">Per movie</div>
      </div>
      <div class="stat-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s backwards;">
        <div class="stat-label">Largest Movie</div>
        <div class="stat-value" style="font-size: 2rem; background: linear-gradient(135deg, #f59e0b, #fbbf24); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
          {{ storage.largest_movies.length > 0 ? formatSize(storage.largest_movies[0].file_size_bytes) : '0' }}
        </div>
        <div class="stat-subtitle">{{ storage.largest_movies.length > 0 ? storage.largest_movies[0].title : '' }}</div>
      </div>
    </div>

    <!-- Storage by Category -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6" v-if="storage">
      <!-- By DV Status -->
      <div class="card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.25s backwards;">
        <div class="flex items-center space-x-3 mb-6">
          <div class="section-icon violet">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
            </svg>
          </div>
          <h3 class="text-lg font-bold">By DV Status</h3>
        </div>
        <div class="space-y-4">
          <div v-for="item in storage.by_dv_status" :key="item.category" class="storage-row">
            <div class="flex items-center justify-between mb-1">
              <span class="text-sm font-semibold" style="color: #f5f5f7;">{{ item.category }}</span>
              <div class="flex items-center space-x-3">
                <span class="text-xs" style="color: #9ca3af;">{{ item.count }} movies</span>
                <span class="text-sm font-bold" style="color: #818cf8;">{{ formatSize(item.total_bytes) }}</span>
              </div>
            </div>
            <div class="storage-bar-track">
              <div class="storage-bar-fill" :style="{ width: getBarWidth(item.total_bytes, storage.total_bytes) + '%', background: dvStatusColor(item.category || '') }"></div>
            </div>
            <div class="text-xs mt-1" style="color: #9ca3af;">Avg: {{ formatSize(item.avg_bytes || 0) }} per movie</div>
          </div>
        </div>
      </div>

      <!-- By Resolution -->
      <div class="card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.3s backwards;">
        <div class="flex items-center space-x-3 mb-6">
          <div class="section-icon green">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h3 class="text-lg font-bold">By Resolution</h3>
        </div>
        <div class="space-y-4">
          <div v-for="item in storage.by_resolution" :key="item.resolution" class="storage-row">
            <div class="flex items-center justify-between mb-1">
              <span class="text-sm font-semibold" style="color: #f5f5f7;">{{ item.resolution }}</span>
              <div class="flex items-center space-x-3">
                <span class="text-xs" style="color: #9ca3af;">{{ item.count }} movies</span>
                <span class="text-sm font-bold" style="color: #10b981;">{{ formatSize(item.total_bytes) }}</span>
              </div>
            </div>
            <div class="storage-bar-track">
              <div class="storage-bar-fill" :style="{ width: getBarWidth(item.total_bytes, storage.total_bytes) + '%', background: resColor(item.resolution || '') }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- By Audio -->
      <div class="card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.35s backwards;">
        <div class="flex items-center space-x-3 mb-6">
          <div class="section-icon blue">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
            </svg>
          </div>
          <h3 class="text-lg font-bold">By Audio</h3>
        </div>
        <div class="space-y-4">
          <div v-for="item in storage.by_audio" :key="item.audio" class="storage-row">
            <div class="flex items-center justify-between mb-1">
              <span class="text-sm font-semibold" style="color: #f5f5f7;">{{ item.audio }}</span>
              <div class="flex items-center space-x-3">
                <span class="text-xs" style="color: #9ca3af;">{{ item.count }}</span>
                <span class="text-sm font-bold" style="color: #3b82f6;">{{ formatSize(item.total_bytes) }}</span>
              </div>
            </div>
            <div class="storage-bar-track">
              <div class="storage-bar-fill" :style="{ width: getBarWidth(item.total_bytes, storage.total_bytes) + '%', background: '#3b82f6' }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- By Codec -->
      <div class="card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.4s backwards;">
        <div class="flex items-center space-x-3 mb-6">
          <div class="section-icon amber">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
          </div>
          <h3 class="text-lg font-bold">By Video Codec</h3>
        </div>
        <div class="space-y-4">
          <div v-for="item in storage.by_codec" :key="item.codec" class="storage-row">
            <div class="flex items-center justify-between mb-1">
              <span class="text-sm font-semibold" style="color: #f5f5f7;">{{ (item.codec || 'Unknown').toUpperCase() }}</span>
              <div class="flex items-center space-x-3">
                <span class="text-xs" style="color: #9ca3af;">{{ item.count }}</span>
                <span class="text-sm font-bold" style="color: #f59e0b;">{{ formatSize(item.total_bytes) }}</span>
              </div>
            </div>
            <div class="storage-bar-track">
              <div class="storage-bar-fill" :style="{ width: getBarWidth(item.total_bytes, storage.total_bytes) + '%', background: '#f59e0b' }"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Largest Movies Table -->
    <div class="card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.45s backwards;" v-if="storage">
      <div class="flex items-center space-x-3 mb-6">
        <div class="section-icon">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
          </svg>
        </div>
        <h3 class="text-lg font-bold">Largest Files</h3>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b" style="border-color: rgba(107, 107, 127, 0.2);">
              <th class="table-header text-left">Title</th>
              <th class="table-header text-left">Year</th>
              <th class="table-header text-left">Quality</th>
              <th class="table-header text-right">Size</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="movie in storage.largest_movies" :key="movie.id" class="table-row">
              <td class="table-cell font-medium" style="color: #f5f5f7;">{{ movie.title }}</td>
              <td class="table-cell" style="color: #9ca3af;">{{ movie.year || '-' }}</td>
              <td class="table-cell">
                <span class="text-xs font-semibold" style="color: #a78bfa;">{{ movie.quality }}</span>
              </td>
              <td class="table-cell text-right font-bold" style="color: #818cf8;">{{ formatSize(movie.file_size_bytes) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading && !storage" class="text-center py-20">
      <div class="inline-block w-10 h-10 border-2 border-[#818cf8] border-t-transparent rounded-full animate-spin"></div>
      <p class="mt-4 text-sm" style="color: #9ca3af;">Analyzing storage...</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAnalyticsStore } from '@/stores/analytics'

const store = useAnalyticsStore()
const storage = computed(() => store.storageAnalytics)

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(i > 2 ? 1 : 0) + ' ' + units[i]
}

function getBarWidth(value: number, total: number): number {
  if (total === 0) return 0
  return Math.max(1, Math.round((value / total) * 100))
}

function dvStatusColor(category: string): string {
  if (category.includes('FEL')) return '#818cf8'
  if (category.includes('Dolby')) return '#7c3aed'
  return '#9ca3af'
}

function resColor(res: string): string {
  if (res === '2160p' || res === '4K') return '#10b981'
  if (res === '1080p') return '#3b82f6'
  return '#f59e0b'
}

onMounted(() => {
  store.fetchStorageAnalytics()
})
</script>

<style scoped>
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

.section-icon {
  width: 40px; height: 40px; border-radius: 10px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(99, 102, 241, 0.2));
  border: 1px solid rgba(99, 102, 241, 0.3);
  display: flex; align-items: center; justify-content: center;
  color: #818cf8; flex-shrink: 0;
}
.section-icon.violet { background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(124, 58, 237, 0.1)); border-color: rgba(124, 58, 237, 0.3); color: #a78bfa; }
.section-icon.green { background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0.1)); border-color: rgba(16, 185, 129, 0.3); color: #34d399; }
.section-icon.blue { background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(59, 130, 246, 0.1)); border-color: rgba(59, 130, 246, 0.3); color: #60a5fa; }
.section-icon.amber { background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0.1)); border-color: rgba(245, 158, 11, 0.3); color: #fbbf24; }

.storage-bar-track {
  width: 100%; height: 4px;
  background: rgba(31, 41, 55, 0.6);
  border-radius: 999px; overflow: hidden;
}
.storage-bar-fill {
  height: 100%; border-radius: 999px;
  transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
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
.table-row:hover { background: rgba(99, 102, 241, 0.05); }
.table-cell { padding: 0.75rem 1rem; font-size: 0.875rem; }
</style>
