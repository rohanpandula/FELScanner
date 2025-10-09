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
            quality: { avg_file_size_gb: 0, avg_bitrate_mbps: 0 },
            recent: []
        });
        const reports = ref([]);
        const iptTorrents = ref([]);
        const connections = reactive({});
        const actionLoading = reactive({ scan: false, verify: false, monitor: false, ipt: false });
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

        const refreshAll = async () => {
            loading.value = true;
            await Promise.all([
                refreshStatus(),
                refreshMetrics(),
                refreshReports(),
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

        onMounted(async () => {
            await refreshAll();
            await loadSettings();
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
            showSettings,
            settingsForm,
            savingSettings,
            settingsMessage,
            testStatus,
            refreshAll,
            refreshIPT,
            triggerAction,
            toggleChartTheme,
            formatTimestamp,
            formatRelative,
            saveSettings,
            testPlex,
            testTelegram,
            testFlareSolverr,
            testIPT,
            connectService
        };
    }
}).mount('#app');
