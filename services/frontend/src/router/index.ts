import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
  },
  {
    path: '/quality',
    name: 'QualityReport',
    component: () => import('@/views/QualityReport.vue'),
  },
  {
    path: '/storage',
    name: 'StorageAnalytics',
    component: () => import('@/views/StorageAnalytics.vue'),
  },
  {
    path: '/insights',
    name: 'Insights',
    component: () => import('@/views/Insights.vue'),
  },
  {
    path: '/metadata',
    name: 'MetadataExplorer',
    component: () => import('@/views/MetadataExplorer.vue'),
  },
  {
    path: '/downloads',
    name: 'Downloads',
    component: () => import('@/views/Downloads.vue'),
  },
  {
    path: '/ipt',
    name: 'IPTScanner',
    component: () => import('@/views/IPTScanner.vue'),
  },
  {
    path: '/release-groups',
    name: 'ReleaseGroups',
    component: () => import('@/views/ReleaseGroups.vue'),
  },
  {
    path: '/activity',
    name: 'ActivityFeed',
    component: () => import('@/views/ActivityFeed.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
