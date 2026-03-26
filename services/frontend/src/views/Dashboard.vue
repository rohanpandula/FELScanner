<template>
  <div class="dashboard space-y-8">
    <!-- Statistics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div class="stat-card group" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.1s backwards;">
        <div class="stat-label">Total Library</div>
        <div class="stat-value">{{ moviesStore.statistics.total }}</div>
        <div class="stat-subtitle">Movies Scanned</div>
      </div>

      <div class="stat-card group" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s backwards;">
        <div class="stat-label">Dolby Vision</div>
        <div class="stat-value" style="background: linear-gradient(135deg, #818cf8, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
          {{ moviesStore.statistics.dv_total }}
        </div>
        <div class="stat-subtitle">
          P7: {{ moviesStore.statistics.dv_p7 }} · P5: {{ moviesStore.statistics.dv_p5 }}
        </div>
      </div>

      <div class="stat-card group" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.3s backwards;">
        <div class="stat-label">FEL Enhanced</div>
        <div class="stat-value">{{ moviesStore.statistics.dv_fel }}</div>
        <div class="stat-subtitle">Full Enhancement Layer</div>
      </div>

      <div class="stat-card group" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.4s backwards;">
        <div class="stat-label">Dolby Atmos</div>
        <div class="stat-value" style="background: linear-gradient(135deg, #3b82f6, #60a5fa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
          {{ moviesStore.statistics.atmos_total }}
        </div>
        <div class="stat-subtitle">Object-Based Audio</div>
      </div>
    </div>

    <!-- Scan Control & Status -->
    <div class="card scanner-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.5s backwards;">
      <div class="flex items-center space-x-3 mb-6">
        <div class="scanner-icon">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
          </svg>
        </div>
        <h2 class="text-2xl font-bold">Library Scanner</h2>
      </div>

      <div v-if="appStore.scanStatus" class="space-y-6">
        <div class="flex items-center justify-between">
          <div class="space-y-2">
            <div class="flex items-center space-x-3">
              <span class="text-sm font-semibold" style="color: #9ca3af;">Status</span>
              <span class="scanner-status capitalize" :class="scanStatusClass">
                {{ appStore.scanStatus.state }}
              </span>
            </div>
            <div v-if="appStore.scanStatus.current_movie" class="text-sm mt-2" style="color: #9ca3af;">
              <span class="font-semibold" style="color: #818cf8;">Currently scanning:</span> {{ appStore.scanStatus.current_movie }}
            </div>
          </div>

          <div class="flex space-x-3">
            <button
              @click="triggerScanWithStream()"
              class="btn btn-primary"
              :disabled="!appStore.canTriggerScan || isStreamingScanning"
            >
              {{ isStreamingScanning ? 'Scanning...' : 'Start Scan' }}
            </button>
            <button
              @click="appStore.triggerVerify()"
              class="btn btn-secondary"
              :disabled="!appStore.canTriggerScan"
            >
              Verify
            </button>
            <button
              v-if="appStore.isScanning"
              @click="appStore.cancelScan()"
              class="btn btn-danger"
            >
              Cancel
            </button>
          </div>
        </div>

        <!-- Progress Bar -->
        <div v-if="appStore.isScanning" class="w-full space-y-2">
          <div class="flex justify-between items-center">
            <span class="text-sm font-semibold" style="color: #9ca3af;">Scanning Progress</span>
            <span class="text-sm font-bold" style="color: #818cf8;">
              {{ appStore.scanStatus.scanned_count }} / {{ appStore.scanStatus.total_movies }}
            </span>
          </div>
          <div class="progress-bar-container">
            <div
              class="progress-bar-fill"
              :style="{ width: `${appStore.scanStatus.progress}%` }"
            ></div>
          </div>
        </div>

        <!-- Elapsed Time -->
        <div v-if="appStore.scanStatus.start_time" class="flex items-center space-x-2 text-sm" style="color: #9ca3af;">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span class="font-semibold">Elapsed:</span>
          <span style="color: #818cf8;">{{ formatElapsedTime(appStore.scanStatus.elapsed_time) }}</span>
        </div>
      </div>

      <!-- Scan Log Box (only visible during manual scan) -->
      <div v-if="showLogBox" class="mt-6">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold" style="color: #818cf8;">Scan Log</h3>
          <button
            @click="closeLogBox"
            class="text-gray-400 hover:text-white transition-colors"
            title="Close log"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
        <div
          ref="logContainer"
          class="font-mono text-xs overflow-y-auto rounded p-3"
          style="background: rgba(0, 0, 0, 0.4); max-height: 250px; min-height: 150px;"
        >
          <div
            v-for="(log, index) in scanLogs"
            :key="index"
            class="py-0.5"
            :class="{ 'text-red-400': log.error, 'text-green-400': log.message?.includes('complete'), 'text-gray-300': !log.error && !log.message?.includes('complete') }"
          >
            <span class="text-gray-500">[{{ formatLogTime(log.timestamp) }}]</span>
            <span class="ml-2">{{ log.message }}</span>
            <span v-if="log.progress && log.progress > 0" class="text-blue-400 ml-2">({{ log.progress }}%)</span>
          </div>
          <div v-if="isStreamingScanning && scanLogs.length > 0" class="py-0.5 text-gray-500">
            <span class="animate-pulse">...</span>
          </div>
        </div>
      </div>
    </div>

    <!-- DV Profile Distribution Chart -->
    <div class="card chart-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.6s backwards;">
      <div class="flex items-center space-x-3 mb-6">
        <div class="chart-icon">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
          </svg>
        </div>
        <h2 class="text-2xl font-bold">Profile Distribution</h2>
      </div>
      <div class="w-full max-w-lg mx-auto">
        <canvas ref="chartCanvas"></canvas>
      </div>
    </div>

    <!-- Pending Downloads Summary -->
    <div
      v-if="downloadsStore.hasPendingDownloads"
      class="card downloads-alert"
      style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.7s backwards; background: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.3);"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-4">
          <div class="download-icon-pulse">
            <svg class="w-8 h-8" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h3 class="text-xl font-bold" style="color: #f87171;">Pending Approvals</h3>
            <p class="text-sm mt-1" style="color: #fca5a5; font-weight: 500;">
              {{ downloadsStore.pendingCount }} download{{ downloadsStore.pendingCount !== 1 ? 's' : '' }} awaiting your review
            </p>
          </div>
        </div>
        <router-link to="/downloads" class="btn btn-primary">
          Review Now
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { useAppStore } from '@/stores/app'
import { useMoviesStore } from '@/stores/movies'
import { useDownloadsStore } from '@/stores/downloads'
import { Chart, type ChartConfiguration } from 'chart.js/auto'

const appStore = useAppStore()
const moviesStore = useMoviesStore()
const downloadsStore = useDownloadsStore()

const chartCanvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

// Scan log streaming state
const showLogBox = ref(false)
const scanLogs = ref<Array<{ timestamp: string; message: string; error?: boolean; scanned?: number; total?: number; progress?: number }>>([])
const logContainer = ref<HTMLElement | null>(null)
const isStreamingScanning = ref(false)

const scanStatusClass = computed(() => {
  const state = appStore.scanStatus?.state
  if (state === 'scanning' || state === 'verifying') {
    return 'status-scanning'
  } else if (state === 'idle') {
    return 'status-idle'
  } else if (state === 'error') {
    return 'status-error'
  }
  return ''
})

onMounted(async () => {
  await Promise.all([
    moviesStore.fetchStatistics(),
    downloadsStore.fetchPendingDownloads(),
    appStore.fetchScanStatus(),
    appStore.fetchConnectionStatus(),
  ])
  initializeChart()
})

onUnmounted(() => {
  if (chart) {
    chart.destroy()
  }
})

watch(
  () => moviesStore.statistics,
  () => {
    updateChart()
  },
  { deep: true }
)

function initializeChart() {
  if (!chartCanvas.value) return

  // Build chart data only for profiles that have movies
  const labels: string[] = []
  const data: number[] = []
  const colors: string[] = []

  if (moviesStore.statistics.dv_p5 > 0) {
    labels.push('Profile 5')
    data.push(moviesStore.statistics.dv_p5)
    colors.push('#3b82f6') // Blue for P5
  }
  if (moviesStore.statistics.dv_p7 > 0) {
    labels.push('Profile 7')
    data.push(moviesStore.statistics.dv_p7)
    colors.push('#9333ea') // Purple for P7
  }
  if (moviesStore.statistics.dv_p8 > 0) {
    labels.push('Profile 8')
    data.push(moviesStore.statistics.dv_p8)
    colors.push('#10b981') // Green for P8
  }
  if (moviesStore.statistics.dv_p10 > 0) {
    labels.push('Profile 10')
    data.push(moviesStore.statistics.dv_p10)
    colors.push('#f59e0b') // Amber for P10
  }

  const config: ChartConfiguration = {
    type: 'doughnut',
    data: {
      labels,
      datasets: [
        {
          data,
          backgroundColor: colors,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          position: 'bottom',
        },
      },
    },
  }

  chart = new Chart(chartCanvas.value, config)
}

function updateChart() {
  if (!chart) return

  // Rebuild chart data only for profiles that have movies
  const labels: string[] = []
  const data: number[] = []
  const colors: string[] = []

  if (moviesStore.statistics.dv_p5 > 0) {
    labels.push('Profile 5')
    data.push(moviesStore.statistics.dv_p5)
    colors.push('#3b82f6') // Blue for P5
  }
  if (moviesStore.statistics.dv_p7 > 0) {
    labels.push('Profile 7')
    data.push(moviesStore.statistics.dv_p7)
    colors.push('#9333ea') // Purple for P7
  }
  if (moviesStore.statistics.dv_p8 > 0) {
    labels.push('Profile 8')
    data.push(moviesStore.statistics.dv_p8)
    colors.push('#10b981') // Green for P8
  }
  if (moviesStore.statistics.dv_p10 > 0) {
    labels.push('Profile 10')
    data.push(moviesStore.statistics.dv_p10)
    colors.push('#f59e0b') // Amber for P10
  }

  chart.data.labels = labels
  chart.data.datasets[0].data = data
  chart.data.datasets[0].backgroundColor = colors

  chart.update()
}

function formatElapsedTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs}s`
}

// Format timestamp for log display
function formatLogTime(timestamp: string): string {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { hour12: false })
  } catch {
    return '--:--:--'
  }
}

// Auto-scroll log container to bottom
async function scrollLogToBottom() {
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

// Close the log box
function closeLogBox() {
  showLogBox.value = false
  scanLogs.value = []
}

// Trigger scan with SSE streaming
async function triggerScanWithStream() {
  isStreamingScanning.value = true
  showLogBox.value = true
  scanLogs.value = []

  const streamUrl = '/api/v1/scan/trigger/stream'

  try {
    const eventSource = new EventSource(streamUrl)

    eventSource.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'log') {
          scanLogs.value.push(data)
          await scrollLogToBottom()
        } else if (data.type === 'complete') {
          scanLogs.value.push({
            timestamp: data.timestamp,
            message: `${data.message} - DV: ${data.results.dv_discovered}, FEL: ${data.results.fel_discovered}, Atmos: ${data.results.atmos_discovered}`,
          })
          await scrollLogToBottom()
          eventSource.close()
          isStreamingScanning.value = false

          // Refresh data
          await Promise.all([
            moviesStore.fetchStatistics(),
            appStore.fetchScanStatus(),
          ])
          appStore.addFlashMessage('success', `Scan complete: ${data.results.movies_scanned} movies scanned`)
        } else if (data.type === 'error') {
          scanLogs.value.push({
            timestamp: data.timestamp,
            message: data.message,
            error: true,
          })
          await scrollLogToBottom()
          eventSource.close()
          isStreamingScanning.value = false
          appStore.addFlashMessage('error', data.message)
        } else if (data.type === 'keepalive') {
          // Ignore keepalive
        }
      } catch (e) {
        console.error('Failed to parse SSE message:', e)
      }
    }

    eventSource.onerror = async () => {
      eventSource.close()
      if (isStreamingScanning.value) {
        scanLogs.value.push({
          timestamp: new Date().toISOString(),
          message: 'Connection lost',
          error: true,
        })
        await scrollLogToBottom()
        isStreamingScanning.value = false
        appStore.addFlashMessage('error', 'Lost connection to scan stream')
      }
    }
  } catch (error: any) {
    appStore.addFlashMessage('error', error.message || 'Failed to start scan')
    isStreamingScanning.value = false
  }
}
</script>

<style scoped>
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.scanner-icon,
.chart-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(99, 102, 241, 0.2));
  border: 1px solid rgba(99, 102, 241, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #818cf8;
  flex-shrink: 0;
}

.scanner-status {
  padding: 0.5rem 1rem;
  border-radius: 8px;
  font-weight: 700;
  font-size: 0.875rem;
}

.status-scanning {
  background: rgba(124, 58, 237, 0.2);
  border: 1px solid rgba(124, 58, 237, 0.4);
  color: #a78bfa;
  animation: pulse-status 2s ease-in-out infinite;
}

.status-idle {
  background: rgba(16, 185, 129, 0.2);
  border: 1px solid rgba(16, 185, 129, 0.4);
  color: #34d399;
}

.status-error {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.4);
  color: #f87171;
}

@keyframes pulse-status {
  0%, 100% {
    opacity: 1;
    box-shadow: 0 0 20px currentColor;
  }
  50% {
    opacity: 0.7;
    box-shadow: 0 0 30px currentColor;
  }
}

.progress-bar-container {
  width: 100%;
  height: 12px;
  background: rgba(31, 41, 55, 0.6);
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid rgba(156, 163, 175, 0.2);
  position: relative;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #818cf8, #6366f1, #818cf8);
  background-size: 200% 100%;
  border-radius: 999px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  animation: shimmer-progress 2s ease-in-out infinite;
  box-shadow: 0 0 20px rgba(99, 102, 241, 0.5);
}

@keyframes shimmer-progress {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.download-icon-pulse {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.3);
  border: 2px solid rgba(239, 68, 68, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f87171;
  animation: pulse-download 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  flex-shrink: 0;
}

@keyframes pulse-download {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
  }
  50% {
    transform: scale(1.05);
    box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
  }
}

.downloads-alert {
  position: relative;
  overflow: hidden;
}

.downloads-alert::after {
  content: '';
  position: absolute;
  top: -50%;
  right: -50%;
  bottom: -50%;
  left: -50%;
  background: linear-gradient(
    45deg,
    transparent 30%,
    rgba(239, 68, 68, 0.1) 50%,
    transparent 70%
  );
  animation: alert-shimmer 3s linear infinite;
}

@keyframes alert-shimmer {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
