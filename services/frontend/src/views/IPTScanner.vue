<template>
  <div class="ipt-scanner space-y-6">
    <!-- Header -->
    <div class="card">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold">IPTorrents Scanner</h1>
          <p class="text-sm text-gray-600 mt-1">Browse and manage IPTorrents cache</p>
        </div>

        <div class="flex space-x-3">
          <button @click="checkHealth" class="btn btn-secondary">
            Check Health
          </button>
          <button @click="triggerScan" class="btn btn-primary" :disabled="isScanning">
            <span v-if="isScanning">Scanning...</span>
            <span v-else>Trigger Scan</span>
          </button>
          <button @click="clearCache" class="btn btn-danger">
            Clear Cache
          </button>
        </div>
      </div>
    </div>

    <!-- Scan Log Box (only visible during manual scan) -->
    <div v-if="showLogBox" class="card">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold" style="color: #4d7cff;">Scan Log</h3>
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
          <span v-if="log.torrents_found" class="text-blue-400 ml-1">({{ log.torrents_found }} torrents)</span>
          <span v-if="log.unique_torrents" class="text-blue-400 ml-1">({{ log.unique_torrents }} unique)</span>
          <span v-if="log.new_count" class="text-green-400 ml-1">({{ log.new_count }} new)</span>
        </div>
        <div v-if="isScanning && scanLogs.length > 0" class="py-0.5 text-gray-500">
          <span class="animate-pulse">...</span>
        </div>
      </div>
    </div>

    <!-- Statistics -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
      <div class="card">
        <div class="text-sm text-gray-600 mb-1">Known Torrents</div>
        <div class="text-3xl font-bold">{{ knownTotal }}</div>
      </div>

      <div class="card">
        <div class="text-sm text-gray-600 mb-1">Latest Scan</div>
        <div class="text-3xl font-bold">{{ scanResults?.total || 0 }}</div>
      </div>

      <div class="card">
        <div class="text-sm text-gray-600 mb-1">New Torrents</div>
        <div class="text-3xl font-bold text-green-600">{{ scanResults?.new || 0 }}</div>
      </div>

      <div class="card">
        <div class="text-sm text-gray-600 mb-1">Last Scan</div>
        <div class="text-lg font-bold text-blue-400">{{ formatScanTime(scanResults?.timestamp) }}</div>
      </div>
    </div>

    <!-- Filters -->
    <div class="card">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
        <div>
          <label class="label">Search</label>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search torrents..."
            class="input"
          />
        </div>

        <div>
          <label class="label">Filter</label>
          <select v-model="filterMode" class="input">
            <option value="all">All Torrents</option>
            <option value="new">New Only</option>
            <option value="not_in_library">Not in Library</option>
            <option value="in_library">In Library</option>
          </select>
        </div>

        <div>
          <label class="label">
            Min Year: <span class="font-mono font-bold" style="color: #4d7cff;">{{ minYear }}</span>
          </label>
          <div class="flex items-center gap-3">
            <input
              v-model.number="minYear"
              type="range"
              :min="1950"
              :max="currentYear"
              class="w-full accent-gold"
              style="height: 6px;"
            />
            <button
              @click="minYear = 1950"
              class="text-xs px-2 py-1 rounded transition-colors shrink-0"
              style="background: rgba(77, 124, 255, 0.1); color: #4d7cff;"
              title="Reset to show all years"
            >
              All
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="card text-center py-12">
      <div class="spinner mx-auto"></div>
      <p class="mt-4 text-gray-600">Loading torrents...</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredTorrents.length === 0" class="card text-center py-12">
      <p class="text-gray-600">No torrents found</p>
    </div>

    <!-- Torrents Table -->
    <div v-else class="card overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-700">
        <thead style="background: rgba(31, 41, 55, 0.6);">
          <tr>
            <th class="px-5 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #4d7cff;">Title</th>
            <th
              class="px-4 py-4 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none"
              style="color: #4d7cff;"
              @click="toggleSort('year')"
            >
              Year
              <span v-if="sortBy === 'year'" class="ml-1">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th
              class="px-4 py-4 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none"
              style="color: #4d7cff;"
              @click="toggleSort('uploaded')"
            >
              Uploaded
              <span v-if="sortBy === 'uploaded'" class="ml-1">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="px-4 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #4d7cff;">Size</th>
            <th class="px-4 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #4d7cff;">Group</th>
            <th class="px-4 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #4d7cff;">Status</th>
            <th class="px-4 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #4d7cff;">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-700" style="background: rgba(20, 20, 30, 0.4);">
          <template v-for="(group, gIdx) in paginatedGroups" :key="gIdx">
            <!-- Main row (first / best torrent in group) -->
            <tr
              class="hover:bg-[rgba(45,45,61,0.4)] transition-colors"
              :class="{ 'bg-[rgba(16,185,129,0.06)]': group.primary.isNew }"
            >
              <!-- Title -->
              <td class="px-5 py-4">
                <div class="flex items-center gap-2">
                  <span v-if="group.primary.isNew" class="shrink-0 inline-block w-2 h-2 rounded-full" style="background: #10b981;" title="New"></span>
                  <div>
                    <a
                      :href="group.primary.link || group.primary.url"
                      target="_blank"
                      class="text-sm font-medium hover:underline transition-colors"
                      style="color: #e5e5e5;"
                      :title="group.primary.name || group.primary.title"
                    >
                      {{ group.primary.metadata?.clean_title || group.primary.name || group.primary.title }}
                    </a>
                    <div class="text-xs mt-0.5" style="color: #6b7280;">
                      <span v-if="group.primary.metadata?.release_type">{{ group.primary.metadata.release_type }}</span>
                      <span v-if="group.primary.metadata?.hdr_type"> · {{ group.primary.metadata.hdr_type }}</span>
                    </div>
                  </div>
                </div>
              </td>

              <td class="px-4 py-4 whitespace-nowrap">
                <div class="text-sm font-mono" style="color: #9ca3af;">{{ group.primary.metadata?.year || '-' }}</div>
              </td>
              <td class="px-4 py-4 whitespace-nowrap">
                <div class="text-sm" style="color: #9ca3af;">{{ formatAdded(group.primary.upload_date) }}</div>
              </td>
              <td class="px-4 py-4 whitespace-nowrap">
                <div class="text-sm" style="color: #9ca3af;">{{ group.primary.size }}</div>
              </td>
              <td class="px-4 py-4 whitespace-nowrap">
                <div class="text-xs font-mono" style="color: #9ca3af;">{{ group.primary.metadata?.release_group || '-' }}</div>
              </td>
              <td class="px-4 py-4 whitespace-nowrap">
                <div v-if="group.primary.library?.in_library">
                  <span class="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium"
                    style="background: rgba(16, 185, 129, 0.12); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.25);">
                    <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                    Owned
                  </span>
                  <div class="text-xs mt-1" style="color: #6b7280;">{{ group.primary.library.library_quality }}</div>
                </div>
                <div v-else>
                  <span class="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium"
                    style="background: rgba(107, 114, 128, 0.12); color: #6b7280; border: 1px solid rgba(107, 114, 128, 0.2);">
                    Not in library
                  </span>
                </div>
              </td>
              <td class="px-4 py-4 whitespace-nowrap">
                <!-- Multiple versions: show versions button instead of download -->
                <button
                  v-if="group.versions.length > 0"
                  @click="toggleGroup(group.key)"
                  class="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded font-semibold cursor-pointer transition-all"
                  style="background: rgba(77, 124, 255, 0.15); color: #7ea1ff; border: 1px solid rgba(77, 124, 255, 0.25);"
                  @mouseover="$event.currentTarget.style.background = 'rgba(77, 124, 255, 0.25)'"
                  @mouseout="$event.currentTarget.style.background = 'rgba(77, 124, 255, 0.15)'"
                >
                  <svg
                    class="w-3 h-3 transition-transform"
                    :class="{ 'rotate-90': expandedGroups.has(group.key) }"
                    fill="currentColor" viewBox="0 0 20 20"
                  >
                    <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/>
                  </svg>
                  {{ group.versions.length + 1 }} versions
                </button>
                <!-- Single version: show download button -->
                <button
                  v-else-if="group.primary.library?.in_library || group.primary.library?.in_radarr"
                  @click="downloadTorrent(group.primary)"
                  :disabled="group.primary._downloading"
                  class="text-xs px-3 py-1.5 rounded font-semibold transition-all inline-block"
                  :style="group.primary._downloading
                    ? 'background: rgba(107, 114, 128, 0.2); color: #6b7280; border: 1px solid rgba(107, 114, 128, 0.3); cursor: wait;'
                    : 'background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); cursor: pointer;'"
                  @mouseover="!group.primary._downloading && ($event.target.style.background = 'rgba(16, 185, 129, 0.25)')"
                  @mouseout="!group.primary._downloading && ($event.target.style.background = 'rgba(16, 185, 129, 0.15)')"
                >
                  {{ group.primary._downloading ? 'Sending...' : 'Download' }}
                </button>
                <button
                  v-else
                  @click="downloadTorrent(group.primary)"
                  :disabled="group.primary._downloading"
                  class="text-xs px-3 py-1.5 rounded font-semibold transition-all inline-block"
                  :style="group.primary._downloading
                    ? 'background: rgba(107, 114, 128, 0.2); color: #6b7280; border: 1px solid rgba(107, 114, 128, 0.3); cursor: wait;'
                    : 'background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); cursor: pointer;'"
                  @mouseover="!group.primary._downloading && ($event.target.style.background = 'rgba(245, 158, 11, 0.25)')"
                  @mouseout="!group.primary._downloading && ($event.target.style.background = 'rgba(245, 158, 11, 0.15)')"
                >
                  {{ group.primary._downloading ? 'Sending...' : 'Add + Download' }}
                </button>
              </td>
            </tr>

            <!-- Expanded sub-rows -->
            <template v-if="expandedGroups.has(group.key)">
              <tr
                v-for="(version, vIdx) in group.versions"
                :key="`${gIdx}-v-${vIdx}`"
                class="transition-colors"
                style="background: rgba(77, 124, 255, 0.03);"
              >
                <td class="px-5 py-3" style="padding-left: 2.5rem;">
                  <div class="flex items-center gap-2">
                    <span class="shrink-0 w-4 text-center" style="color: #4b5563;">└</span>
                    <div>
                      <a
                        :href="version.link || version.url"
                        target="_blank"
                        class="text-sm hover:underline transition-colors"
                        style="color: #9ca3af;"
                        :title="version.name || version.title"
                      >
                        {{ versionLabel(version, group.primary) }}
                      </a>
                      <div class="text-xs mt-0.5" style="color: #4b5563;">
                        <span v-if="version.metadata?.release_type">{{ version.metadata.release_type }}</span>
                        <span v-if="version.metadata?.hdr_type"> · {{ version.metadata.hdr_type }}</span>
                      </div>
                    </div>
                  </div>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">
                  <div class="text-sm font-mono" style="color: #6b7280;">{{ version.metadata?.year || '-' }}</div>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">
                  <div class="text-sm" style="color: #6b7280;">{{ formatAdded(version.upload_date) }}</div>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">
                  <div class="text-sm" :style="version.size !== group.primary.size ? 'color: #7ea1ff;' : 'color: #6b7280;'">{{ version.size }}</div>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">
                  <div class="text-xs font-mono" :style="version.metadata?.release_group !== group.primary.metadata?.release_group ? 'color: #7ea1ff;' : 'color: #6b7280;'">{{ version.metadata?.release_group || '-' }}</div>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">
                  <div v-if="version.library?.in_library">
                    <span class="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium"
                      style="background: rgba(16, 185, 129, 0.12); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.25);">
                      <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                      Owned
                    </span>
                  </div>
                  <div v-else>
                    <span class="text-xs" style="color: #4b5563;">—</span>
                  </div>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">
                  <button
                    v-if="version.library?.in_library || version.library?.in_radarr"
                    @click="downloadTorrent(version)"
                    :disabled="version._downloading"
                    class="text-xs px-3 py-1.5 rounded font-semibold transition-all inline-block"
                    :style="version._downloading
                      ? 'background: rgba(107, 114, 128, 0.2); color: #6b7280; border: 1px solid rgba(107, 114, 128, 0.3); cursor: wait;'
                      : 'background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); cursor: pointer;'"
                  >
                    {{ version._downloading ? '...' : 'Download' }}
                  </button>
                  <button
                    v-else
                    @click="downloadTorrent(version)"
                    :disabled="version._downloading"
                    class="text-xs px-3 py-1.5 rounded font-semibold transition-all inline-block"
                    :style="version._downloading
                      ? 'background: rgba(107, 114, 128, 0.2); color: #6b7280; border: 1px solid rgba(107, 114, 128, 0.3); cursor: wait;'
                      : 'background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); cursor: pointer;'"
                  >
                    {{ version._downloading ? '...' : 'Add + DL' }}
                  </button>
                </td>
              </tr>
            </template>
          </template>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="card">
      <div class="flex items-center justify-between">
        <button
          @click="currentPage--"
          :disabled="currentPage === 1"
          class="btn btn-secondary"
        >
          Previous
        </button>

        <div class="flex items-center space-x-2">
          <span class="text-sm text-gray-600">
            Page {{ currentPage }} of {{ totalPages }} ({{ groupedTorrents.length }} movies, {{ filteredTorrents.length }} torrents)
          </span>
        </div>

        <button
          @click="currentPage++"
          :disabled="currentPage >= totalPages"
          class="btn btn-secondary"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { iptApi } from '@/api'
import type { IPTTorrent, IPTScanResult } from '@/api/types'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const isLoading = ref(false)
const isScanning = ref(false)
const displayTorrents = ref<(IPTTorrent & { _downloading?: boolean })[]>([])
const scanResults = ref<(IPTScanResult & { timestamp?: string }) | null>(null)
const knownTotal = ref(0)
const searchQuery = ref('')
const filterMode = ref('all')
const currentPage = ref(1)
const perPage = 25
const currentYear = new Date().getFullYear()
const minYear = ref(1950)

// Sorting
const sortBy = ref<'year' | 'uploaded' | null>(null)
const sortDir = ref<'asc' | 'desc'>('desc')

function toggleSort(field: 'year' | 'uploaded') {
  if (sortBy.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = field
    sortDir.value = field === 'year' ? 'desc' : 'asc'
  }
  currentPage.value = 1
}

// Log streaming state
const showLogBox = ref(false)
const scanLogs = ref<Array<{ timestamp: string; message: string; error?: boolean; torrents_found?: number; unique_torrents?: number; new_count?: number }>>([])
const logContainer = ref<HTMLElement | null>(null)

onMounted(async () => {
  await Promise.all([loadResults(), loadKnownCount()])
})

const filteredTorrents = computed(() => {
  let torrents = displayTorrents.value

  // Text search
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    torrents = torrents.filter((t) => {
      const title = (t.metadata?.clean_title || t.title || '').toLowerCase()
      return title.includes(query) || t.title.toLowerCase().includes(query)
    })
  }

  // Filter mode
  if (filterMode.value === 'new') {
    torrents = torrents.filter((t) => t.isNew)
  } else if (filterMode.value === 'not_in_library') {
    torrents = torrents.filter((t) => !t.library?.in_library)
  } else if (filterMode.value === 'in_library') {
    torrents = torrents.filter((t) => t.library?.in_library)
  }

  // Min year filter
  if (minYear.value > 1950) {
    torrents = torrents.filter((t) => {
      const year = t.metadata?.year
      return year && year >= minYear.value
    })
  }

  // Sorting
  if (sortBy.value) {
    const dir = sortDir.value === 'asc' ? 1 : -1
    torrents = [...torrents].sort((a, b) => {
      if (sortBy.value === 'year') {
        const aYear = a.metadata?.year || 0
        const bYear = b.metadata?.year || 0
        return (aYear - bYear) * dir
      }
      if (sortBy.value === 'uploaded') {
        // Parse "X.X hours/days ago" into numeric hours for sorting
        const aHours = parseAddedToHours(a.upload_date)
        const bHours = parseAddedToHours(b.upload_date)
        return (aHours - bHours) * dir
      }
      return 0
    })
  }

  return torrents
})

function parseAddedToHours(added?: string): number {
  if (!added) return 99999
  const cleaned = added.replace(/\s+by\s+\S+$/i, '').trim()
  const match = cleaned.match(/([\d.]+)\s*(hour|day|week|month|minute)/i)
  if (!match) return 99999
  const val = parseFloat(match[1])
  const unit = match[2].toLowerCase()
  if (unit.startsWith('minute')) return val / 60
  if (unit.startsWith('hour')) return val
  if (unit.startsWith('day')) return val * 24
  if (unit.startsWith('week')) return val * 24 * 7
  if (unit.startsWith('month')) return val * 24 * 30
  return 99999
}

// Group torrents by normalized title+year
interface TorrentGroup {
  key: string
  primary: any
  versions: any[]
}

const expandedGroups = ref<Set<string>>(new Set())

function toggleGroup(key: string) {
  if (expandedGroups.value.has(key)) {
    expandedGroups.value.delete(key)
  } else {
    expandedGroups.value.add(key)
  }
  // Force reactivity
  expandedGroups.value = new Set(expandedGroups.value)
}

function groupKey(torrent: any): string {
  const title = (torrent.metadata?.clean_title || torrent.name || torrent.title || '').toLowerCase().trim()
  const year = torrent.metadata?.year || ''
  return `${title}|${year}`
}

const groupedTorrents = computed<TorrentGroup[]>(() => {
  const groups = new Map<string, any[]>()
  for (const t of filteredTorrents.value) {
    const key = groupKey(t)
    if (!groups.has(key)) {
      groups.set(key, [])
    }
    groups.get(key)!.push(t)
  }

  const result: TorrentGroup[] = []
  for (const [key, torrents] of groups) {
    // Primary = first in list (already sorted by recency or user sort)
    const [primary, ...versions] = torrents
    result.push({ key, primary, versions })
  }
  return result
})

function versionLabel(version: any, primary: any): string {
  // Build a label showing what's different from the primary
  const diffs: string[] = []
  const vType = version.metadata?.release_type
  const pType = primary.metadata?.release_type
  if (vType && vType !== pType) diffs.push(vType)

  const vHdr = version.metadata?.hdr_type
  const pHdr = primary.metadata?.hdr_type
  if (vHdr && vHdr !== pHdr) diffs.push(vHdr)

  const vGroup = version.metadata?.release_group
  const pGroup = primary.metadata?.release_group
  if (vGroup && vGroup !== pGroup) diffs.push(vGroup)

  if (diffs.length > 0) return diffs.join(' · ')
  // Fallback: show truncated torrent name
  const name = version.name || version.title || ''
  return name.length > 60 ? name.slice(0, 57) + '...' : name
}

const totalPages = computed(() => {
  return Math.ceil(groupedTorrents.value.length / perPage)
})

const paginatedGroups = computed(() => {
  const start = (currentPage.value - 1) * perPage
  const end = start + perPage
  return groupedTorrents.value.slice(start, end)
})

async function loadKnownCount() {
  try {
    const cached = await iptApi.getCachedTorrents()
    knownTotal.value = cached.length
  } catch {
    // Non-critical, ignore
  }
}

async function loadResults() {
  isLoading.value = true
  try {
    const response = await iptApi.getResultsRaw()
    scanResults.value = {
      total: response.results.total,
      new: response.results.new,
      torrents: [],
      timestamp: response.timestamp,
    }
    displayTorrents.value = response.results.torrents.map((t: any) => ({
      title: t.name,
      name: t.name,
      url: t.link,
      link: t.link,
      size: t.size,
      seeders: t.seeders,
      leechers: t.leechers,
      upload_date: t.added,
      isNew: t.isNew,
      metadata: t.metadata,
      library: t.library,
      downloadUrl: t.downloadUrl,
      _downloading: false,
    }))
  } catch (error: any) {
    appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to load scan results')
  } finally {
    isLoading.value = false
  }
}

async function downloadTorrent(torrent: any) {
  if (torrent._downloading) return

  const title = torrent.metadata?.clean_title || torrent.title || torrent.name
  const year = torrent.metadata?.year
  const downloadUrl = torrent.downloadUrl || torrent.link || torrent.url
  const inRadarr = !!torrent.library?.in_radarr

  if (!downloadUrl) {
    appStore.addFlashMessage('error', 'No download URL available for this torrent')
    return
  }

  torrent._downloading = true
  try {
    const result = await iptApi.downloadTorrent({
      title,
      year,
      download_url: downloadUrl,
      in_radarr: inRadarr,
    })
    if (result.success) {
      const action = result.added_to_radarr ? 'Added to Radarr & downloading' : 'Downloading'
      appStore.addFlashMessage('success', `${action}: ${title}`)
    } else {
      appStore.addFlashMessage('error', result.message || 'Download failed')
    }
  } catch (error: any) {
    const detail = error.response?.data?.detail || error.message || 'Download failed'
    appStore.addFlashMessage('error', `Download failed: ${detail}`)
  } finally {
    torrent._downloading = false
  }
}

function formatScanTime(timestamp?: string): string {
  if (!timestamp) return 'Never'
  try {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays}d ago`
  } catch {
    return 'Unknown'
  }
}

function formatLogTime(timestamp: string): string {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { hour12: false })
  } catch {
    return '--:--:--'
  }
}

async function scrollLogToBottom() {
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

function closeLogBox() {
  showLogBox.value = false
  scanLogs.value = []
}

async function triggerScan() {
  isScanning.value = true
  showLogBox.value = true
  scanLogs.value = []

  const streamUrl = '/api/v1/ipt/scan/stream'

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
            message: `Scan complete! Found ${data.results.total} total, ${data.results.new} new.`,
          })
          await scrollLogToBottom()
          eventSource.close()
          isScanning.value = false

          await Promise.all([loadResults(), loadKnownCount()])
          appStore.addFlashMessage('success', `IPT scan complete: ${data.results.new} new torrents found`)
        } else if (data.type === 'error') {
          scanLogs.value.push({
            timestamp: data.timestamp,
            message: data.message,
            error: true,
          })
          await scrollLogToBottom()
          eventSource.close()
          isScanning.value = false
          appStore.addFlashMessage('error', data.message || 'Scan failed')
        }
      } catch (e) {
        console.error('Failed to parse SSE message:', e)
      }
    }

    eventSource.onerror = async () => {
      eventSource.close()
      if (isScanning.value) {
        scanLogs.value.push({
          timestamp: new Date().toISOString(),
          message: 'Connection lost',
          error: true,
        })
        await scrollLogToBottom()
        isScanning.value = false
        appStore.addFlashMessage('error', 'Lost connection to scan stream')
      }
    }
  } catch (error: any) {
    appStore.addFlashMessage('error', error.message || 'Failed to start IPT scan')
    isScanning.value = false
  }
}

function formatAdded(added?: string): string {
  if (!added) return '-'
  return added.replace(/\s+by\s+\S+$/i, '').trim()
}

async function clearCache() {
  if (!confirm('Are you sure you want to clear the IPT cache?')) {
    return
  }

  try {
    const response = await iptApi.clearCache()
    appStore.addFlashMessage('success', response.message || 'Cache cleared successfully')
    displayTorrents.value = []
    scanResults.value = null
  } catch (error: any) {
    appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to clear cache')
  }
}

async function checkHealth() {
  try {
    const response = await iptApi.checkHealth()
    appStore.addFlashMessage('success', `IPT Scraper: ${response.status} - ${response.message}`)
  } catch (error: any) {
    appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to check health')
  }
}
</script>
