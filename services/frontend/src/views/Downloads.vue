<template>
  <div class="downloads space-y-8 anim-fade-up">
    <!-- Page header -->
    <header class="flex items-end justify-between flex-wrap gap-4">
      <div>
        <div class="eyebrow mb-2">Approval Queue</div>
        <h1 class="section-title">Downloads</h1>
        <p class="section-sub mt-1">
          Review upgrade candidates, watch live transfers, audit the trail.
        </p>
      </div>
    </header>

    <!-- Tabs -->
    <div class="tabstrip" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        role="tab"
        :aria-selected="activeTab === tab.id"
        @click="activeTab = tab.id"
        class="tab"
        :class="{ 'tab-active': activeTab === tab.id }"
      >
        <span>{{ tab.label }}</span>
        <span v-if="tab.count > 0" class="tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <!-- Pending Approvals Tab -->
    <section v-if="activeTab === 'pending'" class="space-y-5">
      <div class="flex justify-between items-center">
        <h2 class="display text-xl">Pending approvals</h2>
        <button @click="cleanupExpired" class="btn btn-secondary">
          Cleanup expired
        </button>
      </div>

      <div v-if="downloadsStore.isLoading" class="card text-center py-14">
        <div class="spinner mx-auto"></div>
      </div>

      <div v-else-if="!downloadsStore.hasPendingDownloads" class="card text-center py-16">
        <p class="muted">Nothing waiting on a verdict.</p>
      </div>

      <div v-else class="space-y-4">
        <article
          v-for="download in downloadsStore.pendingDownloads"
          :key="download.id"
          class="card card-hoverable pending-card"
        >
          <div class="flex items-start justify-between gap-6 flex-wrap">
            <div class="flex-1 min-w-0">
              <h3 class="display text-lg leading-tight">
                {{ download.movie_title }}
                <span v-if="download.movie_year" class="muted font-normal">({{ download.movie_year }})</span>
              </h3>
              <p class="text-sm muted mt-1 font-mono break-all">{{ download.torrent_name }}</p>
            </div>

            <div class="flex gap-2 shrink-0">
              <button @click="approveDownload(download.id)" class="btn btn-success btn-sm">
                Approve
              </button>
              <button @click="declineDownload(download.id)" class="btn btn-danger btn-sm">
                Decline
              </button>
            </div>
          </div>

          <div class="flex flex-wrap gap-2 mt-4">
            <span class="badge badge-fel">{{ download.quality }}</span>
            <span v-if="download.upgrade_type" class="badge badge-hdr">{{ download.upgrade_type }}</span>
            <span v-if="download.size_mb" class="badge badge-neutral">
              {{ formatSize(download.size_mb) }}
            </span>
            <span v-if="download.seeders !== null" class="badge badge-success">
              {{ download.seeders }} seeders
            </span>
          </div>

          <dl class="meta-grid mt-4">
            <div>
              <dt>Queued</dt>
              <dd>{{ formatDate(download.created_at) }}</dd>
            </div>
            <div>
              <dt>Expires</dt>
              <dd>{{ formatDate(download.expires_at) }}</dd>
            </div>
          </dl>
        </article>
      </div>
    </section>

    <!-- Active Torrents Tab -->
    <section v-if="activeTab === 'active'" class="space-y-5">
      <div class="flex justify-between items-center">
        <h2 class="display text-xl">Active transfers</h2>
        <button @click="refreshActiveTorrents" class="btn btn-secondary">
          Refresh
        </button>
      </div>

      <div v-if="downloadsStore.isLoading" class="card text-center py-14">
        <div class="spinner mx-auto"></div>
      </div>

      <div v-else-if="!downloadsStore.hasActiveTorrents" class="card text-center py-16">
        <p class="muted">No active torrents.</p>
      </div>

      <div v-else class="space-y-6">
        <div v-if="downloadsStore.downloadingTorrents.length > 0">
          <div class="eyebrow mb-3" style="color: #60a5fa">Downloading</div>
          <div class="space-y-3">
            <article
              v-for="torrent in downloadsStore.downloadingTorrents"
              :key="torrent.hash"
              class="card active-card"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="flex-1 min-w-0">
                  <h4 class="font-semibold truncate">{{ torrent.name }}</h4>
                  <div class="text-sm muted mt-1">
                    {{ formatSize(torrent.downloaded / 1048576) }}
                    / {{ formatSize(torrent.size / 1048576) }}
                  </div>
                </div>
                <span class="badge badge-atmos capitalize">{{ torrent.state }}</span>
              </div>

              <div class="progress-wrap mt-4">
                <div class="flex justify-between text-xs muted mb-1.5">
                  <span>Progress</span>
                  <span class="tabular-nums">{{ (torrent.progress * 100).toFixed(1) }}%</span>
                </div>
                <div class="progress-track">
                  <div
                    class="progress-fill"
                    :style="{ width: `${torrent.progress * 100}%` }"
                  ></div>
                </div>
              </div>

              <div class="flex justify-between text-xs muted mt-3 tabular-nums">
                <span>↓ {{ formatSpeed(torrent.download_speed) }}</span>
                <span>↑ {{ formatSpeed(torrent.upload_speed) }}</span>
                <span>ETA {{ formatETA(torrent.eta) }}</span>
              </div>
            </article>
          </div>
        </div>

        <div v-if="downloadsStore.seedingTorrents.length > 0">
          <div class="eyebrow mb-3" style="color: #34d399">Seeding</div>
          <div class="space-y-3">
            <article
              v-for="torrent in downloadsStore.seedingTorrents"
              :key="torrent.hash"
              class="card"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="flex-1 min-w-0">
                  <h4 class="font-semibold truncate">{{ torrent.name }}</h4>
                  <div class="text-sm muted mt-1">
                    {{ formatSize(torrent.size / 1048576) }} ·
                    uploaded {{ formatSize(torrent.uploaded / 1048576) }}
                  </div>
                </div>
                <span class="badge badge-success capitalize">{{ torrent.state }}</span>
              </div>
            </article>
          </div>
        </div>
      </div>
    </section>

    <!-- History Tab -->
    <section v-if="activeTab === 'history'" class="space-y-5">
      <div class="flex justify-between items-center">
        <h2 class="display text-xl">Audit trail</h2>
        <button @click="clearHistory" class="btn btn-danger">
          Clear history
        </button>
      </div>

      <div v-if="downloadsStore.isLoading" class="card text-center py-14">
        <div class="spinner mx-auto"></div>
      </div>

      <div v-else-if="downloadsStore.downloadHistory.length === 0" class="card text-center py-16">
        <p class="muted">No download history yet.</p>
      </div>

      <div v-else class="card p-0 overflow-hidden">
        <div class="overflow-x-auto">
          <table class="data-table">
            <thead>
              <tr>
                <th>Movie</th>
                <th>Torrent</th>
                <th>Quality</th>
                <th>Upgrade</th>
                <th>Action</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in downloadsStore.downloadHistory" :key="item.id">
                <td>
                  <span class="font-medium">{{ item.movie_title }}</span>
                  <span v-if="item.movie_year" class="muted ml-1">({{ item.movie_year }})</span>
                </td>
                <td class="font-mono text-xs muted">{{ item.torrent_name }}</td>
                <td>{{ item.quality }}</td>
                <td class="muted">{{ item.upgrade_type || '—' }}</td>
                <td>
                  <span
                    class="badge"
                    :class="{
                      'badge-success': item.action === 'approved',
                      'badge-danger':  item.action === 'declined',
                      'badge-neutral': item.action === 'expired',
                    }"
                  >
                    {{ item.action }}
                  </span>
                </td>
                <td class="muted">{{ formatDate(item.actioned_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDownloadsStore } from '@/stores/downloads'

const downloadsStore = useDownloadsStore()
const activeTab = ref<'pending' | 'active' | 'history'>('pending')

const tabs = computed(() => [
  { id: 'pending' as const, label: 'Pending', count: downloadsStore.pendingCount },
  { id: 'active'  as const, label: 'Active',  count: downloadsStore.activeCount },
  { id: 'history' as const, label: 'History', count: 0 },
])

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
  if (confirm('Clear download history?')) {
    await downloadsStore.clearHistory()
  }
}

function formatSize(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`
  return `${mb.toFixed(2)} MB`
}
function formatSpeed(bytesPerSec: number): string {
  const mbps = bytesPerSec / 1048576
  if (mbps >= 1) return `${mbps.toFixed(2)} MB/s`
  const kbps = bytesPerSec / 1024
  return `${kbps.toFixed(2)} KB/s`
}
function formatETA(seconds: number): string {
  if (seconds === 0 || seconds === 8640000) return '∞'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}
function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString()
}
</script>

<style scoped>
.tabstrip {
  display: inline-flex;
  padding: 0.3rem;
  background: rgba(10, 10, 15, 0.55);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(107, 107, 127, 0.18);
  border-radius: 12px;
  gap: 0.25rem;
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.55rem 1.05rem;
  font-family: 'Geist', ui-sans-serif, sans-serif;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(180, 180, 198, 0.7);
  border-radius: 9px;
  transition: color 220ms cubic-bezier(0.4, 0, 0.2, 1),
    background 220ms cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
}

.tab:hover { color: #4d7cff; }

.tab-active {
  color: #4d7cff;
  background: rgba(77, 124, 255, 0.12);
  box-shadow: inset 0 0 0 1px rgba(77, 124, 255, 0.25);
}

.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  background: rgba(77, 124, 255, 0.2);
  color: #9bb4ff;
  border-radius: 999px;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.tab:not(.tab-active) .tab-count {
  background: rgba(107, 107, 127, 0.2);
  color: rgba(180, 180, 198, 0.85);
}

.pending-card {
  border-left: 2px solid rgba(77, 124, 255, 0.5);
}

.active-card {
  border-left: 2px solid rgba(59, 130, 246, 0.45);
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(107, 107, 127, 0.12);
}

.meta-grid dt {
  font-family: 'Geist', ui-sans-serif, sans-serif;
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #4d7cff;
  margin-bottom: 0.25rem;
}

.meta-grid dd {
  font-size: 0.82rem;
  color: rgba(236, 236, 240, 0.85);
  font-variant-numeric: tabular-nums;
}

.progress-wrap { width: 100%; }

.progress-track {
  position: relative;
  height: 6px;
  border-radius: 999px;
  background: rgba(45, 45, 61, 0.6);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  /* Warm amber→gold — no AI purple-blue gradient */
  background: linear-gradient(90deg, #c0801a, #4d7cff 55%, #9bb4ff);
  box-shadow: 0 0 14px rgba(77, 124, 255, 0.35);
  transition: width 400ms cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}

.progress-fill::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.35),
    transparent
  );
  animation: stream 1.6s linear infinite;
}

@keyframes stream {
  from { transform: translateX(-100%); }
  to   { transform: translateX(100%); }
}

.spinner {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 2px solid rgba(77, 124, 255, 0.18);
  border-top-color: #4d7cff;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
