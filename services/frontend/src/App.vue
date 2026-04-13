<template>
  <div id="app" class="min-h-screen relative">
    <!-- Top gold filament -->
    <div class="filament" aria-hidden="true"></div>

    <!-- Header -->
    <header class="header">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center py-4">
          <!-- Logo & Status -->
          <div class="flex items-center space-x-6">
            <router-link to="/" class="flex items-center space-x-3 group">
              <div class="logo-mark">
                <svg class="w-[18px] h-[18px]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 7h16M4 12h10M4 17h16" />
                </svg>
              </div>
              <div class="leading-none">
                <div class="wordmark">FELScanner</div>
                <div class="wordmark-sub">dv · truehd · p7 fel</div>
              </div>
            </router-link>

            <!-- Status Indicator -->
            <div v-if="appStore.scanStatus" class="status-pill">
              <span class="status-dot" :class="statusIndicatorClass"></span>
              <span class="status-text">{{ appStore.scanStatus.state }}</span>
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
    return 'status-scanning'
  } else if (state === 'idle') {
    return 'status-idle'
  } else if (state === 'error') {
    return 'status-error'
  }
  return 'status-unknown'
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
/* Subtle accent top line */
.filament {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(77, 124, 255, 0.2) 40%,
    rgba(77, 124, 255, 0.5) 50%,
    rgba(77, 124, 255, 0.2) 60%,
    transparent 100%
  );
  z-index: 100;
  pointer-events: none;
}

/* Header */
.header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(12, 12, 14, 0.75);
  backdrop-filter: blur(20px) saturate(140%);
  -webkit-backdrop-filter: blur(20px) saturate(140%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

/* Logo — flat square mark, no gradient coin */
.logo-mark {
  width: 30px;
  height: 30px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: #4d7cff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    0 1px 2px rgba(0, 0, 0, 0.3);
  transition: transform 240ms cubic-bezier(0.16, 1, 0.3, 1);
}

.group:hover .logo-mark {
  transform: scale(1.04);
}

/* Wordmark — sans, tight tracking, weight-only hierarchy */
.wordmark {
  font-family: 'Geist', ui-sans-serif, sans-serif;
  font-weight: 600;
  font-size: 0.95rem;
  letter-spacing: -0.025em;
  color: #f4f4f5;
  line-height: 1;
}

.wordmark-sub {
  font-family: 'Geist Mono', 'JetBrains Mono', ui-monospace, monospace;
  font-size: 0.62rem;
  font-weight: 400;
  letter-spacing: 0;
  color: #71717a;
  margin-top: 3px;
  text-transform: none;
}

/* Status pill */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.status-pill .status-text {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.68rem;
  font-weight: 500;
  letter-spacing: 0;
  color: #a1a1aa;
  text-transform: none;
}

/* More Dropdown */
.more-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.5rem;
  min-width: 200px;
  background: rgba(12, 12, 14, 0.96);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 0.35rem;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 12px 40px rgba(0, 0, 0, 0.6);
  z-index: 50;
}

.dropdown-link {
  display: block;
  padding: 0.5rem 0.75rem;
  font-family: 'Geist', ui-sans-serif, sans-serif;
  font-size: 0.82rem;
  font-weight: 500;
  letter-spacing: -0.005em;
  color: #a1a1aa;
  border-radius: 6px;
  text-transform: none;
  transition: all 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

.dropdown-link:hover {
  color: #f4f4f5;
  background: rgba(255, 255, 255, 0.05);
}

.dropdown-link-active {
  color: #4d7cff;
  background: rgba(77, 124, 255, 0.1);
}

/* Flash Transitions */
.flash-enter-active {
  transition: all 0.44s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.flash-leave-active {
  transition: all 0.28s cubic-bezier(0.4, 0, 1, 1);
}

.flash-enter-from {
  opacity: 0;
  transform: translateX(80px) scale(0.92);
}

.flash-leave-to {
  opacity: 0;
  transform: translateX(-80px);
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
  opacity: 0.55;
  transition: all 0.2s;
}

.flash-close:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.08);
}

/* Page Transitions */
.page-enter-active {
  transition: all 0.36s cubic-bezier(0.4, 0, 0.2, 1);
}

.page-leave-active {
  transition: all 0.22s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(14px);
}

.page-leave-to {
  opacity: 0;
}
</style>
