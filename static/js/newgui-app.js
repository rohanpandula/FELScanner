const { createApp, ref, reactive, onMounted } = Vue;

const fetchJSON = async (url) => {
    const response = await fetch(url, { credentials: 'same-origin' });
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
};

const postForm = async (url, data = {}) => {
    const body = new URLSearchParams(data);
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        },
        body
    });
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
    return response.text();
};

const fetchMovieAPI = async (url) => {
    const response = await fetch(url, { credentials: 'same-origin' });
    const text = await response.text();
    let payload = {};
    if (text) {
        try {
            payload = JSON.parse(text);
        } catch (error) {
            throw new Error(`Invalid JSON response from ${url}`);
        }
    }
    if (!response.ok) {
        const message = payload && payload.error ? payload.error : `Request failed: ${response.status}`;
        throw new Error(message);
    }
    return payload;
};

createApp({
    setup() {
        const loading = ref(true);
        const flashMessage = ref('');
        const showSettings = ref(false);
        const savingSettings = ref(false);
        const settingsMessage = ref('');
        const state = reactive({
            is_scanning: false,
            monitor_active: false,
            last_scan_time: null,
            next_scan_time: null
        });
        const metrics = reactive({
            totals: { library: 0, dv: 0, fel: 0, atmos: 0 },
            ratios: { dv_percent: 0, atmos_percent: 0, fel_percent: 0, dv_and_atmos: 0, fel_and_atmos: 0 },
            dv_profiles: [],
            year_breakdown: [],
            quality: { median_file_size_gb: 0, median_bitrate_mbps: 0 },
            recent: []
        });
        const reports = ref([]);
        const iptTorrents = ref([]);
        const connections = reactive({});
        const actionLoading = reactive({ scan: false, verify: false, monitor: false, ipt: false });
        const downloads = reactive({
            pending: [],
            active: []
        });
        const settingsForm = reactive({
            plex_url: '',
            plex_token: '',
            library_name: '',
            collection_enable_dv: false,
            collection_name_all_dv: '',
            collection_enable_p7: false,
            collection_name_profile7: '',
            collection_enable_atmos: false,
            collection_name_truehd_atmos: '',
            scan_frequency: 24,
            auto_start: 'none',
            max_reports_size: 10,
            telegram_enabled: false,
            telegram_token: '',
            telegram_chat_id: '',
            telegram_notify_all_updates: false,
            telegram_notify_new_movies: false,
            telegram_notify_dv: false,
            telegram_notify_p7: false,
            telegram_notify_atmos: false,
            flaresolverr_url: '',
            ipt_uid: '',
            ipt_pass: ''
        });
        const testStatus = reactive({
            plex: { testing: false, success: false, message: '' },
            telegram: { testing: false, success: false, message: '' },
            flaresolverr: { testing: false, success: false, message: '' },
            ipt: { testing: false, success: false, message: '' }
        });
        const metadata = reactive({
            movies: [],
            summaryRefreshedAt: null
        });
        const movieSearch = ref('');
        const metadataLoading = reactive({ list: false, detail: false });
        const metadataError = reactive({ list: '', detail: '' });
        const metadataFilters = reactive({
            dvMode: 'off', // off, any, p7fel, other
            atmosOnly: false,
            resolution: 'all',
            sort: 'title'
        });
        const selectedMovie = ref(null);
        const selectedVersionId = ref(null);
        const getVersionFeatures = (version) => (version && version.features) ? version.features : {};

        const resolutionRank = (version) => {
            const features = getVersionFeatures(version);
            if (features.resolutionRank) return features.resolutionRank;
            const res = (version?.videoResolution || '').toString().toLowerCase();
            if (['4k', '2160', '2160p', 'uhd'].some((item) => res.includes(item))) return 3;
            if (['1080', '1080p'].some((item) => res.includes(item))) return 2;
            if (['720', '720p'].some((item) => res.includes(item))) return 1;
            const height = Number(version?.height);
            if (Number.isFinite(height)) {
                if (height >= 1700) return 3;
                if (height >= 900) return 2;
                if (height >= 700) return 1;
            }
            return 0;
        };

        const versionScore = (version) => {
            if (!version) return -1;
            const features = getVersionFeatures(version);
            let score = 0;
            if (features.hasDolbyVision) score += 100;
            if (features.dolbyVisionIsProfile7) score += 15;
            if (features.dolbyVisionHasFEL) score += 10;
            if (features.hasAtmos) score += 25;
            score += resolutionRank(version) * 5;
            if ((version.videoCodec || '').toLowerCase() === 'hevc') score += 2;
            if ((version.audioCodec || '').toLowerCase().includes('truehd')) score += 1;
            return score;
        };

        const getPreferredVersion = (movie) => {
            if (!movie || !Array.isArray(movie.versions) || !movie.versions.length) return null;
            if (movie.versions.length === 1) return movie.versions[0];
            const sorted = [...movie.versions].sort((a, b) => versionScore(b) - versionScore(a));
            return sorted[0];
        };

        const getPreferredVersionId = (movie) => {
            const preferred = getPreferredVersion(movie);
            if (preferred && preferred.id !== undefined && preferred.id !== null) {
                return preferred.id;
            }
            if (movie && Array.isArray(movie.versions) && movie.versions.length) {
                return movie.versions[0].id ?? null;
            }
            return null;
        };

        const filteredMovies = Vue.computed(() => {
            const query = movieSearch.value.trim().toLowerCase();
            const matchesQuery = (movie) => {
                if (!query) return true;
                const haystack = [
                    movie.title || '',
                    movie.year ? String(movie.year) : '',
                    ...(movie.collections || [])
                ].join(' ').toLowerCase();
                return haystack.includes(query);
            };

            const matchesFilters = (movie) => {
                const preferred = getPreferredVersion(movie);
                const features = getVersionFeatures(preferred);
                if (metadataFilters.dvMode === 'any' && !features.hasDolbyVision) return false;
                if (metadataFilters.dvMode === 'p7fel' && !(features.hasDolbyVision && features.dolbyVisionIsProfile7 && features.dolbyVisionHasFEL)) return false;
                if (metadataFilters.dvMode === 'other' && !(features.hasDolbyVision && (!features.dolbyVisionIsProfile7 || !features.dolbyVisionHasFEL))) return false;
                if (metadataFilters.atmosOnly && !features.hasAtmos) return false;
                if (metadataFilters.resolution !== 'all') {
                    const rank = features.resolutionRank || resolutionRank(preferred);
                    if (metadataFilters.resolution === '4k' && rank < 3) return false;
                    if (metadataFilters.resolution === '1080p' && (rank < 2 || rank >= 3)) return false;
                    if (metadataFilters.resolution === '720p' && rank !== 1) return false;
                }
                return true;
            };

            const sorter = (a, b) => {
                const sortKey = metadataFilters.sort;
                if (sortKey === 'dv') {
                    return versionScore(getPreferredVersion(b)) - versionScore(getPreferredVersion(a));
                }
                if (sortKey === 'resolution') {
                    return resolutionRank(getPreferredVersion(b)) - resolutionRank(getPreferredVersion(a));
                }
                if (sortKey === 'recent') {
                    const atA = new Date(a.updatedAt || a.addedAt || 0).getTime();
                    const atB = new Date(b.updatedAt || b.addedAt || 0).getTime();
                    return atB - atA;
                }
                // default title sort
                const titleA = (a.title || '').toLowerCase();
                const titleB = (b.title || '').toLowerCase();
                if (titleA < titleB) return -1;
                if (titleA > titleB) return 1;
                return 0;
            };

            return metadata.movies
                .filter((movie) => matchesQuery(movie) && matchesFilters(movie))
                .slice()
                .sort(sorter);
        });
        const selectedVersion = Vue.computed(() => {
            if (!selectedMovie.value || !Array.isArray(selectedMovie.value.versions)) return null;
            const versions = selectedMovie.value.versions;
            if (!versions.length) return null;
            if (!selectedVersionId.value) {
                return getPreferredVersion(selectedMovie.value) || versions[0];
            }
            return versions.find((item) => String(item.id) === String(selectedVersionId.value)) || versions[0];
        });
        let profileChart = null;
        let chartDark = true;

        const summaryCards = Vue.computed(() => [
            {
                label: 'Dolby Vision Titles',
                value: metrics.totals.dv,
                meta: `${metrics.ratios.dv_percent}% of library`
            },
            {
                label: 'Profile 7 FEL',
                value: metrics.totals.fel,
                meta: `${metrics.ratios.fel_percent}% of library`
            },
            {
                label: 'TrueHD Atmos',
                value: metrics.totals.atmos,
                meta: `${metrics.ratios.atmos_percent}% of library`
            },
            {
                label: 'DV + Atmos Overlap',
                value: metrics.ratios.dv_and_atmos,
                meta: 'Titles delivering both formats'
            }
        ]);

        const formatTimestamp = (value) => {
            if (!value) return null;
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) return value;
            return date.toLocaleString();
        };

        const formatRelative = (value) => {
            if (!value) return 'Unknown';
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) return value;
            const delta = Date.now() - date.getTime();
            const minute = 60 * 1000;
            const hour = 60 * minute;
            const day = 24 * hour;
            if (delta < minute) return 'Just now';
            if (delta < hour) return `${Math.floor(delta / minute)} min ago`;
            if (delta < day) return `${Math.floor(delta / hour)} hr ago`;
            return date.toLocaleDateString();
        };

        const formatFileSize = (value) => {
            const bytes = Number(value);
            if (!Number.isFinite(bytes) || bytes <= 0) return '—';
            const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
            let size = bytes;
            let unitIndex = 0;
            while (size >= 1024 && unitIndex < units.length - 1) {
                size /= 1024;
                unitIndex += 1;
            }
            const precision = size >= 10 || unitIndex === 0 ? 0 : 1;
            return `${size.toFixed(precision)} ${units[unitIndex]}`;
        };

        const formatBitrate = (value) => {
            const numeric = Number(value);
            if (!Number.isFinite(numeric) || numeric <= 0) return '—';
            const kbps = numeric > 100000 ? numeric / 1000 : numeric;
            if (kbps >= 1000) {
                return `${(kbps / 1000).toFixed(1)} Mbps`;
            }
            return `${Math.round(kbps)} Kbps`;
        };

        const formatDuration = (value) => {
            const ms = Number(value);
            if (!Number.isFinite(ms) || ms <= 0) return '—';
            const totalSeconds = Math.floor(ms / 1000);
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = totalSeconds % 60;
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            }
            if (minutes > 0) {
                return `${minutes}m ${seconds}s`;
            }
            return `${seconds}s`;
        };

        const formatResolution = (version) => {
            if (!version) return '—';
            if (version.width && version.height) {
                return `${version.width}×${version.height}`;
            }
            if (version.videoResolution) {
                return String(version.videoResolution).toUpperCase();
            }
            return '—';
        };

        const formatAudioSummary = (version) => {
            if (!version) return '—';
            const codec = version.audioCodec ? String(version.audioCodec).toUpperCase() : null;
            const channels = version.audioChannels ? `${version.audioChannels}ch` : null;
            return [codec, channels].filter(Boolean).join(' · ') || '—';
        };

        const formatVersionLabel = (version) => {
            if (!version) return 'Version';
            return [
                formatResolution(version),
                version.videoCodec ? String(version.videoCodec).toUpperCase() : null,
                version.container ? String(version.container).toUpperCase() : null
            ].filter(Boolean).join(' · ') || 'Version';
        };

        const dvLabel = (features) => {
            if (!features || !features.hasDolbyVision) return null;
            if (features.dolbyVisionIsProfile7) {
                return features.dolbyVisionHasFEL ? 'Dolby Vision P7 FEL' : 'Dolby Vision P7';
            }
            return 'Dolby Vision';
        };

        const formatVersionSummary = (version) => {
            if (!version) return 'Version data unavailable';
            const features = getVersionFeatures(version);
            const summary = [];
            const dv = dvLabel(features);
            if (dv) summary.push(dv);
            else if (features.dynamicRange) summary.push(features.dynamicRange);
            summary.push(formatResolution(version));
            if (version.videoCodec) summary.push(String(version.videoCodec).toUpperCase());
            if (features.audioFormats && features.audioFormats.length) {
                summary.push(features.audioFormats[0]);
            } else {
                summary.push(formatAudioSummary(version));
            }
            return summary.filter(Boolean).join(' · ') || 'Version data unavailable';
        };

        const formatLanguage = (code) => {
            if (!code) return null;
            return String(code).toUpperCase();
        };

        const formatSampleRate = (value) => {
            const numeric = Number(value);
            if (!Number.isFinite(numeric) || numeric <= 0) return null;
            if (numeric >= 1000) {
                const khz = numeric / 1000;
                return `${Number.isInteger(khz) ? khz.toFixed(0) : khz.toFixed(1)} kHz`;
            }
            return `${Math.round(numeric)} Hz`;
        };

        const formatChannels = (stream) => {
            if (!stream) return null;
            if (stream.channelLayout) {
                return String(stream.channelLayout).toUpperCase();
            }
            if (stream.channels) {
                return `${stream.channels}ch`;
            }
            return null;
        };

        const describeVideoStream = (stream) => {
            if (!stream) return '';
            const details = [
                stream.codec ? String(stream.codec).toUpperCase() : null,
                stream.width && stream.height ? `${stream.width}×${stream.height}` : null,
                stream.profile || null,
                stream.bitDepth ? `${stream.bitDepth}-bit` : null,
                stream.colorTransfer || stream.colorPrimaries
                    ? [stream.colorTransfer, stream.colorPrimaries].filter(Boolean).join('/')
                    : null
            ].filter(Boolean);
            return details.join(' · ');
        };

        const describeAudioStream = (stream) => {
            if (!stream) return '';
            const bitRate = formatBitrate(stream.bitRate);
            const sample = formatSampleRate(stream.sampleRate);
            const details = [
                stream.codec ? String(stream.codec).toUpperCase() : null,
                formatChannels(stream),
                sample,
                bitRate !== '—' ? bitRate : null,
                formatLanguage(stream.language),
                stream.title || null
            ].filter(Boolean);
            return details.join(' · ');
        };

        const describeSubtitleStream = (stream) => {
            if (!stream) return '';
            const flags = [];
            if (stream.forced) flags.push('Forced');
            if (stream.hearingImpaired) flags.push('SDH');
            const details = [
                stream.codec ? String(stream.codec).toUpperCase() : null,
                formatLanguage(stream.language),
                stream.title || null,
                flags.length ? flags.join(', ') : null
            ].filter(Boolean);
            return details.join(' · ');
        };

        const refreshStatus = async () => {
            const payload = await fetchJSON('/api/status');
            state.is_scanning = payload.status?.is_scanning || false;
            state.last_scan_time = payload.status?.last_scan_time;
            state.next_scan_time = payload.status?.next_scan_time;
            state.monitor_active = payload.status?.monitor_active || false;
        };

        const refreshMetrics = async () => {
            const payload = await fetchJSON('/api/metrics');
            Object.assign(metrics.totals, payload.totals || {});
            Object.assign(metrics.ratios, payload.ratios || {});
            metrics.dv_profiles = payload.dv_profiles || [];
            metrics.year_breakdown = payload.year_breakdown || [];
            metrics.quality = payload.quality || metrics.quality;
            metrics.recent = payload.recent || [];
            Vue.nextTick(updateChart);
        };

        const refreshReports = async () => {
            reports.value = await fetchJSON('/api/reports');
        };

        const refreshIPT = async () => {
            try {
                const payload = await fetchJSON('/api/iptscanner/torrents');
                iptTorrents.value = payload.torrents || [];
            } catch (error) {
                console.error('Failed to load IPT torrents', error);
            }
        };

        const refreshConnections = async () => {
            const payload = await fetchJSON('/api/connections');
            Object.keys(connections).forEach((key) => delete connections[key]);
            Object.assign(connections, payload);
        };

        const refreshMetadataList = async (forceRefresh = false) => {
            metadataLoading.list = true;
            metadataError.list = '';
            try {
                const url = forceRefresh ? '/api/movies?refresh=1' : '/api/movies';
                const payload = await fetchMovieAPI(url);
                const previousMap = new Map(
                    metadata.movies.map((item) => [String(item.ratingKey), item])
                );
                const items = (payload.movies || []).map((item) => {
                    const key = String(item.ratingKey);
                    const previous = previousMap.get(key);
                    if (
                        previous &&
                        previous.detailRefreshedAt &&
                        (!item.detailRefreshedAt || item.detailRefreshedAt === previous.detailRefreshedAt)
                    ) {
                        return { ...item, versions: previous.versions };
                    }
                    return item;
                });
                items.sort((a, b) => {
                    const titleA = (a.title || '').toLowerCase();
                    const titleB = (b.title || '').toLowerCase();
                    if (titleA < titleB) return -1;
                    if (titleA > titleB) return 1;
                    return 0;
                });
                metadata.movies = items;
                metadata.summaryRefreshedAt = payload.summaryRefreshedAt || null;

                if (selectedMovie.value) {
                    const match = items.find(
                        (item) => String(item.ratingKey) === String(selectedMovie.value.ratingKey)
                    );
                    if (match) {
                        selectedMovie.value = match;
                    }
                }
            } catch (error) {
                metadataError.list = error.message || 'Failed to load movie metadata.';
                console.error('Failed to load metadata list', error);
            } finally {
                metadataLoading.list = false;
            }
        };

        const loadMovieDetail = async (ratingKey, forceRefresh = true) => {
            if (!ratingKey) return null;
            metadataLoading.detail = true;
            metadataError.detail = '';
            const key = String(ratingKey);
            const previousVersionId = selectedVersionId.value ? String(selectedVersionId.value) : null;
            try {
                const url = forceRefresh ? `/api/movies/${key}?refresh=1` : `/api/movies/${key}`;
                const payload = await fetchMovieAPI(url);
                if (!payload.movie) {
                    throw new Error(payload.error || 'Metadata unavailable.');
                }
                const detail = payload.movie;
                selectedMovie.value = detail;

                const versionIds = (detail.versions || []).map((item) => String(item.id));
                if (previousVersionId && versionIds.includes(previousVersionId)) {
                    selectedVersionId.value = previousVersionId;
                } else {
                    selectedVersionId.value = getPreferredVersionId(detail);
                }

                const index = metadata.movies.findIndex(
                    (item) => String(item.ratingKey) === String(detail.ratingKey)
                );
                if (index >= 0) {
                    metadata.movies.splice(index, 1, detail);
                } else {
                    metadata.movies.push(detail);
                    metadata.movies.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
                }

                if (detail.detailError) {
                    metadataError.detail = detail.detailError;
                }
                return detail;
            } catch (error) {
                metadataError.detail = error.message || 'Failed to load metadata.';
                console.error('Failed to load movie detail', error);
                return null;
            } finally {
                metadataLoading.detail = false;
            }
        };

        const versionSummaryTags = (version) => {
            const features = getVersionFeatures(version);
            return features.summaryTags || [];
        };

        const tagBadgeClass = (tag) => {
            const lower = (tag || '').toLowerCase();
            if (lower.includes('fel')) return 'border-indigo-500/60 bg-indigo-500/10 text-indigo-200';
            if (lower.includes('do vi') || lower.includes('dolby vision')) return 'border-indigo-500/40 bg-indigo-500/5 text-indigo-100';
            if (lower.includes('atmos')) return 'border-teal-500/60 bg-teal-500/10 text-teal-200';
            if (lower.includes('4k')) return 'border-amber-500/40 bg-amber-500/10 text-amber-200';
            return 'border-slate-700 bg-slate-900/60 text-slate-300';
        };

        const selectMovie = async (movie, options = {}) => {
            if (!movie || !movie.ratingKey) return;
            selectedMovie.value = movie;
            selectedVersionId.value = getPreferredVersionId(movie);
            metadataError.detail = '';
            const forceRefresh = options.refresh !== undefined ? options.refresh : true;
            await loadMovieDetail(movie.ratingKey, forceRefresh);
        };

        const refreshSelectedMovie = async () => {
            if (!selectedMovie.value || !selectedMovie.value.ratingKey) return;
            metadataError.detail = '';
            await loadMovieDetail(selectedMovie.value.ratingKey, true);
        };

        const setSelectedVersion = (versionId) => {
            selectedVersionId.value = versionId;
        };

        const cycleDvFilter = () => {
            const order = ['off', 'any', 'p7fel', 'other'];
            const idx = order.indexOf(metadataFilters.dvMode);
            metadataFilters.dvMode = order[(idx + 1) % order.length];
        };

        const dvFilterLabel = Vue.computed(() => {
            switch (metadataFilters.dvMode) {
                case 'any':
                    return 'DV: Any';
                case 'p7fel':
                    return 'DV: P7 FEL';
                case 'other':
                    return 'DV: Other';
                default:
                    return 'DV: Off';
            }
        });

        const dvFilterActive = Vue.computed(() => metadataFilters.dvMode !== 'off');

        const movieByRatingKey = (ratingKey) => {
            if (!ratingKey) return null;
            return metadata.movies.find((item) => String(item.ratingKey) === String(ratingKey)) || null;
        };

        const openRecentMovie = async (item) => {
            if (!item || !item.rating_key) return;
            const ratingKey = String(item.rating_key);
            const existing = movieByRatingKey(ratingKey);
            if (existing) {
                await selectMovie(existing, { refresh: true });
                return;
            }
            await loadMovieDetail(ratingKey, true);
        };

        const refreshAll = async () => {
            loading.value = true;
            await Promise.all([
                refreshStatus(),
                refreshMetrics(),
                refreshReports(),
                refreshIPT(),
                refreshConnections(),
                refreshMetadataList()
            ]).catch((error) => console.error('Refresh error', error));
            loading.value = false;
        };

        const triggerAction = async (endpoint, payload = {}) => {
            const key = endpoint.includes('ipt') ? 'ipt' : endpoint.includes('verify') ? 'verify' : endpoint.includes('monitor') ? 'monitor' : 'scan';
            actionLoading[key] = true;
            flashMessage.value = '';
            try {
                await postForm(endpoint, payload);
                flashMessage.value = 'Action requested successfully.';
                await refreshAll();
            } catch (error) {
                console.error('Action failed', error);
                flashMessage.value = 'Unable to complete the request.';
            } finally {
                actionLoading[key] = false;
                setTimeout(() => {
                    flashMessage.value = '';
                }, 4000);
            }
        };

        const updateChart = () => {
            const ctx = document.getElementById('profileChart');
            if (!ctx) return;
            const labels = metrics.dv_profiles.map((item) => `Profile ${item.profile}`);
            const dataPoints = metrics.dv_profiles.map((item) => item.count);
            if (!labels.length) {
                if (profileChart) {
                    profileChart.destroy();
                    profileChart = null;
                }
                return;
            }
            const palette = chartDark
                ? ['#6366F1', '#14B8A6', '#F97316', '#E879F9', '#38BDF8', '#FCD34D']
                : ['#312E81', '#0F766E', '#C2410C', '#9D174D', '#0C4A6E', '#CA8A04'];
            if (profileChart) {
                profileChart.data.labels = labels;
                profileChart.data.datasets[0].data = dataPoints;
                profileChart.data.datasets[0].backgroundColor = palette;
                profileChart.update();
                return;
            }
            profileChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels,
                    datasets: [
                        {
                            data: dataPoints,
                            backgroundColor: palette,
                            borderColor: '#0f172a',
                            borderWidth: 2,
                            hoverOffset: 12
                        }
                    ]
                },
                options: {
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                color: chartDark ? '#E2E8F0' : '#1F2937'
                            }
                        }
                    }
                }
            });
        };

        const toggleChartTheme = () => {
            chartDark = !chartDark;
            if (profileChart) {
                profileChart.destroy();
                profileChart = null;
            }
            Vue.nextTick(updateChart);
        };

        const startAutoRefresh = () => {
            setInterval(() => {
                refreshStatus();
                refreshConnections();
            }, 15000);
        };

        const loadSettings = async () => {
            try {
                const payload = await fetchJSON('/api/settings');
                Object.assign(settingsForm, payload);
            } catch (error) {
                console.error('Failed to load settings', error);
            }
        };

        const saveSettings = async () => {
            savingSettings.value = true;
            settingsMessage.value = '';
            try {
                const body = new URLSearchParams(settingsForm);
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
                    },
                    body
                });
                if (!response.ok) {
                    throw new Error(`Request failed: ${response.status}`);
                }
                settingsMessage.value = 'Settings saved successfully!';
                setTimeout(() => {
                    settingsMessage.value = '';
                    showSettings.value = false;
                }, 2000);
            } catch (error) {
                console.error('Failed to save settings', error);
                settingsMessage.value = 'Failed to save settings. Please try again.';
            } finally {
                savingSettings.value = false;
            }
        };

        const testPlex = async () => {
            testStatus.plex.testing = true;
            testStatus.plex.message = '';
            try {
                const response = await fetch('/api/test-connection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        plex_url: settingsForm.plex_url,
                        plex_token: settingsForm.plex_token,
                        library_name: settingsForm.library_name
                    })
                });
                const result = await response.json();
                testStatus.plex.success = result.success;
                testStatus.plex.message = result.success
                    ? `Connected! Found ${result.movie_count} movies.`
                    : result.error || 'Connection failed';
            } catch (error) {
                testStatus.plex.success = false;
                testStatus.plex.message = error.message || 'Test failed';
            } finally {
                testStatus.plex.testing = false;
            }
        };

        const testTelegram = async () => {
            testStatus.telegram.testing = true;
            testStatus.telegram.message = '';
            try {
                const response = await fetch('/api/test-telegram', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        token: settingsForm.telegram_token,
                        chat_id: settingsForm.telegram_chat_id
                    })
                });
                const result = await response.json();
                testStatus.telegram.success = result.success;
                testStatus.telegram.message = result.success
                    ? 'Test message sent successfully!'
                    : result.error || 'Test failed';
            } catch (error) {
                testStatus.telegram.success = false;
                testStatus.telegram.message = error.message || 'Test failed';
            } finally {
                testStatus.telegram.testing = false;
            }
        };

        const testFlareSolverr = async () => {
            testStatus.flaresolverr.testing = true;
            testStatus.flaresolverr.message = '';
            try {
                const response = await fetch('/api/test-flaresolverr', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: settingsForm.flaresolverr_url
                    })
                });
                const result = await response.json();
                testStatus.flaresolverr.success = result.success;
                testStatus.flaresolverr.message = result.success
                    ? (result.message || 'FlareSolverr is working!')
                    : result.error || 'Test failed';
            } catch (error) {
                testStatus.flaresolverr.success = false;
                testStatus.flaresolverr.message = error.message || 'Test failed';
            } finally {
                testStatus.flaresolverr.testing = false;
            }
        };

        const testIPT = async () => {
            testStatus.ipt.testing = true;
            testStatus.ipt.message = '';
            try {
                const response = await fetch('/api/iptscanner/test-login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        uid: settingsForm.ipt_uid,
                        pass: settingsForm.ipt_pass
                    })
                });
                const result = await response.json();
                testStatus.ipt.success = result.success;
                testStatus.ipt.message = result.success
                    ? (result.message || 'IPTorrents login successful!')
                    : result.error || 'Login failed';
            } catch (error) {
                testStatus.ipt.success = false;
                testStatus.ipt.message = error.message || 'Test failed';
            } finally {
                testStatus.ipt.testing = false;
            }
        };

        const connectService = async (serviceName) => {
            if (serviceName === 'iptorrents') {
                // For IPT, try to fetch torrents if credentials are configured
                actionLoading.ipt = true;
                flashMessage.value = 'Connecting to IPTorrents...';
                try {
                    await postForm('/actions/ipt-fetch');
                    flashMessage.value = 'Connected to IPTorrents successfully!';
                    await refreshAll();
                } catch (error) {
                    console.error('IPT connection failed', error);
                    flashMessage.value = 'IPTorrents connection failed. Opening settings...';
                    setTimeout(() => {
                        showSettings.value = true;
                    }, 1500);
                } finally {
                    actionLoading.ipt = false;
                    setTimeout(() => {
                        flashMessage.value = '';
                    }, 4000);
                }
            } else {
                // For other services, open settings modal
                showSettings.value = true;
            }
        };

        const refreshDownloads = async () => {
            try {
                const [pendingData, activeData] = await Promise.all([
                    fetchJSON('/api/download/pending'),
                    fetchJSON('/api/download/active')
                ]);
                downloads.pending = (pendingData || []).map((download) => ({
                    ...download,
                    id: download.request_id || download.id
                }));
                downloads.active = activeData || [];
            } catch (error) {
                console.error('Failed to refresh downloads', error);
            }
        };

        const checkTorrentUpgrade = async (torrent) => {
            // Mark torrent as being checked
            torrent.checking = true;
            flashMessage.value = 'Checking torrent for quality upgrades...';

            try {
                const response = await fetch('/api/download/check-upgrade', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: torrent.name,
                        link: torrent.link,
                        size: torrent.size
                    })
                });

                const result = await response.json();

                if (result.success) {
                    if (result.skipped) {
                        flashMessage.value = result.message || 'Not a quality upgrade';
                    } else {
                        flashMessage.value = result.message || 'Upgrade check complete';
                        // Refresh pending downloads to show the new approval request
                        await refreshDownloads();
                    }
                } else {
                    flashMessage.value = `Check failed: ${result.error || 'Unknown error'}`;
                }
            } catch (error) {
                console.error('Failed to check torrent upgrade', error);
                flashMessage.value = 'Failed to check torrent upgrade';
            } finally {
                torrent.checking = false;
                setTimeout(() => {
                    flashMessage.value = '';
                }, 4000);
            }
        };

        const approveDownload = async (downloadId) => {
            const download = downloads.pending.find(
                (d) => (d.request_id || d.id) === downloadId
            );
            if (!download) return;

            const requestId = download.request_id || downloadId;
            download.processing = true;
            try {
                const response = await fetch('/api/download/approve', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ request_id: requestId })
                });
                const result = await response.json();

                if (result.success) {
                    flashMessage.value = 'Download approved! Adding to qBittorrent...';
                    await refreshDownloads();
                } else {
                    flashMessage.value = `Failed to approve: ${result.error || 'Unknown error'}`;
                }
            } catch (error) {
                console.error('Failed to approve download', error);
                flashMessage.value = 'Failed to approve download';
            } finally {
                download.processing = false;
                setTimeout(() => {
                    flashMessage.value = '';
                }, 4000);
            }
        };

        const declineDownload = async (downloadId) => {
            const download = downloads.pending.find(
                (d) => (d.request_id || d.id) === downloadId
            );
            if (!download) return;

            const requestId = download.request_id || downloadId;
            download.processing = true;
            try {
                const response = await fetch('/api/download/decline', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ request_id: requestId })
                });
                const result = await response.json();

                if (result.success) {
                    flashMessage.value = 'Download declined';
                    await refreshDownloads();
                } else {
                    flashMessage.value = `Failed to decline: ${result.error || 'Unknown error'}`;
                }
            } catch (error) {
                console.error('Failed to decline download', error);
                flashMessage.value = 'Failed to decline download';
            } finally {
                download.processing = false;
                setTimeout(() => {
                    flashMessage.value = '';
                }, 3000);
            }
        };

        const formatTorrentState = (state) => {
            const stateMap = {
                'downloading': 'Downloading',
                'pausedDL': 'Paused',
                'stalledDL': 'Stalled',
                'uploading': 'Seeding',
                'stalledUP': 'Seeding',
                'pausedUP': 'Completed',
                'queuedDL': 'Queued',
                'queuedUP': 'Queued',
                'checkingDL': 'Checking',
                'checkingUP': 'Checking',
                'error': 'Error',
                'missingFiles': 'Missing',
                'unknown': 'Unknown'
            };
            return stateMap[state] || state || 'Unknown';
        };

        const formatSpeed = (bytesPerSecond) => {
            const bytes = Number(bytesPerSecond);
            if (!Number.isFinite(bytes) || bytes <= 0) return '—';

            if (bytes >= 1024 * 1024) {
                return `${(bytes / (1024 * 1024)).toFixed(1)} MB/s`;
            }
            if (bytes >= 1024) {
                return `${(bytes / 1024).toFixed(1)} KB/s`;
            }
            return `${bytes} B/s`;
        };

        onMounted(async () => {
            await refreshAll();
            await loadSettings();
            await refreshDownloads();
            startAutoRefresh();
        });

        return {
            loading,
            state,
            metrics,
            reports,
            iptTorrents,
            connections,
            actionLoading,
            downloads,
            summaryCards,
            flashMessage,
            showSettings,
            settingsForm,
            savingSettings,
            settingsMessage,
            testStatus,
            refreshAll,
            refreshIPT,
            refreshDownloads,
            checkTorrentUpgrade,
            approveDownload,
            declineDownload,
            metadata,
            movieSearch,
            metadataFilters,
            filteredMovies,
            metadataLoading,
            metadataError,
            selectedMovie,
            selectedVersion,
            selectedVersionId,
            refreshMetadataList,
            getPreferredVersion,
            getVersionFeatures,
            versionSummaryTags,
            tagBadgeClass,
            selectMovie,
            refreshSelectedMovie,
            setSelectedVersion,
            cycleDvFilter,
            dvFilterLabel,
            dvFilterActive,
            movieByRatingKey,
            openRecentMovie,
            triggerAction,
            toggleChartTheme,
            formatTimestamp,
            formatRelative,
            formatFileSize,
            formatBitrate,
            formatDuration,
            formatResolution,
            formatAudioSummary,
            formatVersionSummary,
            formatVersionLabel,
            formatTorrentState,
            formatSpeed,
            describeVideoStream,
            describeAudioStream,
            describeSubtitleStream,
            saveSettings,
            testPlex,
            testTelegram,
            testFlareSolverr,
            testIPT,
            connectService
        };
    }
}).mount('#app');
