// Scan Status
export interface ScanStatus {
  state: 'idle' | 'scanning' | 'verifying' | 'error'
  progress: number
  current_movie: string | null
  total_movies: number
  scanned_count: number
  message: string | null
  start_time: string | null
  elapsed_time: number
}

// Connection Status
export interface ConnectionStatus {
  plex: ServiceStatus
  qbittorrent: ServiceStatus
  radarr: ServiceStatus
  telegram: ServiceStatus
  flaresolverr: ServiceStatus
  ipt_scraper: ServiceStatus
}

export interface ServiceStatus {
  connected: boolean
  message: string | null
  last_check: string | null
}

// Movie
export interface Movie {
  id: number
  rating_key: string
  title: string
  year: number | null
  quality: string
  codec: string | null
  resolution: string | null
  dv_profile: string | null
  dv_fel: boolean
  has_atmos: boolean
  file_path: string
  file_size: number | null
  added_at: string
  updated_at: string
  extra_data: Record<string, any>
}

export interface MovieListResponse {
  movies: Movie[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export interface MovieFilters {
  search?: string
  dv_profile?: string
  dv_fel?: boolean
  has_atmos?: boolean
  resolution?: string
  page?: number
  per_page?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

// Metadata
export interface MovieMetadata {
  movie: Movie
  versions: MovieVersion[]
  ffprobe_data: FfprobeData | null
}

export interface MovieVersion {
  id: number
  file_path: string
  file_size: number
  quality: string
  codec: string | null
  resolution: string | null
  dv_profile: string | null
  dv_fel: boolean
  has_atmos: boolean
  is_primary: boolean
}

export interface FfprobeData {
  format: {
    filename: string
    format_name: string
    duration: string
    size: string
    bit_rate: string
  }
  video_streams: VideoStream[]
  audio_streams: AudioStream[]
  subtitle_streams: SubtitleStream[]
}

export interface VideoStream {
  index: number
  codec_name: string
  codec_long_name: string
  profile: string | null
  width: number
  height: number
  bit_rate: string | null
  frame_rate: string | null
  color_space: string | null
  color_transfer: string | null
  color_primaries: string | null
  side_data_list: SideData[]
}

export interface AudioStream {
  index: number
  codec_name: string
  codec_long_name: string
  channels: number
  channel_layout: string | null
  sample_rate: string
  bit_rate: string | null
  language: string | null
  title: string | null
}

export interface SubtitleStream {
  index: number
  codec_name: string
  language: string | null
  title: string | null
  forced: boolean
}

export interface SideData {
  side_data_type: string
}

// Downloads
export interface PendingDownload {
  id: number
  movie_title: string
  movie_year: number | null
  torrent_name: string
  torrent_url: string
  quality: string
  upgrade_type: string | null
  size_mb: number | null
  seeders: number | null
  status: 'pending' | 'approved' | 'declined' | 'expired'
  created_at: string
  expires_at: string
  telegram_message_id: number | null
}

export interface ActiveTorrent {
  hash: string
  name: string
  state: string
  progress: number
  download_speed: number
  upload_speed: number
  eta: number
  size: number
  downloaded: number
  uploaded: number
  category: string
  added_on: number
}

export interface DownloadHistory {
  id: number
  movie_title: string
  movie_year: number | null
  torrent_name: string
  quality: string
  upgrade_type: string | null
  size_mb: number | null
  action: 'approved' | 'declined' | 'expired'
  actioned_at: string
}

// IPT Scanner
export interface TorrentMetadata {
  clean_title: string | null
  year: number | null
  resolution: string | null
  source: string | null
  dv_profile: string | null
  has_dv: boolean
  has_fel: boolean
  hdr_type: string | null
  has_atmos: boolean
  audio_codec: string | null
  audio_channels: string | null
  video_codec: string | null
  bit_depth: number | null
  release_type: string | null
  release_group: string | null
  languages: string[]
  quality_score: number | null
}

export interface IPTTorrent {
  title: string
  url: string
  size: string
  seeders: number
  leechers: number
  upload_date: string
  category: string
  quality: string
  isNew: boolean
  metadata?: TorrentMetadata
}

export interface IPTScanResult {
  total: number
  new: number
  torrents: IPTTorrent[]
}

// Settings
export interface Settings {
  // Plex
  plex_url: string
  plex_token: string
  plex_library_name: string

  // Collections
  collection_dv_p7: string
  collection_dv_fel: string
  collection_atmos: string

  // qBittorrent
  qbittorrent_url: string
  qbittorrent_username: string
  qbittorrent_password: string

  // Radarr
  radarr_url: string
  radarr_api_key: string

  // Telegram
  telegram_enabled: boolean
  telegram_bot_token: string
  telegram_chat_id: string

  // IPT
  ipt_enabled: boolean
  ipt_url: string
  ipt_uid: string
  ipt_pass: string

  // Scan Settings
  scan_schedule_enabled: boolean
  scan_schedule_hours: number[]
  auto_start_mode: 'disabled' | 'scan' | 'monitor'

  // Monitor Settings
  monitor_enabled: boolean
  monitor_interval_minutes: number

  // Notification Rules
  notify_fel: boolean
  notify_fel_from_p5: boolean
  notify_fel_from_hdr: boolean
  notify_fel_duplicates: boolean
  notify_p5: boolean
  notify_p5_from_hdr: boolean
  notify_p5_duplicates: boolean
  notify_dv_any: boolean
  notify_dv_upgrades: boolean
  notify_hdr_from_sdr: boolean
  notify_atmos_any: boolean
  notify_atmos_to_dv: boolean
  notify_resolution_upgrade: boolean
  notify_4k_any: boolean
  notify_1080p_from_lower: boolean

  // Download Settings
  download_approval_expires_hours: number
  download_category_fel: string
  download_category_dv: string
  download_category_hdr: string
}

// Collections
export interface Collection {
  name: string
  rating_key: string
  movie_count: number
}

export interface CollectionMovies {
  collection_name: string
  movies: Movie[]
  total: number
}

// API Response
export interface ApiResponse<T> {
  data: T
  message?: string
}

export interface ApiError {
  detail: string
}

// ============================================================================
// Analytics Types (Features 1, 2, 4, 5, 7)
// ============================================================================

// Feature 1: Quality Report / Library Health
export interface QualityReport {
  health_score: number
  total_movies: number
  quality_tiers: {
    reference: number
    excellent: number
    great: number
    good: number
    acceptable: number
    needs_upgrade: number
  }
  hdr_distribution: Record<string, number>
  audio_distribution: Record<string, number>
  resolution_distribution: Record<string, number>
  profile_breakdown: Record<string, number>
  quality_summary: {
    dv_percentage: number
    fel_percentage: number
    atmos_percentage: number
    fourk_percentage: number
    dv_count: number
    fel_count: number
    atmos_count: number
    fourk_count: number
  }
}

// Feature 2: Upgrade Opportunities
export interface UpgradeOpportunity {
  id: number
  title: string
  year: number | null
  current_quality: string
  quality_score: number
  resolution: string | null
  dv_profile: string | null
  dv_fel: boolean
  has_atmos: boolean
  hdr_type: string | null
  possible_upgrades: string[]
  upgrade_priority: number
}

// Feature 4: Duplicate Management
export interface DuplicateGroup {
  id?: number
  title: string
  year: number | null
  version_count: number
  primary_quality?: string
  quality_score?: number
  file_size_bytes?: number
  total_size_bytes?: number
  best_quality_score?: number
  versions: DuplicateVersion[]
  type: 'multi_version' | 'duplicate_entries'
}

export interface DuplicateVersion {
  id?: number
  quality?: string
  quality_score?: number
  resolution?: string | null
  dv_profile?: string | null
  dv_fel?: boolean
  has_atmos?: boolean
  file_size_bytes?: number
  file_path?: string | null
  is_primary?: boolean
}

// Feature 5: Storage Analytics
export interface StorageAnalytics {
  total_bytes: number
  total_movies: number
  avg_file_size_bytes: number
  by_resolution: StorageBreakdown[]
  by_dv_status: StorageBreakdown[]
  by_audio: StorageBreakdown[]
  by_codec: StorageBreakdown[]
  largest_movies: StorageMovie[]
  smallest_dv_movies: StorageMovie[]
}

export interface StorageBreakdown {
  resolution?: string
  category?: string
  audio?: string
  codec?: string
  count: number
  total_bytes: number
  avg_bytes?: number
}

export interface StorageMovie {
  id: number
  title: string
  year: number | null
  quality: string
  file_size_bytes: number
  resolution?: string | null
  dv_profile?: string | null
}

// Feature 7: Comparison View
export interface ComparisonResult {
  movie: {
    id: number
    title: string
    year: number | null
    resolution: string | null
    dv_profile: string | null
    dv_fel: boolean
    has_atmos: boolean
    audio_codec: string | null
    audio_channels: string | null
    video_codec: string | null
    hdr_type: string | null
    file_size_bytes: number | null
    quality_score: number
    display_quality: string
  }
  torrent: {
    resolution: string | null
    dv_profile: string | null
    has_fel: boolean
    has_atmos: boolean
    audio_codec: string | null
    audio_channels: string | null
    video_codec: string | null
    hdr_type: string | null
    source: string | null
    release_group: string | null
    quality_score: number
  }
  is_upgrade: boolean
  score_difference: number
  upgrade_details: {
    field: string
    from: string
    to: string
    impact: 'major' | 'moderate' | 'minor'
  }[]
}

// ============================================================================
// Release Groups Types (Feature 6)
// ============================================================================

export interface ReleaseGroup {
  id: number
  group_name: string
  is_preferred: boolean
  is_blocked: boolean
  priority: number
  avg_file_size_gb: number | null
  total_releases_seen: number
  total_downloads: number
  avg_quality_score: number | null
  first_seen_at: string | null
  last_seen_at: string | null
  notes: string | null
  metadata?: Record<string, any>
}

export interface ReleaseGroupSummary {
  total_groups: number
  preferred_count: number
  blocked_count: number
  top_groups: {
    group_name: string
    releases_seen: number
    avg_quality: number | null
    avg_size_gb: number | null
    is_preferred: boolean
  }[]
}

// ============================================================================
// Activity Feed Types (Feature 9)
// ============================================================================

export interface ActivityEvent {
  id: number
  event_type: string
  title: string
  description: string | null
  severity: 'info' | 'success' | 'warning' | 'error'
  movie_id: number | null
  movie_title: string | null
  movie_year: number | null
  related_id: string | null
  related_type: string | null
  quality_before: string | null
  quality_after: string | null
  metadata: Record<string, any> | null
  created_at: string
}

export interface ActivityFeedResponse {
  total: number
  limit: number
  offset: number
  events: ActivityEvent[]
}

export interface ActivitySummary {
  total_events: number
  hours: number
  by_type: Record<string, number>
  by_severity: Record<string, number>
}
