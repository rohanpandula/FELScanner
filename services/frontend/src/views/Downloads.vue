<template>
  <div class="downloads space-y-6">
    <!-- Tabs -->
    <div class="card">
      <div class="flex border-b border-gray-200">
        <button
          @click="activeTab = 'pending'"
          class="px-6 py-3 font-medium transition-colors"
          :class="activeTab === 'pending' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-600 hover:text-gray-900'"
        >
          Pending Approvals
          <span v-if="downloadsStore.pendingCount > 0" class="ml-2 px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded-full">
            {{ downloadsStore.pendingCount }}
          </span>
        </button>
        <button
          @click="activeTab = 'active'"
          class="px-6 py-3 font-medium transition-colors"
          :class="activeTab === 'active' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-600 hover:text-gray-900'"
        >
          Active Torrents
          <span v-if="downloadsStore.activeCount > 0" class="ml-2 px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
            {{ downloadsStore.activeCount }}
          </span>
        </button>
        <button
          @click="activeTab = 'history'"
          class="px-6 py-3 font-medium transition-colors"
          :class="activeTab === 'history' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-600 hover:text-gray-900'"
        >
          History
        </button>
      </div>
    </div>

    <!-- Pending Approvals Tab -->
    <div v-if="activeTab === 'pending'" class="space-y-4">
      <div class="flex justify-between items-center">
        <h2 class="text-xl font-bold">Pending Download Approvals</h2>
        <button @click="cleanupExpired" class="btn btn-secondary">
          Cleanup Expired
        </button>
      </div>

      <div v-if="downloadsStore.isLoading" class="card text-center py-12">
        <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>

      <div v-else-if="!downloadsStore.hasPendingDownloads" class="card text-center py-12">
        <p class="text-gray-600">No pending download approvals</p>
      </div>

      <div v-else class="space-y-4">
        <div
          v-for="download in downloadsStore.pendingDownloads"
          :key="download.id"
          class="card bg-yellow-50 border border-yellow-200"
        >
          <div class="space-y-3">
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <h3 class="text-lg font-semibold">
                  {{ download.movie_title }}
                  <span v-if="download.movie_year" class="text-gray-600">({{ download.movie_year }})</span>
                </h3>
                <p class="text-sm text-gray-700 mt-1">{{ download.torrent_name }}</p>
              </div>

              <div class="flex space-x-2">
                <button
                  @click="approveDownload(download.id)"
                  class="btn btn-success"
                >
                  Approve
                </button>
                <button
                  @click="declineDownload(download.id)"
                  class="btn btn-danger"
                >
                  Decline
                </button>
              </div>
            </div>

            <div class="flex flex-wrap gap-2">
              <span class="badge badge-info">{{ download.quality }}</span>
              <span v-if="download.upgrade_type" class="badge badge-warning">{{ download.upgrade_type }}</span>
              <span v-if="download.size_mb" class="badge bg-gray-100 text-gray-800">
                {{ formatSize(download.size_mb) }}
              </span>
              <span v-if="download.seeders !== null" class="badge bg-green-100 text-green-800">
                {{ download.seeders }} seeders
              </span>
            </div>

            <div class="text-xs text-gray-600">
              <div>Created: {{ formatDate(download.created_at) }}</div>
              <div>Expires: {{ formatDate(download.expires_at) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Active Torrents Tab -->
    <div v-if="activeTab === 'active'" class="space-y-4">
      <div class="flex justify-between items-center">
        <h2 class="text-xl font-bold">Active Torrents</h2>
        <button @click="refreshActiveTorrents" class="btn btn-secondary">
          Refresh
        </button>
      </div>

      <div v-if="downloadsStore.isLoading" class="card text-center py-12">
        <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>

      <div v-else-if="!downloadsStore.hasActiveTorrents" class="card text-center py-12">
        <p class="text-gray-600">No active torrents</p>
      </div>

      <div v-else class="space-y-4">
        <!-- Downloading Torrents -->
        <div v-if="downloadsStore.downloadingTorrents.length > 0">
          <h3 class="font-semibold mb-3">Downloading</h3>
          <div class="space-y-3">
            <div
              v-for="torrent in downloadsStore.downloadingTorrents"
              :key="torrent.hash"
              class="card bg-blue-50 border border-blue-200"
            >
              <div class="space-y-3">
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <h4 class="font-medium">{{ torrent.name }}</h4>
                    <div class="text-sm text-gray-600 mt-1">
                      {{ formatSize(torrent.downloaded / 1048576) }} / {{ formatSize(torrent.size / 1048576) }}
                    </div>
                  </div>
                  <span class="badge bg-blue-100 text-blue-800 capitalize">{{ torrent.state }}</span>
                </div>

                <div class="w-full">
                  <div class="flex justify-between text-sm mb-1">
                    <span>Progress</span>
                    <span>{{ (torrent.progress * 100).toFixed(1) }}%</span>
                  </div>
                  <div class="w-full bg-gray-200 rounded-full h-2">
                    <div
                      class="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      :style="{ width: `${torrent.progress * 100}%` }"
                    ></div>
                  </div>
                </div>

                <div class="flex justify-between text-sm text-gray-600">
                  <span>↓ {{ formatSpeed(torrent.download_speed) }}</span>
                  <span>↑ {{ formatSpeed(torrent.upload_speed) }}</span>
                  <span>ETA: {{ formatETA(torrent.eta) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Seeding Torrents -->
        <div v-if="downloadsStore.seedingTorrents.length > 0">
          <h3 class="font-semibold mb-3">Seeding</h3>
          <div class="space-y-3">
            <div
              v-for="torrent in downloadsStore.seedingTorrents"
              :key="torrent.hash"
              class="card bg-green-50 border border-green-200"
            >
              <div class="flex items-start justify-between">
                <div class="flex-1">
                  <h4 class="font-medium">{{ torrent.name }}</h4>
                  <div class="text-sm text-gray-600 mt-1">
                    Size: {{ formatSize(torrent.size / 1048576) }} |
                    Uploaded: {{ formatSize(torrent.uploaded / 1048576) }}
                  </div>
                </div>
                <span class="badge bg-green-100 text-green-800 capitalize">{{ torrent.state }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- History Tab -->
    <div v-if="activeTab === 'history'" class="space-y-4">
      <div class="flex justify-between items-center">
        <h2 class="text-xl font-bold">Download History</h2>
        <button @click="clearHistory" class="btn btn-danger">
          Clear History
        </button>
      </div>

      <div v-if="downloadsStore.isLoading" class="card text-center py-12">
        <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>

      <div v-else-if="downloadsStore.downloadHistory.length === 0" class="card text-center py-12">
        <p class="text-gray-600">No download history</p>
      </div>

      <div v-else class="card overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-gray-200">
            <tr>
              <th class="text-left py-3 px-4">Movie</th>
              <th class="text-left py-3 px-4">Torrent</th>
              <th class="text-left py-3 px-4">Quality</th>
              <th class="text-left py-3 px-4">Upgrade Type</th>
              <th class="text-left py-3 px-4">Action</th>
              <th class="text-left py-3 px-4">Date</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in downloadsStore.downloadHistory"
              :key="item.id"
              class="border-b border-gray-100 hover:bg-gray-50"
            >
              <td class="py-3 px-4">
                {{ item.movie_title }}
                <span v-if="item.movie_year" class="text-gray-600">({{ item.movie_year }})</span>
              </td>
              <td class="py-3 px-4 font-mono text-xs">{{ item.torrent_name }}</td>
              <td class="py-3 px-4">{{ item.quality }}</td>
              <td class="py-3 px-4">{{ item.upgrade_type || '-' }}</td>
              <td class="py-3 px-4">
                <span
                  class="badge"
                  :class="{
                    'bg-green-100 text-green-800': item.action === 'approved',
                    'bg-red-100 text-red-800': item.action === 'declined',
                    'bg-gray-100 text-gray-800': item.action === 'expired',
                  }"
                >
                  {{ item.action }}
                </span>
              </td>
              <td class="py-3 px-4">{{ formatDate(item.actioned_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDownloadsStore } from '@/stores/downloads'

const downloadsStore = useDownloadsStore()
const activeTab = ref<'pending' | 'active' | 'history'>('pending')

onMounted(async () => {
  await downloadsStore.fetchPendingDownloads()
  await downloadsStore.fetchActiveTorrents()
})

async function approveDownload(downloadId: number) {
  await downloadsStore.approveDownload(downloadId)
}

async function declineDownload(downloadId: number) {
  await downloadsStore.declineDownload(downloadId)
}

async function cleanupExpired() {
  await downloadsStore.cleanupExpired()
}

async function refreshActiveTorrents() {
  await downloadsStore.fetchActiveTorrents()
}

async function clearHistory() {
  if (confirm('Are you sure you want to clear download history?')) {
    await downloadsStore.clearHistory()
  }
}

function formatSize(mb: number): string {
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(2)} GB`
  }
  return `${mb.toFixed(2)} MB`
}

function formatSpeed(bytesPerSec: number): string {
  const mbps = bytesPerSec / 1048576
  if (mbps >= 1) {
    return `${mbps.toFixed(2)} MB/s`
  }
  const kbps = bytesPerSec / 1024
  return `${kbps.toFixed(2)} KB/s`
}

function formatETA(seconds: number): string {
  if (seconds === 0 || seconds === 8640000) return '∞'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleString()
}
</script>
