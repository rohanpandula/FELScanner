<template>
  <div class="quality-report space-y-8">
    <!-- Health Score Hero -->
    <div class="card health-hero" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.1s backwards;">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center space-x-3 mb-4">
            <div class="section-icon">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <h2 class="text-2xl font-bold">Library Health</h2>
          </div>
          <p class="text-sm" style="color: #9ca3af;">Overall quality assessment of your Plex library</p>
        </div>
        <div class="health-score-ring">
          <svg viewBox="0 0 120 120" class="w-32 h-32">
            <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(31, 41, 55, 0.6)" stroke-width="8" />
            <circle
              cx="60" cy="60" r="52"
              fill="none"
              :stroke="healthScoreColor"
              stroke-width="8"
              stroke-linecap="round"
              :stroke-dasharray="`${(report?.health_score || 0) * 3.267} 326.7`"
              stroke-dashoffset="0"
              transform="rotate(-90 60 60)"
              style="transition: stroke-dasharray 1s cubic-bezier(0.4, 0, 0.2, 1);"
            />
            <text x="60" y="55" text-anchor="middle" :fill="healthScoreColor" font-size="28" font-weight="900">
              {{ report?.health_score || 0 }}
            </text>
            <text x="60" y="72" text-anchor="middle" fill="#9ca3af" font-size="10" font-weight="600" style="text-transform: uppercase; letter-spacing: 0.1em;">
              / 100
            </text>
          </svg>
        </div>
      </div>
    </div>

    <!-- Key Metrics -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4" v-if="report">
      <div class="stat-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.15s backwards;">
        <div class="stat-label">Dolby Vision</div>
        <div class="stat-value" style="font-size: 1.75rem; background: linear-gradient(135deg, #4d7cff, #9bb4ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
          {{ report.quality_summary.dv_percentage }}%
        </div>
        <div class="stat-subtitle">{{ report.quality_summary.dv_count }} movies</div>
      </div>
      <div class="stat-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s backwards;">
        <div class="stat-label">FEL (P7)</div>
        <div class="stat-value" style="font-size: 1.75rem;">
          {{ report.quality_summary.fel_percentage }}%
        </div>
        <div class="stat-subtitle">{{ report.quality_summary.fel_count }} movies</div>
      </div>
      <div class="stat-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.25s backwards;">
        <div class="stat-label">Atmos</div>
        <div class="stat-value" style="font-size: 1.75rem; background: linear-gradient(135deg, #3b82f6, #60a5fa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
          {{ report.quality_summary.atmos_percentage }}%
        </div>
        <div class="stat-subtitle">{{ report.quality_summary.atmos_count }} movies</div>
      </div>
      <div class="stat-card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.3s backwards;">
        <div class="stat-label">4K</div>
        <div class="stat-value" style="font-size: 1.75rem; background: linear-gradient(135deg, #10b981, #34d399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
          {{ report.quality_summary.fourk_percentage }}%
        </div>
        <div class="stat-subtitle">{{ report.quality_summary.fourk_count }} movies</div>
      </div>
    </div>

    <!-- Quality Tiers -->
    <div class="card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.35s backwards;" v-if="report">
      <div class="flex items-center space-x-3 mb-6">
        <div class="section-icon">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
          </svg>
        </div>
        <h2 class="text-xl font-bold">Quality Distribution</h2>
      </div>

      <div class="space-y-3">
        <div v-for="tier in qualityTierData" :key="tier.key" class="tier-bar-row">
          <div class="flex items-center justify-between mb-1">
            <div class="flex items-center space-x-2">
              <span class="tier-dot" :style="{ background: tier.color }"></span>
              <span class="text-sm font-semibold" style="color: #f5f5f7;">{{ tier.label }}</span>
            </div>
            <div class="flex items-center space-x-3">
              <span class="text-sm font-bold" :style="{ color: tier.color }">{{ tier.count }}</span>
              <span class="text-xs" style="color: #9ca3af;">{{ tier.percentage }}%</span>
            </div>
          </div>
          <div class="tier-bar-track">
            <div
              class="tier-bar-fill"
              :style="{ width: tier.barWidth + '%', background: tier.color }"
            ></div>
          </div>
          <div class="text-xs mt-1" style="color: #9ca3af;">{{ tier.description }}</div>
        </div>
      </div>
    </div>

    <!-- Storytelling viz row: quality tiers + quality radar -->
    <section v-if="report" class="grid grid-cols-1 lg:grid-cols-5 gap-5">
      <div class="card p-4 lg:col-span-3">
        <AntVChart
          :spec="tierPieSpec"
          caption="Quality tiers"
          note="A full pie is a 100%-covered library. The slices tell you how close you are to a reference-grade collection."
        />
      </div>
      <div class="card p-4 lg:col-span-2">
        <AntVChart
          :spec="qualityRadarSpec"
          caption="Quality dimensions"
          note="Each axis is the percentage of the library that meets that quality signal."
        />
      </div>
    </section>

    <!-- Distribution Charts Row -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6" v-if="report">
      <!-- DV Profile Breakdown -->
      <div class="card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.4s backwards;">
        <h3 class="text-lg font-bold mb-4">DV Profile Breakdown</h3>
        <div class="space-y-3">
          <div v-for="(count, profile) in report.profile_breakdown" :key="profile" class="flex items-center justify-between py-2 border-b" style="border-color: rgba(107, 107, 127, 0.15);">
            <span class="badge" :class="profileBadgeClass(profile as string)">{{ profile }}</span>
            <span class="text-sm font-bold" style="color: #f5f5f7;">{{ count }}</span>
          </div>
          <div v-if="Object.keys(report.profile_breakdown).length === 0" class="text-center py-8" style="color: #9ca3af;">
            No Dolby Vision movies detected
          </div>
        </div>
      </div>

      <!-- Resolution Breakdown -->
      <div class="card" style="animation: fadeInUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.45s backwards;">
        <h3 class="text-lg font-bold mb-4">Resolution Breakdown</h3>
        <div class="space-y-3">
          <div v-for="(count, res) in report.resolution_distribution" :key="res" class="flex items-center justify-between py-2 border-b" style="border-color: rgba(107, 107, 127, 0.15);">
            <span class="badge" :class="resBadgeClass(res as string)">{{ res }}</span>
            <span class="text-sm font-bold" style="color: #f5f5f7;">{{ count }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="store.loading && !report" class="text-center py-20">
      <div class="inline-block w-10 h-10 border-2 border-[#4d7cff] border-t-transparent rounded-full animate-spin"></div>
      <p class="mt-4 text-sm" style="color: #9ca3af;">Analyzing library quality...</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAnalyticsStore } from '@/stores/analytics'
import AntVChart from '@/components/AntVChart.vue'
import type { ChartSpec } from '@/composables/useAntVChart'

const store = useAnalyticsStore()
const report = computed(() => store.qualityReport)

const tierPieSpec = computed<ChartSpec | null>(() => {
  const r = report.value
  if (!r) return null
  const tiers = r.quality_tiers
  const entries = [
    { category: 'Reference',     value: tiers.reference },
    { category: 'Excellent',     value: tiers.excellent },
    { category: 'Great',         value: tiers.great },
    { category: 'Good',          value: tiers.good },
    { category: 'Acceptable',    value: tiers.acceptable },
    { category: 'Needs upgrade', value: tiers.needs_upgrade },
  ].filter((e) => e.value > 0)
  if (!entries.length) return null
  return {
    type: 'pie',
    theme: 'dark',
    width: 600,
    height: 440,
    data: entries,
    extra: { innerRadius: 0.62 },
  }
})

const qualityRadarSpec = computed<ChartSpec | null>(() => {
  const r = report.value
  if (!r) return null
  const q = r.quality_summary
  return {
    type: 'radar',
    theme: 'dark',
    width: 500,
    height: 440,
    data: [
      { name: 'Dolby Vision', value: q.dv_percentage },
      { name: 'FEL (P7)',     value: q.fel_percentage },
      { name: 'Atmos',        value: q.atmos_percentage },
      { name: '4K',           value: q.fourk_percentage },
    ],
  }
})

const healthScoreColor = computed(() => {
  const score = report.value?.health_score || 0
  if (score >= 80) return '#10b981'
  if (score >= 60) return '#4d7cff'
  if (score >= 40) return '#f59e0b'
  return '#d45473'
})

function pctRaw(count: number, total: number): number {
  return (count / (total || 1)) * 100
}
function pctLabel(count: number, total: number): string {
  if (count === 0) return '0'
  const raw = pctRaw(count, total)
  if (raw < 1) return '<1'
  if (raw < 10) return raw.toFixed(1)
  return String(Math.round(raw))
}
function pctBarWidth(count: number, total: number): number {
  const raw = pctRaw(count, total)
  if (raw === 0) return 0
  return Math.max(1.2, raw) // visible minimum so tiny-but-nonzero tiers still draw a sliver
}

const qualityTierData = computed(() => {
  if (!report.value) return []
  const tiers = report.value.quality_tiers
  const total = report.value.total_movies || 1

  const rows = [
    { key: 'reference',     label: 'Reference',     count: tiers.reference,     color: '#4d7cff', description: 'P7 FEL + Atmos + 4K' },
    { key: 'excellent',     label: 'Excellent',     count: tiers.excellent,     color: '#10b981', description: 'Dolby Vision + Atmos + 4K' },
    { key: 'great',         label: 'Great',         count: tiers.great,         color: '#4d7cff', description: 'DV + 4K or FEL' },
    { key: 'good',          label: 'Good',          count: tiers.good,          color: '#3b82f6', description: '4K HDR or DV 1080p' },
    { key: 'acceptable',    label: 'Acceptable',    count: tiers.acceptable,    color: '#f59e0b', description: '4K SDR or 1080p HDR' },
    { key: 'needs_upgrade', label: 'Needs Upgrade', count: tiers.needs_upgrade, color: '#d45473', description: '1080p SDR or lower' },
  ]
  return rows.map((r) => ({
    ...r,
    percentage: pctLabel(r.count, total),
    barWidth:   pctBarWidth(r.count, total),
  }))
})

function profileBadgeClass(profile: string) {
  if (profile === 'P7') return 'badge-p7'
  if (profile === 'P5') return 'badge-hdr'
  if (profile === 'P8') return 'badge-4k'
  return 'badge-atmos'
}

function resBadgeClass(res: string) {
  if (res === '2160p' || res === '4K') return 'badge-4k'
  if (res === '1080p') return 'badge-atmos'
  return 'badge-hdr'
}

onMounted(() => {
  store.fetchQualityReport()
})
</script>

<style scoped>
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

.section-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(77, 124, 255, 0.2), rgba(77, 124, 255, 0.2));
  border: 1px solid rgba(77, 124, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4d7cff;
  flex-shrink: 0;
}

.health-hero {
  background: rgba(26, 26, 36, 0.6);
}

.tier-bar-track {
  width: 100%;
  height: 6px;
  background: rgba(31, 41, 55, 0.6);
  border-radius: 999px;
  overflow: hidden;
}

.tier-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
}

.tier-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
