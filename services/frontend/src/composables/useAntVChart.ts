import { ref, watch, type Ref, type MaybeRef, unref, isRef } from 'vue'
import { apiClient } from '@/api/client'

type ChartTheme = 'default' | 'academy' | 'dark'

export interface ChartSpec {
  type: string
  data?: unknown
  title?: string
  theme?: ChartTheme
  width?: number
  height?: number
  // Chart-specific extras (innerRadius, stack, axisYTitle, percent, …)
  extra?: Record<string, unknown>
}

interface Options {
  /** Re-render when this boolean flips to true (e.g., data is ready). */
  enabled?: MaybeRef<boolean>
}

/**
 * Wraps the AntV chart proxy (/api/v1/viz/chart). Posts a spec, stores the
 * returned hosted image URL. Reactive — updates when the spec ref changes.
 */
export function useAntVChart(spec: Ref<ChartSpec | null>, options: Options = {}) {
  const url = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function render() {
    const value = spec.value
    if (!value) return
    const enabled = unref(options.enabled)
    if (enabled === false) return

    loading.value = true
    error.value = null
    try {
      const res = await apiClient.post<{ url: string }>('/v1/viz/chart', {
        type: value.type,
        data: value.data,
        title: value.title,
        theme: value.theme ?? 'dark',
        width: value.width ?? 800,
        height: value.height ?? 400,
        extra: value.extra ?? null,
      })
      url.value = res.url
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Chart failed'
      error.value = msg
    } finally {
      loading.value = false
    }
  }

  watch(spec, render, { immediate: true, deep: true })
  if (isRef(options.enabled)) {
    watch(options.enabled, (v) => { if (v) render() })
  }

  return { url, loading, error, render }
}
