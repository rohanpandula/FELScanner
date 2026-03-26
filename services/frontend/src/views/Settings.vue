<template>
  <div class="settings space-y-6">
    <!-- Service Connections -->
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-bold">Service Connections</h2>
        <button @click="appStore.checkConnections()" class="btn btn-secondary btn-sm">
          Check All
        </button>
      </div>

      <div v-if="appStore.connectionStatus" class="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div
          v-for="(status, service) in appStore.connectionStatus"
          :key="service"
          class="flex items-center space-x-2"
        >
          <span
            class="h-3 w-3 rounded-full"
            :class="status.connected ? 'bg-green-500' : 'bg-red-500'"
          ></span>
          <span class="capitalize text-sm">{{ formatServiceName(service) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

onMounted(async () => {
  // Fetch connection status when the settings page loads
  await appStore.fetchConnectionStatus()
})

function formatServiceName(service: string): string {
  return service.replace(/_/g, ' ')
}
</script>
