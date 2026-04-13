<template>
  <div class="metadata-explorer space-y-7 anim-fade-up">
    <!-- Header -->
    <header class="flex items-end justify-between flex-wrap gap-4">
      <div>
        <div class="eyebrow mb-2">Library Index</div>
        <h1 class="section-title">Metadata</h1>
        <p class="section-sub mt-1">Every Dolby Vision track, every audio layer, every frame accounted for.</p>
      </div>
      <div class="count-chip">
        <span class="tabular-nums">{{ moviesStore.movies.length }}</span>
        <span class="divider-slash">/</span>
        <span class="tabular-nums">{{ moviesStore.total }}</span>
        <span class="muted ml-1">movies</span>
      </div>
    </header>

    <!-- Search and Filters -->
    <div class="card">
      <div class="search-row">
        <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
          <circle cx="11" cy="11" r="7" />
          <path stroke-linecap="round" d="m20 20-3-3" />
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search by title"
          class="search-input"
          @keyup.enter="handleSearch"
        />
        <button
          v-if="moviesStore.hasFilters"
          @click="clearFilters"
          class="btn btn-ghost btn-sm"
        >
          Clear filters
        </button>
      </div>

      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5">
        <div>
          <label class="label">DV profile</label>
          <select v-model="filters.dv_profile" @change="applyFilters" class="select">
            <option :value="undefined">All</option>
            <option value="Profile 7">Profile 7</option>
            <option value="Profile 5">Profile 5</option>
            <option value="Profile 4">Profile 4</option>
          </select>
        </div>
        <div>
          <label class="label">FEL</label>
          <select v-model="filters.dv_fel" @change="applyFilters" class="select">
            <option :value="undefined">All</option>
            <option :value="true">Yes</option>
            <option :value="false">No</option>
          </select>
        </div>
        <div>
          <label class="label">Atmos</label>
          <select v-model="filters.has_atmos" @change="applyFilters" class="select">
            <option :value="undefined">All</option>
            <option :value="true">Yes</option>
            <option :value="false">No</option>
          </select>
        </div>
        <div>
          <label class="label">Resolution</label>
          <select v-model="filters.resolution" @change="applyFilters" class="select">
            <option :value="undefined">All</option>
            <option value="4K">4K</option>
            <option value="1080p">1080p</option>
            <option value="720p">720p</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Movies Table -->
    <div v-if="moviesStore.isLoading" class="card text-center py-14">
      <div class="spinner mx-auto"></div>
      <p class="mt-4 muted">Loading movies…</p>
    </div>

    <div v-else-if="!moviesStore.hasMovies" class="card text-center py-16">
      <p class="muted">No movies match those filters.</p>
    </div>

    <div v-else class="card p-0 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Year</th>
              <th>DV</th>
              <th>FEL</th>
              <th>Atmos</th>
              <th>Res</th>
              <th>Codec</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="movie in moviesStore.movies"
              :key="movie.id"
              class="cursor-pointer"
              @click="openMovieDetails(movie.id)"
            >
              <td class="font-medium">{{ movie.title }}</td>
              <td class="muted tabular-nums">{{ movie.year || '—' }}</td>
              <td>
                <span v-if="movie.dv_profile" class="badge badge-p7">
                  {{ movie.dv_profile }}
                </span>
                <span v-else class="muted">—</span>
              </td>
              <td>
                <span v-if="movie.dv_fel" class="badge badge-fel">FEL</span>
                <span v-else class="muted">—</span>
              </td>
              <td>
                <span v-if="movie.has_atmos" class="badge badge-atmos">Atmos</span>
                <span v-else class="muted">—</span>
              </td>
              <td class="muted">{{ movie.resolution || '—' }}</td>
              <td class="muted font-mono text-xs">{{ movie.video_codec || '—' }}</td>
              <td>
                <button class="btn btn-ghost btn-sm" @click.stop="openMovieDetails(movie.id)">
                  Details →
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="moviesStore.totalPages > 1" class="flex items-center justify-between">
      <button
        @click="previousPage"
        :disabled="moviesStore.page === 1"
        class="btn btn-secondary"
      >
        ← Previous
      </button>

      <span class="eyebrow">
        Page {{ moviesStore.page }} / {{ moviesStore.totalPages }}
      </span>

      <button
        @click="nextPage"
        :disabled="moviesStore.page >= moviesStore.totalPages"
        class="btn btn-secondary"
      >
        Next →
      </button>
    </div>

    <!-- Movie Details Modal -->
    <teleport to="body">
      <transition name="overlay">
        <div
          v-if="showDetailsModal"
          class="overlay"
          @click="closeModal"
        >
          <transition name="modal" appear>
            <div v-if="showDetailsModal" class="modal-shell" @click.stop>
              <header class="modal-header">
                <div>
                  <div class="eyebrow">Media File</div>
                  <h2 class="display text-xl mt-1 truncate">
                    {{ metadataStore.currentMovie?.title }}
                  </h2>
                </div>
                <button @click="closeModal" class="icon-btn" aria-label="Close">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" class="w-5 h-5">
                    <path stroke-linecap="round" d="M6 6l12 12M18 6l-12 12" />
                  </svg>
                </button>
              </header>

              <div v-if="metadataStore.isLoading" class="modal-body text-center py-14">
                <div class="spinner mx-auto"></div>
              </div>

              <div v-else-if="metadataStore.currentMovie" class="modal-body space-y-7">
                <section>
                  <div class="eyebrow mb-3">Media signatures</div>
                  <dl class="info-grid">
                    <div>
                      <dt>HDR format</dt>
                      <dd>
                        <template v-if="metadataStore.currentMovie.dv_profile">
                          <span class="badge badge-p7">
                            Dolby Vision {{ metadataStore.currentMovie.dv_profile }}
                          </span>
                          <span v-if="metadataStore.currentMovie.dv_fel" class="badge badge-fel ml-2">FEL</span>
                        </template>
                        <span v-else-if="hasHDR" class="badge badge-hdr">{{ getHDRType() }}</span>
                        <span v-else class="muted">SDR</span>
                      </dd>
                    </div>

                    <div>
                      <dt>Atmos audio</dt>
                      <dd>
                        <span v-if="metadataStore.currentMovie.has_atmos" class="badge badge-atmos">
                          {{ getAtmosType() }}
                        </span>
                        <span v-else class="muted">No</span>
                      </dd>
                    </div>

                    <div>
                      <dt>Video</dt>
                      <dd class="tabular-nums">
                        <template v-if="metadataStore.videoStreams.length > 0">
                          {{ metadataStore.currentMovie.codec }}
                          <span class="pipe">·</span>
                          {{ metadataStore.currentMovie.resolution }}
                          <span class="pipe">·</span>
                          {{ metadataStore.videoStreams[0].width }}×{{ metadataStore.videoStreams[0].height }}
                          <template v-if="metadataStore.videoStreams[0].frame_rate">
                            <span class="pipe">·</span>{{ metadataStore.videoStreams[0].frame_rate }} fps
                          </template>
                        </template>
                        <template v-else>
                          {{ metadataStore.currentMovie.codec }}
                          <span class="pipe">·</span>
                          {{ metadataStore.currentMovie.resolution }}
                        </template>
                      </dd>
                    </div>

                    <div>
                      <dt>Quality</dt>
                      <dd>{{ metadataStore.currentMovie.quality }}</dd>
                    </div>
                  </dl>
                </section>

                <section>
                  <div class="eyebrow mb-3">Audio tracks</div>
                  <ol v-if="metadataStore.audioStreams.length > 0" class="track-list">
                    <li v-for="(stream, index) in metadataStore.audioStreams" :key="index">
                      <span class="track-idx">{{ String(index + 1).padStart(2, '0') }}</span>
                      <span class="track-codec">{{ formatAudioCodec(stream) }}</span>
                      <span class="track-layout">{{ formatChannelLayout(stream) }}</span>
                      <span v-if="stream.language" class="track-lang">{{ stream.language }}</span>
                    </li>
                  </ol>
                  <p v-else class="muted">No audio tracks detected.</p>
                </section>

                <section>
                  <div class="eyebrow mb-3">File path</div>
                  <p class="file-path">{{ metadataStore.currentMovie.file_path }}</p>
                </section>
              </div>

              <footer class="modal-footer">
                <button @click="refreshMetadata" class="btn btn-secondary">Refresh metadata</button>
                <button @click="closeModal" class="btn btn-primary">Close</button>
              </footer>
            </div>
          </transition>
        </div>
      </transition>
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

<style scoped>
.count-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.95rem;
  font-family: 'Geist', ui-sans-serif, sans-serif;
  font-size: 0.78rem;
  letter-spacing: 0.1em;
  background: rgba(10, 10, 15, 0.55);
  border: 1px solid rgba(212, 175, 55, 0.2);
  border-radius: 999px;
  color: var(--cinema-white);
}
.divider-slash { color: rgba(212, 175, 55, 0.5); margin: 0 0.1rem; }

.search-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.search-icon {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
  width: 18px;
  height: 18px;
  color: var(--cinema-gold);
  pointer-events: none;
  opacity: 0.75;
}
.search-input {
  flex: 1;
  padding: 0.85rem 1rem 0.85rem 2.8rem;
  font-size: 0.95rem;
  font-family: 'Geist', ui-sans-serif, sans-serif;
  background: rgba(10, 10, 15, 0.6);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(107, 107, 127, 0.2);
  border-radius: 12px;
  color: var(--cinema-white);
  transition: border-color 220ms, box-shadow 220ms;
}
.search-input:focus {
  outline: none;
  border-color: rgba(212, 175, 55, 0.55);
  box-shadow: 0 0 0 3px rgba(212, 175, 55, 0.14),
    0 0 24px rgba(212, 175, 55, 0.12);
}
.search-input::placeholder { color: rgba(107, 107, 127, 0.7); }

/* Overlay + modal (mirror SettingsModal) */
.overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 80;
  background:
    radial-gradient(ellipse 60% 50% at 50% 30%, rgba(124, 58, 237, 0.22), transparent 70%),
    rgba(4, 4, 9, 0.72);
  backdrop-filter: blur(10px);
}
.modal-shell {
  width: 100%;
  max-width: 56rem;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(rgba(26, 26, 36, 0.94), rgba(26, 26, 36, 0.94)),
    radial-gradient(ellipse 80% 40% at 50% 0%, rgba(212, 175, 55, 0.18), transparent 70%);
  border: 1px solid rgba(212, 175, 55, 0.22);
  border-radius: 18px;
  box-shadow: 0 32px 80px rgba(0, 0, 0, 0.7),
    0 0 0 1px rgba(212, 175, 55, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.3rem 1.75rem 1.1rem;
  border-bottom: 1px solid rgba(107, 107, 127, 0.15);
  background: rgba(10, 10, 15, 0.5);
  gap: 1rem;
}
.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  color: var(--cinema-gray);
  border-radius: 8px;
  flex-shrink: 0;
  transition: all 220ms var(--ease-standard);
}
.icon-btn:hover { color: var(--cinema-gold); background: rgba(212, 175, 55, 0.08); }
.modal-body { padding: 1.75rem; overflow-y: auto; flex: 1; }
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  padding: 1.1rem 1.75rem;
  border-top: 1px solid rgba(107, 107, 127, 0.15);
  background: rgba(10, 10, 15, 0.5);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.2rem 2rem;
}
.info-grid dt {
  font-family: 'Geist', ui-sans-serif, sans-serif;
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--cinema-gold);
  margin-bottom: 0.5rem;
}
.info-grid dd {
  font-size: 0.92rem;
  color: var(--cinema-white);
  font-family: 'Geist', ui-sans-serif, sans-serif;
}
.pipe { color: rgba(212, 175, 55, 0.45); margin: 0 0.35rem; }

.track-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.track-list li {
  display: grid;
  grid-template-columns: 2.2rem 1fr auto auto;
  align-items: center;
  gap: 0.85rem;
  padding: 0.55rem 0.85rem;
  background: rgba(10, 10, 15, 0.4);
  border: 1px solid rgba(107, 107, 127, 0.14);
  border-radius: 10px;
  font-size: 0.86rem;
}
.track-idx {
  font-family: 'Geist Mono', ui-monospace, monospace;
  color: var(--cinema-gold);
  font-size: 0.72rem;
}
.track-codec {
  font-weight: 600;
  color: var(--cinema-white);
}
.track-layout { color: rgba(236, 236, 240, 0.75); font-size: 0.8rem; }
.track-lang {
  font-family: 'Geist', ui-sans-serif, sans-serif;
  font-size: 0.62rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--cinema-gray);
  background: rgba(45, 45, 61, 0.5);
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
}

.file-path {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.78rem;
  color: rgba(236, 236, 240, 0.85);
  padding: 0.95rem 1.1rem;
  background: rgba(10, 10, 15, 0.55);
  border: 1px solid rgba(107, 107, 127, 0.18);
  border-radius: 10px;
  word-break: break-all;
  line-height: 1.55;
}

.spinner {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 2px solid rgba(212, 175, 55, 0.18);
  border-top-color: var(--cinema-gold);
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.overlay-enter-active, .overlay-leave-active { transition: opacity 220ms var(--ease-standard); }
.overlay-enter-from, .overlay-leave-to { opacity: 0; }
.modal-enter-active { transition: all 340ms var(--ease-spring); }
.modal-leave-active { transition: all 200ms var(--ease-standard); }
.modal-enter-from, .modal-leave-to { opacity: 0; transform: translateY(14px) scale(0.97); }
</style>
