<template>
  <figure class="antv-chart" :class="{ 'is-loading': loading }">
    <figcaption v-if="caption || $slots.caption" class="antv-caption">
      <slot name="caption">{{ caption }}</slot>
    </figcaption>

    <div class="antv-frame" :style="frameStyle">
      <transition name="chart">
        <img
          v-if="url && !loading && !error"
          :src="url"
          :alt="alt || caption || 'chart'"
          class="antv-image"
          loading="lazy"
        />
        <div v-else-if="loading" class="antv-skeleton skeleton" />
        <div v-else-if="error" class="antv-error">
          <span class="eyebrow">Chart unavailable</span>
          <p class="subtle">{{ error }}</p>
        </div>
      </transition>
    </div>

    <p v-if="note" class="antv-note subtle">{{ note }}</p>
  </figure>
</template>

<script setup lang="ts">
import { computed, toRef, watch } from 'vue'
import { useAntVChart, type ChartSpec } from '@/composables/useAntVChart'

const props = defineProps<{
  spec: ChartSpec | null
  caption?: string
  note?: string
  alt?: string
}>()

const specRef = toRef(props, 'spec')
const { url, loading, error } = useAntVChart(specRef)

const frameStyle = computed(() => {
  const w = props.spec?.width ?? 800
  const h = props.spec?.height ?? 400
  return { aspectRatio: `${w} / ${h}` }
})

// Quiet warning in case parent hands us an inert spec.
watch(error, (msg) => {
  if (msg) console.warn('[AntVChart]', msg)
})
</script>

<style scoped>
.antv-chart {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 0;
}

.antv-caption {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--zinc-300);
  letter-spacing: 0;
  text-transform: none;
  font-weight: 500;
}

.antv-frame {
  position: relative;
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.015);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 1px 2px rgba(0, 0, 0, 0.25);
}

.antv-image {
  display: block;
  width: 100%;
  height: auto;
}

.antv-skeleton {
  position: absolute;
  inset: 0;
  border-radius: 0;
}

.antv-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 1rem;
  text-align: center;
  color: var(--zinc-500);
}
.antv-error p { font-size: 0.82rem; margin: 0; }

.antv-note {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  margin: 0;
  max-width: 72ch;
  line-height: 1.5;
}

.chart-enter-active { transition: opacity 260ms var(--ease-out); }
.chart-leave-active { transition: opacity 140ms var(--ease-out); }
.chart-enter-from, .chart-leave-to { opacity: 0; }
</style>
