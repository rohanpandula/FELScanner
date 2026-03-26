<template>
  <div class="metadata-explorer space-y-6">
    <!-- Search and Filters -->
    <div class="card">
      <div class="space-y-4">
        <!-- Search Input -->
        <div>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search movies by title..."
            class="input"
            @keyup.enter="handleSearch"
          />
        </div>

        <!-- Filters -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label class="label">DV Profile</label>
            <select v-model="filters.dv_profile" @change="applyFilters" class="input">
              <option :value="undefined">All</option>
              <option value="Profile 7">Profile 7</option>
              <option value="Profile 5">Profile 5</option>
              <option value="Profile 4">Profile 4</option>
            </select>
          </div>

          <div>
            <label class="label">FEL</label>
            <select v-model="filters.dv_fel" @change="applyFilters" class="input">
              <option :value="undefined">All</option>
              <option :value="true">Yes</option>
              <option :value="false">No</option>
            </select>
          </div>

          <div>
            <label class="label">Atmos</label>
            <select v-model="filters.has_atmos" @change="applyFilters" class="input">
              <option :value="undefined">All</option>
              <option :value="true">Yes</option>
              <option :value="false">No</option>
            </select>
          </div>

          <div>
            <label class="label">Resolution</label>
            <select v-model="filters.resolution" @change="applyFilters" class="input">
              <option :value="undefined">All</option>
              <option value="4K">4K</option>
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
            </select>
          </div>
        </div>

        <div class="flex justify-between items-center">
          <button
            v-if="moviesStore.hasFilters"
            @click="clearFilters"
            class="btn btn-secondary"
          >
            Clear Filters
          </button>
          <div class="text-sm text-gray-600">
            Showing {{ moviesStore.movies.length }} of {{ moviesStore.total }} movies
          </div>
        </div>
      </div>
    </div>

    <!-- Movies Table -->
    <div v-if="moviesStore.isLoading" class="text-center py-12">
      <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      <p class="mt-4 text-gray-600">Loading movies...</p>
    </div>

    <div v-else-if="!moviesStore.hasMovies" class="card text-center py-12">
      <p class="text-gray-600">No movies found</p>
    </div>

    <div v-else class="card overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-700">
        <thead style="background: rgba(31, 41, 55, 0.6);">
          <tr>
            <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #818cf8;">Title</th>
            <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #818cf8;">Year</th>
            <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #818cf8;">DV Profile</th>
            <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #818cf8;">FEL</th>
            <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #818cf8;">Atmos</th>
            <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #818cf8;">Resolution</th>
            <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #818cf8;">Codec</th>
            <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider" style="color: #818cf8;">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-700" style="background: rgba(20, 20, 30, 0.4);">
          <tr
            v-for="movie in moviesStore.movies"
            :key="movie.id"
            class="hover:bg-[rgba(45,45,61,0.4)] transition-colors cursor-pointer"
          >
            <td class="px-6 py-4 whitespace-nowrap" @click="openMovieDetails(movie.id)">
              <div class="text-sm font-medium" style="color: #e5e5e5;">{{ movie.title }}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap" @click="openMovieDetails(movie.id)">
              <div class="text-sm" style="color: #9ca3af;">{{ movie.year || '-' }}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap" @click="openMovieDetails(movie.id)">
              <span v-if="movie.dv_profile" class="inline-flex px-3 py-1 text-xs font-semibold rounded-full" style="background: rgba(124, 58, 237, 0.2); color: #a78bfa;">
                {{ movie.dv_profile }}
              </span>
              <span v-else class="text-sm" style="color: #9ca3af;">-</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap" @click="openMovieDetails(movie.id)">
              <span v-if="movie.dv_fel" class="inline-flex px-3 py-1 text-xs font-semibold rounded-full" style="background: rgba(99, 102, 241, 0.2); color: #818cf8;">
                FEL
              </span>
              <span v-else class="text-sm" style="color: #9ca3af;">-</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap" @click="openMovieDetails(movie.id)">
              <span v-if="movie.has_atmos" class="inline-flex px-3 py-1 text-xs font-semibold rounded-full" style="background: rgba(16, 185, 129, 0.2); color: #10b981;">
                Atmos
              </span>
              <span v-else class="text-sm" style="color: #9ca3af;">-</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap" @click="openMovieDetails(movie.id)">
              <div class="text-sm" style="color: #9ca3af;">{{ movie.resolution || '-' }}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap" @click="openMovieDetails(movie.id)">
              <div class="text-sm" style="color: #9ca3af;">{{ movie.video_codec || '-' }}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <button
                @click="openMovieDetails(movie.id)"
                class="text-xs px-3 py-1.5 rounded font-semibold transition-all"
                style="background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3);"
                @mouseover="$event.target.style.background = 'rgba(99, 102, 241, 0.25)'"
                @mouseout="$event.target.style.background = 'rgba(99, 102, 241, 0.15)'"
              >
                Details
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="moviesStore.totalPages > 1" class="card">
      <div class="flex items-center justify-between">
        <button
          @click="previousPage"
          :disabled="moviesStore.page === 1"
          class="btn btn-secondary"
        >
          Previous
        </button>

        <div class="flex items-center space-x-2">
          <span class="text-sm text-gray-600">
            Page {{ moviesStore.page }} of {{ moviesStore.totalPages }}
          </span>
        </div>

        <button
          @click="nextPage"
          :disabled="moviesStore.page >= moviesStore.totalPages"
          class="btn btn-secondary"
        >
          Next
        </button>
      </div>
    </div>

    <!-- Movie Details Modal -->
    <teleport to="body">
      <div
        v-if="showDetailsModal"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
        @click="closeModal"
      >
        <div
          class="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
          @click.stop
        >
          <div class="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
            <h2 class="text-2xl font-bold">{{ metadataStore.currentMovie?.title }}</h2>
            <button @click="closeModal" class="text-gray-500 hover:text-gray-700 text-2xl">
              ×
            </button>
          </div>

          <div v-if="metadataStore.isLoading" class="p-6 text-center">
            <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          </div>

          <div v-else-if="metadataStore.currentMovie" class="p-6 space-y-6">
            <!-- High-Signal Media Information Table -->
            <div>
              <h3 class="text-lg font-semibold mb-3">Media Information</h3>

              <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                  <tbody class="bg-white divide-y divide-gray-200">
                    <!-- HDR Information -->
                    <tr>
                      <td class="px-4 py-3 text-sm font-medium text-gray-900 w-48">HDR Format</td>
                      <td class="px-4 py-3 text-sm text-gray-700">
                        <span v-if="metadataStore.currentMovie.dv_profile" class="font-medium text-purple-700">
                          Dolby Vision {{ metadataStore.currentMovie.dv_profile }}
                          <span v-if="metadataStore.currentMovie.dv_fel" class="ml-2 text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded">FEL</span>
                        </span>
                        <span v-else-if="hasHDR" class="font-medium text-blue-700">
                          {{ getHDRType() }}
                        </span>
                        <span v-else class="text-gray-500">SDR</span>
                      </td>
                    </tr>

                    <!-- Atmos Information -->
                    <tr>
                      <td class="px-4 py-3 text-sm font-medium text-gray-900">Atmos Audio</td>
                      <td class="px-4 py-3 text-sm text-gray-700">
                        <span v-if="metadataStore.currentMovie.has_atmos">
                          <span class="font-medium text-green-700">{{ getAtmosType() }}</span>
                        </span>
                        <span v-else class="text-gray-500">No</span>
                      </td>
                    </tr>

                    <!-- Audio Tracks -->
                    <tr>
                      <td class="px-4 py-3 text-sm font-medium text-gray-900 align-top">Audio Tracks</td>
                      <td class="px-4 py-3 text-sm text-gray-700">
                        <div v-if="metadataStore.audioStreams.length > 0" class="space-y-2">
                          <div v-for="(stream, index) in metadataStore.audioStreams" :key="index" class="flex items-start">
                            <span class="inline-block w-6 text-gray-400 flex-shrink-0">{{ index + 1 }}.</span>
                            <span class="flex-1">
                              <span class="font-medium">{{ formatAudioCodec(stream) }}</span>
                              <span class="text-gray-600 ml-2">{{ formatChannelLayout(stream) }}</span>
                              <span v-if="stream.language" class="text-gray-500 ml-2">({{ stream.language }})</span>
                            </span>
                          </div>
                        </div>
                        <span v-else class="text-gray-500">No audio tracks detected</span>
                      </td>
                    </tr>

                    <!-- Video Information -->
                    <tr>
                      <td class="px-4 py-3 text-sm font-medium text-gray-900">Video</td>
                      <td class="px-4 py-3 text-sm text-gray-700">
                        <span v-if="metadataStore.videoStreams.length > 0">
                          {{ metadataStore.currentMovie.codec }} |
                          {{ metadataStore.currentMovie.resolution }} |
                          {{ metadataStore.videoStreams[0].width }}x{{ metadataStore.videoStreams[0].height }}
                          <span v-if="metadataStore.videoStreams[0].frame_rate"> | {{ metadataStore.videoStreams[0].frame_rate }} fps</span>
                        </span>
                        <span v-else>
                          {{ metadataStore.currentMovie.codec }} | {{ metadataStore.currentMovie.resolution }}
                        </span>
                      </td>
                    </tr>

                    <!-- Quality/Source -->
                    <tr>
                      <td class="px-4 py-3 text-sm font-medium text-gray-900">Quality</td>
                      <td class="px-4 py-3 text-sm text-gray-700">
                        {{ metadataStore.currentMovie.quality }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- File Path -->
            <div>
              <h3 class="text-lg font-semibold mb-2">File Path</h3>
              <p class="text-sm text-gray-700 font-mono bg-gray-50 p-3 rounded break-all">
                {{ metadataStore.currentMovie.file_path }}
              </p>
            </div>

            <div class="flex justify-end space-x-3">
              <button @click="refreshMetadata" class="btn btn-secondary">
                Refresh Metadata
              </button>
              <button @click="closeModal" class="btn btn-primary">
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useMoviesStore } from '@/stores/movies'
import { useMetadataStore } from '@/stores/metadata'
import type { AudioStream } from '@/api/types'

const moviesStore = useMoviesStore()
const metadataStore = useMetadataStore()

const searchQuery = ref('')
const filters = ref({
  dv_profile: undefined as string | undefined,
  dv_fel: undefined as boolean | undefined,
  has_atmos: undefined as boolean | undefined,
  resolution: undefined as string | undefined,
})
const showDetailsModal = ref(false)

// Computed properties for HDR detection
const hasHDR = computed(() => {
  if (!metadataStore.videoStreams.length) return false
  const stream = metadataStore.videoStreams[0]
  // Check for HDR indicators in color transfer
  return stream.color_transfer === 'smpte2084' || stream.color_transfer === 'arib-std-b67'
})

// Helper functions for formatting
function getHDRType(): string {
  if (!metadataStore.videoStreams.length) return 'Unknown'
  const stream = metadataStore.videoStreams[0]

  // Check for HDR10+ (would be in side_data_list)
  const hasHDR10Plus = stream.side_data_list?.some(
    sd => sd.side_data_type === 'HDR10+' || sd.side_data_type === 'HDR Dynamic Metadata SMPTE2094-40'
  )

  if (hasHDR10Plus) return 'HDR10+'

  // Check for HDR10
  if (stream.color_transfer === 'smpte2084') return 'HDR10'

  // Check for HLG
  if (stream.color_transfer === 'arib-std-b67') return 'HLG'

  return 'HDR'
}

function getAtmosType(): string {
  const atmosStream = metadataStore.audioStreams.find(stream =>
    stream.codec_name === 'truehd' &&
    (stream.title?.toLowerCase().includes('atmos') || stream.codec_long_name?.toLowerCase().includes('atmos'))
  )

  if (atmosStream) {
    return 'TrueHD Atmos'
  }

  // Check for DD+ Atmos (EAC3)
  const ddPlusAtmos = metadataStore.audioStreams.find(stream =>
    stream.codec_name === 'eac3' &&
    (stream.title?.toLowerCase().includes('atmos') || stream.codec_long_name?.toLowerCase().includes('atmos'))
  )

  if (ddPlusAtmos) {
    return 'DD+ Atmos'
  }

  return 'Atmos'
}

function formatAudioCodec(stream: AudioStream): string {
  // Format codec name to be more readable
  const codecMap: Record<string, string> = {
    'truehd': 'TrueHD',
    'dts': 'DTS',
    'ac3': 'AC-3',
    'eac3': 'DD+',
    'aac': 'AAC',
    'flac': 'FLAC',
    'pcm_s16le': 'PCM',
    'pcm_s24le': 'PCM 24-bit',
  }

  let codecName = codecMap[stream.codec_name] || stream.codec_name.toUpperCase()

  // Add Atmos indicator if present
  if (stream.title?.toLowerCase().includes('atmos') || stream.codec_long_name?.toLowerCase().includes('atmos')) {
    codecName += ' Atmos'
  }

  return codecName
}

function formatChannelLayout(stream: AudioStream): string {
  // Map channel counts to common names
  const channelMap: Record<number, string> = {
    1: 'Mono',
    2: 'Stereo',
    6: '5.1',
    8: '7.1',
  }

  // Use channel_layout if available, otherwise use channel count
  if (stream.channel_layout) {
    return stream.channel_layout
  }

  return channelMap[stream.channels] || `${stream.channels} channels`
}

onMounted(async () => {
  await moviesStore.fetchMovies()
})

async function handleSearch() {
  await moviesStore.searchMovies(searchQuery.value)
}

async function applyFilters() {
  for (const [key, value] of Object.entries(filters.value)) {
    await moviesStore.setFilter(key as any, value)
  }
}

async function clearFilters() {
  filters.value = {
    dv_profile: undefined,
    dv_fel: undefined,
    has_atmos: undefined,
    resolution: undefined,
  }
  searchQuery.value = ''
  await moviesStore.clearFilters()
}

async function previousPage() {
  if (moviesStore.page > 1) {
    await moviesStore.setPage(moviesStore.page - 1)
  }
}

async function nextPage() {
  if (moviesStore.page < moviesStore.totalPages) {
    await moviesStore.setPage(moviesStore.page + 1)
  }
}

async function openMovieDetails(movieId: number) {
  showDetailsModal.value = true
  await metadataStore.fetchMovieMetadata(movieId)
}

function closeModal() {
  showDetailsModal.value = false
  metadataStore.reset()
}

async function refreshMetadata() {
  if (metadataStore.currentMovie) {
    await metadataStore.refreshMetadata(metadataStore.currentMovie.id)
  }
}
</script>
