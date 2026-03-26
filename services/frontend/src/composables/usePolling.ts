import { onMounted, onUnmounted, ref } from 'vue'

export function usePolling(callback: () => void | Promise<void>, intervalMs: number = 15000) {
  const isPolling = ref(false)
  const intervalId = ref<number | null>(null)

  function start() {
    if (isPolling.value) return

    isPolling.value = true

    // Immediate call
    callback()

    // Set up interval
    intervalId.value = window.setInterval(() => {
      callback()
    }, intervalMs)
  }

  function stop() {
    if (!isPolling.value) return

    isPolling.value = false

    if (intervalId.value !== null) {
      clearInterval(intervalId.value)
      intervalId.value = null
    }
  }

  onMounted(() => {
    start()
  })

  onUnmounted(() => {
    stop()
  })

  return {
    isPolling,
    start,
    stop,
  }
}
