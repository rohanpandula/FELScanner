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

createApp({
    setup() {
        const loading = ref(true);
        const flashMessage = ref('');
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
            quality: { avg_file_size_gb: 0, avg_bitrate_mbps: 0 },
            recent: []
        });
        const iptTorrents = ref([]);
        const connections = reactive({});
        const actionLoading = reactive({ scan: false, verify: false, monitor: false, ipt: false });
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

        const refreshReports = async () => Promise.resolve();

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

        const refreshAll = async () => {
            loading.value = true;
            await Promise.all([
                refreshStatus(),
                refreshMetrics(),
                refreshIPT(),
                refreshConnections()
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

        onMounted(async () => {
            await refreshAll();
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
            summaryCards,
            flashMessage,
            refreshAll,
            refreshIPT,
            triggerAction,
            toggleChartTheme,
            formatTimestamp,
            formatRelative
        };
    }
}).mount('#app');
