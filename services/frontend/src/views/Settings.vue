<template>
  <div class="settings space-y-7 anim-fade-up">
    <header class="flex items-end justify-between flex-wrap gap-4">
      <div>
        <div class="eyebrow mb-2">Integration Status</div>
        <h1 class="section-title">Connections</h1>
        <p class="section-sub mt-1">Every service this scanner depends on, at a glance.</p>
      </div>
      <button @click="appStore.checkConnections()" class="btn btn-secondary">
        Recheck all
      </button>
    </header>

    <div v-if="appStore.connectionStatus" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="(status, service) in appStore.connectionStatus"
        :key="service"
        class="card card-hoverable connection-row"
      >
        <div class="flex items-center gap-3">
          <span
            class="status-dot"
            :class="status.connected ? 'status-idle' : 'status-error'"
          ></span>
          <div class="min-w-0">
            <div class="conn-name">{{ formatServiceName(service) }}</div>
            <div class="conn-state">
              {{ status.connected ? 'Online' : 'Unreachable' }}
            </div>
          </div>
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

<style scoped>
.connection-row { padding: 1.25rem 1.35rem; }
.conn-name {
  font-family: 'Geist', ui-sans-serif, sans-serif;
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--cinema-white);
  text-transform: capitalize;
}
.conn-state {
  font-family: 'Geist', ui-sans-serif, sans-serif;
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--cinema-gray);
  margin-top: 2px;
}
</style>
