<template>
  <div class="activity-feed space-y-8">
    <!-- Header -->
    <div class="flex items-center justify-between" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.1s backwards;">
      <div class="flex items-center space-x-3">
        <div class="section-icon">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <h1 class="text-2xl font-bold">Activity</h1>
          <p class="text-xs mt-1" style="color: #9ca3af;">Timeline of library changes, downloads, and scans</p>
        </div>
      </div>
    </div>

    <!-- Summary Chips -->
    <div class="flex flex-wrap items-center gap-3" v-if="activitySummary" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.15s backwards;">
      <div class="summary-chip">
        <span class="font-bold" style="color: #4d7cff;">{{ activitySummary.total_events }}</span>
        <span>events in last {{ activitySummary.hours }}h</span>
      </div>
      <div v-for="(count, type) in activitySummary.by_type" :key="type" class="summary-chip">
        <span class="font-bold" :style="{ color: eventColor(type as string) }">{{ count }}</span>
        <span>{{ formatEventType(type as string) }}</span>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="flex items-center space-x-3" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s backwards;">
      <select v-model="filterType" class="input" style="width: auto; padding: 0.5rem 1rem; font-size: 0.8rem;">
        <option value="">All Events</option>
        <option value="movie_added">Movie Added</option>
        <option value="movie_upgraded">Movie Upgraded</option>
        <option value="download_approved">Download Approved</option>
        <option value="download_declined">Download Declined</option>
        <option value="scan_completed">Scan Completed</option>
        <option value="ipt_scan">IPT Scan</option>
      </select>
      <select v-model="filterSeverity" class="input" style="width: auto; padding: 0.5rem 1rem; font-size: 0.8rem;">
        <option value="">All Severity</option>
        <option value="success">Success</option>
        <option value="info">Info</option>
        <option value="warning">Warning</option>
        <option value="error">Error</option>
      </select>
    </div>

    <!-- Timeline -->
    <div class="timeline-container" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.25s backwards;">
      <div v-for="event in events" :key="event.id" class="timeline-item">
        <div class="timeline-dot" :style="{ background: severityColor(event.severity) }"></div>
        <div class="timeline-content card" style="padding: 1rem 1.25rem;">
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center space-x-2 mb-1">
                <span class="event-type-badge" :style="{ color: eventColor(event.event_type), borderColor: eventColor(event.event_type) }">
                  {{ formatEventType(event.event_type) }}
                </span>
                <span v-if="event.movie_title" class="text-sm font-semibold" style="color: #f5f5f7;">
                  {{ event.movie_title }}
                  <span v-if="event.movie_year" style="color: #9ca3af;"> ({{ event.movie_year }})</span>
                </span>
              </div>
              <p class="text-sm font-medium" style="color: #f5f5f7;">{{ event.title }}</p>
              <p v-if="event.description" class="text-xs mt-1" style="color: #9ca3af;">{{ event.description }}</p>
              <div v-if="event.quality_before || event.quality_after" class="flex items-center space-x-2 mt-2">
                <span v-if="event.quality_before" class="text-xs px-2 py-0.5 rounded" style="background: rgba(212, 84, 115, 0.15); color: #d45473;">{{ event.quality_before }}</span>
                <svg v-if="event.quality_before && event.quality_after" class="w-3 h-3" style="color: #9ca3af;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
                <span v-if="event.quality_after" class="text-xs px-2 py-0.5 rounded" style="background: rgba(16, 185, 129, 0.15); color: #34d399;">{{ event.quality_after }}</span>
              </div>
            </div>
            <span class="text-xs flex-shrink-0 ml-4" style="color: #9ca3af;">{{ formatTime(event.created_at) }}</span>
          </div>
        </div>
      </div>

      <div v-if="events.length === 0 && !store.loading" class="text-center py-16">
        <p style="color: #9ca3af;">No activity recorded yet. Events will appear as you scan and manage your library.</p>
      </div>
    </div>

    <!-- Load More -->
    <div v-if="total > events.length" class="text-center">
      <button @click="loadMore" class="btn btn-secondary" :disabled="store.loading">
        Load More
      </button>
    </div>

    <!-- Loading -->
    <div v-if="store.loading && events.length === 0" class="text-center py-20">
      <div class="inline-block w-10 h-10 border-2 border-[#4d7cff] border-t-transparent rounded-full animate-spin"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useActivityStore } from '@/stores/activity'

const store = useActivityStore()
const events = computed(() => store.events)
const total = computed(() => store.total)
const activitySummary = computed(() => store.summary)

const filterType = ref('')
const filterSeverity = ref('')
const currentOffset = ref(0)

watch([filterType, filterSeverity], () => {
  currentOffset.value = 0
  store.fetchFeed({
    event_type: filterType.value || undefined,
    severity: filterSeverity.value || undefined,
    limit: 50,
    offset: 0,
  })
})

function loadMore() {
  currentOffset.value += 50
  store.fetchFeed({
    event_type: filterType.value || undefined,
    severity: filterSeverity.value || undefined,
    limit: 50,
    offset: currentOffset.value,
  })
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatEventType(type: string): string {
  const map: Record<string, string> = {
    movie_added: 'Added',
    movie_upgraded: 'Upgraded',
    movie_removed: 'Removed',
    download_approved: 'Approved',
    download_declined: 'Declined',
    scan_completed: 'Scan',
    collection_changed: 'Collection',
    upgrade_available: 'Upgrade',
    ipt_scan: 'IPT Scan',
  }
  return map[type] || type
}

function eventColor(type: string): string {
  const map: Record<string, string> = {
    movie_added: '#10b981',
    movie_upgraded: '#4d7cff',
    movie_removed: '#d45473',
    download_approved: '#10b981',
    download_declined: '#f59e0b',
    scan_completed: '#3b82f6',
    collection_changed: '#9bb4ff',
    upgrade_available: '#4d7cff',
    ipt_scan: '#4d7cff',
  }
  return map[type] || '#9ca3af'
}

function severityColor(severity: string): string {
  const map: Record<string, string> = {
    success: '#10b981',
    info: '#3b82f6',
    warning: '#f59e0b',
    error: '#d45473',
  }
  return map[severity] || '#9ca3af'
}

onMounted(() => {
  store.fetchFeed({ limit: 50 })
  store.fetchSummary(24)
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

.summary-chip {
  display: flex; align-items: center; gap: 0.375rem;
  padding: 0.375rem 0.75rem; border-radius: 999px;
  background: rgba(31, 41, 55, 0.4);
  border: 1px solid rgba(107, 107, 127, 0.2);
  font-size: 0.75rem; color: #9ca3af;
}

.timeline-container { position: relative; padding-left: 2rem; }
.timeline-container::before {
  content: ''; position: absolute; left: 7px; top: 0; bottom: 0; width: 2px;
  background: rgba(107, 107, 127, 0.15);
}

.timeline-item { position: relative; margin-bottom: 1rem; }
.timeline-dot {
  position: absolute; left: -2rem; top: 1.25rem; width: 12px; height: 12px;
  border-radius: 50%; border: 2px solid rgba(10, 10, 15, 0.8);
  z-index: 1;
}

.timeline-content { margin-left: 0; }
.timeline-content:hover { transform: translateY(-2px); }

.event-type-badge {
  font-size: 0.65rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.08em;
  padding: 0.125rem 0.5rem; border-radius: 4px;
  border: 1px solid; background: transparent;
}
</style>
