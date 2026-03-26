import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { moviesApi } from '@/api'
import type { Movie, MovieFilters } from '@/api/types'

export const useMoviesStore = defineStore('movies', () => {
  // State
  const movies = ref<Movie[]>([])
  const total = ref(0)
  const page = ref(1)
  const perPage = ref(50)
  const totalPages = ref(0)
  const isLoading = ref(false)
  const filters = ref<MovieFilters>({
    search: '',
    dv_profile: undefined,
    dv_fel: undefined,
    has_atmos: undefined,
    resolution: undefined,
    sort_by: 'title',
    sort_order: 'asc',
  })
  const statistics = ref({
    total: 0,
    dv_total: 0,
    dv_p5: 0,
    dv_p7: 0,
    dv_p8: 0,
    dv_p10: 0,
    dv_fel: 0,
    atmos_total: 0,
    resolution_4k: 0,
    resolution_1080p: 0,
  })

  // Getters
  const hasMovies = computed(() => movies.value.length > 0)
  const hasFilters = computed(() => {
    return !!(
      filters.value.search ||
      filters.value.dv_profile ||
      filters.value.dv_fel !== undefined ||
      filters.value.has_atmos !== undefined ||
      filters.value.resolution
    )
  })

  // Actions
  async function fetchMovies() {
    isLoading.value = true
    try {
      const response = await moviesApi.getMovies({
        ...filters.value,
        page: page.value,
        per_page: perPage.value,
      })

      movies.value = response.movies
      total.value = response.total
      totalPages.value = response.total_pages
      page.value = response.page
      perPage.value = response.per_page
    } catch (error) {
      console.error('Failed to fetch movies:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchStatistics() {
    try {
      statistics.value = await moviesApi.getStatistics()
    } catch (error) {
      console.error('Failed to fetch statistics:', error)
    }
  }

  async function searchMovies(query: string) {
    filters.value.search = query
    page.value = 1
    await fetchMovies()
  }

  async function setFilter(key: keyof MovieFilters, value: any) {
    filters.value[key] = value as never
    page.value = 1
    await fetchMovies()
  }

  async function clearFilters() {
    filters.value = {
      search: '',
      dv_profile: undefined,
      dv_fel: undefined,
      has_atmos: undefined,
      resolution: undefined,
      sort_by: 'title',
      sort_order: 'asc',
    }
    page.value = 1
    await fetchMovies()
  }

  async function setPage(newPage: number) {
    page.value = newPage
    await fetchMovies()
  }

  async function setPerPage(newPerPage: number) {
    perPage.value = newPerPage
    page.value = 1
    await fetchMovies()
  }

  async function setSortBy(sortBy: string, sortOrder: 'asc' | 'desc' = 'asc') {
    filters.value.sort_by = sortBy
    filters.value.sort_order = sortOrder
    await fetchMovies()
  }

  function reset() {
    movies.value = []
    total.value = 0
    page.value = 1
    totalPages.value = 0
    filters.value = {
      search: '',
      dv_profile: undefined,
      dv_fel: undefined,
      has_atmos: undefined,
      resolution: undefined,
      sort_by: 'title',
      sort_order: 'asc',
    }
  }

  return {
    // State
    movies,
    total,
    page,
    perPage,
    totalPages,
    isLoading,
    filters,
    statistics,

    // Getters
    hasMovies,
    hasFilters,

    // Actions
    fetchMovies,
    fetchStatistics,
    searchMovies,
    setFilter,
    clearFilters,
    setPage,
    setPerPage,
    setSortBy,
    reset,
  }
})
