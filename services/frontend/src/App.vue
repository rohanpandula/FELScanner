<template>
  <div id="app" class="min-h-screen relative" style="padding-top: 2px;">
    <!-- Header -->
    <header class="sticky top-0 z-50" style="background: rgba(11, 15, 25, 0.8); backdrop-filter: blur(16px); border-bottom: 1px solid rgba(55, 65, 81, 0.5);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center py-4">
          <!-- Logo & Status -->
          <div class="flex items-center space-x-5">
            <div class="flex items-center space-x-3">
              <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: linear-gradient(135deg, #6366f1, #8b5cf6);">
                <svg class="w-[18px] h-[18px] text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                </svg>
              </div>
              <div>
                <h1 class="text-lg font-bold text-white" style="letter-spacing: -0.01em;">FELScanner</h1>
              </div>
            </div>

            <!-- Status Indicator -->
            <div v-if="appStore.scanStatus" class="flex items-center space-x-2 px-3 py-1.5 rounded-full" style="background: rgba(31, 41, 55, 0.5); border: 1px solid rgba(55, 65, 81, 0.5);">
              <span
                class="h-2 w-2 rounded-full"
                :class="statusIndicatorClass"
              ></span>
              <span class="text-xs font-medium" style="color: #9ca3af;">{{ appStore.scanStatus.state }}</span>
            </div>
          </div>

          <!-- Navigation -->
          <nav class="flex items-center space-x-1">
            <router-link to="/" class="nav-link" exact-active-class="nav-link-active">
              Dashboard
            </router-link>
            <router-link to="/quality" class="nav-link" active-class="nav-link-active">
              Quality
            </router-link>
            <router-link to="/insights" class="nav-link" active-class="nav-link-active">
              Insights
            </router-link>
            <router-link to="/storage" class="nav-link" active-class="nav-link-active">
              Storage
            </router-link>
            <router-link to="/metadata" class="nav-link" active-class="nav-link-active">
              Metadata
            </router-link>
            <router-link to="/downloads" class="nav-link" active-class="nav-link-active">
              Downloads
            </router-link>
            <router-link to="/ipt" class="nav-link" active-class="nav-link-active">
              IPT
            </router-link>

            <!-- More dropdown -->
            <div class="relative" @mouseenter="showMoreMenu = true" @mouseleave="showMoreMenu = false">
              <button class="nav-link flex items-center space-x-1">
                <span>More</span>
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
              </button>
              <div v-show="showMoreMenu" class="more-dropdown">
                <router-link to="/release-groups" class="dropdown-link" active-class="dropdown-link-active">
                  Release Groups
                </router-link>
                <router-link to="/activity" class="dropdown-link" active-class="dropdown-link-active">
                  Activity
                </router-link>
                <router-link to="/settings" class="dropdown-link" active-class="dropdown-link-active">
                  Settings
                </router-link>
              </div>
            </div>
          </nav>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 relative z-10">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- Flash Messages -->
    <div class="fixed bottom-6 right-6 z-50 space-y-3">
      <transition-group name="flash">
        <div
          v-for="message in appStore.flashMessages"
          :key="message.id"
          class="flash-message"
          :class="flashMessageClass(message.type)"
        >
          <div class="flex items-start space-x-3">
            <span class="flash-icon" v-html="flashMessageIcon(message.type)"></span>
            <span class="flex-1 font-medium text-sm">{{ message.message }}</span>
            <button
              @click="appStore.removeFlashMessage(message.id)"
              class="flash-close"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      </transition-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const showMoreMenu = ref(false)

const statusIndicatorClass = computed(() => {
  const state = appStore.scanStatus?.state
  if (state === 'scanning' || state === 'verifying') {
    return 'bg-[#818cf8]'
  } else if (state === 'idle') {
    return 'bg-[#10b981]'
  } else if (state === 'error') {
    return 'bg-[#ef4444]'
  }
  return 'bg-[#6b7280]'
})

const flashMessageClass = (type: string) => {
  const classes = {
    success: 'flash-success',
    error: 'flash-error',
    warning: 'flash-warning',
    info: 'flash-info',
  }
  return classes[type as keyof typeof classes] || classes.info
}

const flashMessageIcon = (type: string) => {
  const icons = {
    success: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>',
    error: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>',
    warning: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
    info: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
  }
  return icons[type as keyof typeof icons] || icons.info
}

onMounted(() => {
  appStore.startPolling()
})

onUnmounted(() => {
  appStore.stopPolling()
})
</script>

<style scoped>
/* Navigation Links */
.nav-link {
  padding: 0.5rem 0.875rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #9ca3af;
  border-radius: 8px;
  transition: color 0.2s;
}

.nav-link:hover {
  color: white;
}

.nav-link-active {
  color: white;
  background: rgba(99, 102, 241, 0.15);
}

/* More Dropdown */
.more-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.5rem;
  min-width: 180px;
  background: var(--gray-950);
  border: 1px solid rgba(55, 65, 81, 0.6);
  border-radius: 10px;
  padding: 0.375rem;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 50;
}

.dropdown-link {
  display: block;
  padding: 0.5rem 0.875rem;
  font-size: 0.8rem;
  font-weight: 500;
  color: #9ca3af;
  border-radius: 8px;
  transition: all 0.2s;
}

.dropdown-link:hover {
  color: white;
  background: rgba(99, 102, 241, 0.1);
}

.dropdown-link-active {
  color: white;
  background: rgba(99, 102, 241, 0.15);
}

/* Flash Messages */
.flash-message {
  padding: 0.875rem 1rem;
  border-radius: 10px;
  border: 1px solid;
  max-width: 400px;
  font-family: 'Inter', sans-serif;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.flash-success {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
  color: #34d399;
}

.flash-error {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.flash-warning {
  background: rgba(245, 158, 11, 0.1);
  border-color: rgba(245, 158, 11, 0.3);
  color: #fbbf24;
}

.flash-info {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.3);
  color: #60a5fa;
}

.flash-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.flash-close {
  flex-shrink: 0;
  padding: 0.25rem;
  border-radius: 6px;
  color: currentColor;
  opacity: 0.6;
  transition: all 0.2s;
}

.flash-close:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.1);
}

/* Flash Transitions */
.flash-enter-active {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.flash-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 1, 1);
}

.flash-enter-from {
  opacity: 0;
  transform: translateX(80px);
}

.flash-leave-to {
  opacity: 0;
  transform: translateX(-80px);
}

/* Page Transitions */
.page-enter-active {
  transition: all 0.3s ease;
}

.page-leave-active {
  transition: all 0.2s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-leave-to {
  opacity: 0;
}
</style>
