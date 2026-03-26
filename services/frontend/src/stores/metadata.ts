import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { metadataApi, moviesApi } from '@/api'
import type { Movie, MovieMetadata, FfprobeData } from '@/api/types'
import { useAppStore } from './app'

export const useMetadataStore = defineStore('metadata', () => {
  // State
  const currentMovie = ref<Movie | null>(null)
  const movieMetadata = ref<MovieMetadata | null>(null)
  const ffprobeData = ref<FfprobeData | null>(null)
  const isLoading = ref(false)
  const selectedVersionIndex = ref(0)

  // Getters
  const hasMetadata = computed(() => movieMetadata.value !== null)
  const hasVersions = computed(() => {
    return movieMetadata.value?.versions && movieMetadata.value.versions.length > 1
  })
  const selectedVersion = computed(() => {
    if (!movieMetadata.value?.versions) return null
    return movieMetadata.value.versions[selectedVersionIndex.value]
  })
  const hasFfprobeData = computed(() => ffprobeData.value !== null)

  const videoStreams = computed(() => ffprobeData.value?.video_streams || [])
  const audioStreams = computed(() => ffprobeData.value?.audio_streams || [])
  const subtitleStreams = computed(() => ffprobeData.value?.subtitle_streams || [])

  const dolbyVisionInfo = computed(() => {
    if (!ffprobeData.value) return null

    for (const stream of videoStreams.value) {
      const dvSideData = stream.side_data_list?.find(
        (sd) => sd.side_data_type === 'DOVI configuration record'
      )
      if (dvSideData) {
        return {
          profile: stream.profile,
          hasDoVi: true,
        }
      }
    }

    return null
  })

  const hasAtmosAudio = computed(() => {
    if (!ffprobeData.value) return false
    return audioStreams.value.some(
      (stream) =>
        stream.codec_name === 'truehd' &&
        (stream.title?.toLowerCase().includes('atmos') || stream.codec_long_name?.toLowerCase().includes('atmos'))
    )
  })

  // Actions
  async function fetchMovieMetadata(movieId: number) {
    isLoading.value = true
    try {
      const response = await metadataApi.getMovieMetadata(movieId)

      // Map the API response to our Movie type
      currentMovie.value = {
        id: response.id,
        rating_key: response.rating_key,
        title: response.title,
        year: response.year,
        quality: response.quality || '',
        codec: response.codec,
        resolution: response.resolution,
        dv_profile: response.dv_profile,
        dv_fel: response.dv_fel,
        has_atmos: response.has_atmos,
        file_path: response.file_path,
        file_size: response.file_size,
        added_at: '',
        updated_at: '',
        extra_data: response.versions?.all_versions || {},
      }

      // Extract ffprobe data from metadata_cache if available
      if (response.metadata_cache?.ffprobe_data) {
        ffprobeData.value = response.metadata_cache.ffprobe_data
      } else if (response.metadata_cache?.video_streams || response.metadata_cache?.audio_streams) {
        // Construct ffprobe data from individual stream arrays
        ffprobeData.value = {
          format: {
            filename: response.file_path || '',
            format_name: response.file?.container || '',
            duration: '0',
            size: String(response.file_size || 0),
            bit_rate: '0',
          },
          video_streams: response.metadata_cache.video_streams || [],
          audio_streams: response.metadata_cache.audio_streams || [],
          subtitle_streams: response.metadata_cache.subtitle_streams || [],
        }
      } else {
        ffprobeData.value = null
      }

      selectedVersionIndex.value = 0
    } catch (error) {
      console.error('Failed to fetch movie metadata:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchMovie(movieId: number) {
    isLoading.value = true
    try {
      currentMovie.value = await moviesApi.getMovie(movieId)
    } catch (error) {
      console.error('Failed to fetch movie:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchFfprobeData(filePath: string) {
    const appStore = useAppStore()
    isLoading.value = true
    try {
      ffprobeData.value = await metadataApi.getFfprobeData(filePath)
      appStore.addFlashMessage('success', 'Metadata loaded successfully')
    } catch (error: any) {
      appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to load metadata')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function refreshMetadata(movieId: number) {
    const appStore = useAppStore()
    isLoading.value = true
    try {
      const response = await metadataApi.refreshMovieMetadata(movieId)
      appStore.addFlashMessage('success', response.message || 'Metadata refreshed')
      await fetchMovieMetadata(movieId)
    } catch (error: any) {
      appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to refresh metadata')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function clearMetadataCache() {
    const appStore = useAppStore()
    try {
      const response = await metadataApi.clearMetadataCache()
      appStore.addFlashMessage('success', response.message || 'Metadata cache cleared')
    } catch (error: any) {
      appStore.addFlashMessage('error', error.response?.data?.detail || 'Failed to clear cache')
    }
  }

  function selectVersion(index: number) {
    if (movieMetadata.value?.versions && index >= 0 && index < movieMetadata.value.versions.length) {
      selectedVersionIndex.value = index
    }
  }

  function reset() {
    currentMovie.value = null
    movieMetadata.value = null
    ffprobeData.value = null
    selectedVersionIndex.value = 0
  }

  return {
    // State
    currentMovie,
    movieMetadata,
    ffprobeData,
    isLoading,
    selectedVersionIndex,

    // Getters
    hasMetadata,
    hasVersions,
    selectedVersion,
    hasFfprobeData,
    videoStreams,
    audioStreams,
    subtitleStreams,
    dolbyVisionInfo,
    hasAtmosAudio,

    // Actions
    fetchMovieMetadata,
    fetchMovie,
    fetchFfprobeData,
    refreshMetadata,
    clearMetadataCache,
    selectVersion,
    reset,
  }
})
