// Settings page JavaScript
(function() {
    'use strict';

    // Tab switching
    function initTabs() {
        const tabButtons = document.querySelectorAll('.tab-button');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabName = button.getAttribute('data-tab');

                // Remove active class from all tabs and contents
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));

                // Add active class to clicked tab and corresponding content
                button.classList.add('active');
                document.getElementById(`${tabName}-tab`).classList.add('active');
            });
        });
    }

    // Load settings from API
    async function loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const settings = await response.json();

            // Plex settings
            document.getElementById('plex-url').value = settings.plex_url || '';
            document.getElementById('plex-token').value = settings.plex_token || '';
            document.getElementById('library-name').value = settings.library_name || '';

            // Telegram settings
            document.getElementById('telegram-enabled').checked = settings.telegram_enabled || false;
            document.getElementById('telegram-token').value = settings.telegram_token || '';
            document.getElementById('telegram-chat-id').value = settings.telegram_chat_id || '';

            // Collections
            document.getElementById('collection-enable-dv').checked = settings.collection_enable_dv || false;
            document.getElementById('collection-dv').value = settings.collection_name_all_dv || '';
            document.getElementById('collection-enable-p7').checked = settings.collection_enable_p7 || false;
            document.getElementById('collection-p7').value = settings.collection_name_profile7 || '';
            document.getElementById('collection-enable-atmos').checked = settings.collection_enable_atmos || false;
            document.getElementById('collection-atmos').value = settings.collection_name_truehd_atmos || '';

            // Scanning
            document.getElementById('scan-frequency').value = settings.scan_frequency || 24;
            document.getElementById('auto-start').value = settings.auto_start || 'none';
            document.getElementById('max-reports-size').value = settings.max_reports_size || 5;

            // Load Radarr settings
            const radarrResponse = await fetch('/api/radarr/settings');
            const radarrSettings = await radarrResponse.json();
            document.getElementById('radarr-url').value = radarrSettings.url || '';
            document.getElementById('radarr-api-key').value = radarrSettings.api_key || '';
            document.getElementById('radarr-root-path').value = radarrSettings.root_path || '';

            // Load qBittorrent settings
            const qbtResponse = await fetch('/api/qbittorrent/settings');
            const qbtSettings = await qbtResponse.json();
            document.getElementById('qbt-host').value = qbtSettings.host || '';
            document.getElementById('qbt-port').value = qbtSettings.port || 8080;
            document.getElementById('qbt-username').value = qbtSettings.username || '';
            document.getElementById('qbt-category').value = qbtSettings.category || '';
            document.getElementById('qbt-pause-on-add').checked = qbtSettings.pause_on_add || false;
            document.getElementById('qbt-sequential').checked = qbtSettings.sequential_download || false;

            // Load notification settings
            const notifResponse = await fetch('/api/settings/notifications');
            const notifSettings = await notifResponse.json();
            document.getElementById('notify-fel').checked = notifSettings.notify_fel !== false;
            document.getElementById('notify-fel-from-p5').checked = notifSettings.notify_fel_from_p5 !== false;
            document.getElementById('notify-fel-from-hdr').checked = notifSettings.notify_fel_from_hdr !== false;
            document.getElementById('notify-fel-duplicates').checked = notifSettings.notify_fel_duplicates || false;
            document.getElementById('notify-dv').checked = notifSettings.notify_dv || false;
            document.getElementById('notify-dv-from-hdr').checked = notifSettings.notify_dv_from_hdr !== false;
            document.getElementById('notify-dv-profile-upgrades').checked = notifSettings.notify_dv_profile_upgrades !== false;
            document.getElementById('notify-atmos').checked = notifSettings.notify_atmos || false;
            document.getElementById('notify-atmos-only-if-no-atmos').checked = notifSettings.notify_atmos_only_if_no_atmos !== false;
            document.getElementById('notify-atmos-with-dv-upgrade').checked = notifSettings.notify_atmos_with_dv_upgrade !== false;
            document.getElementById('notify-resolution').checked = notifSettings.notify_resolution || false;
            document.getElementById('notify-resolution-only-upgrades').checked = notifSettings.notify_resolution_only_upgrades !== false;
            document.getElementById('notify-only-library-movies').checked = notifSettings.notify_only_library_movies !== false;
            document.getElementById('notify-expire-hours').value = notifSettings.notify_expire_hours || 24;
            document.getElementById('notify-download-start').checked = notifSettings.notify_download_start !== false;
            document.getElementById('notify-download-complete').checked = notifSettings.notify_download_complete !== false;
            document.getElementById('notify-download-error').checked = notifSettings.notify_download_error !== false;

        } catch (error) {
            console.error('Error loading settings:', error);
            showNotification('Failed to load settings', 'error');
        }
    }

    // Test connection buttons
    function initTestButtons() {
        const testButtons = document.querySelectorAll('.test-btn');

        testButtons.forEach(button => {
            button.addEventListener('click', async () => {
                const service = button.getAttribute('data-service');
                const statusEl = document.getElementById(`${service}-status`);

                statusEl.textContent = 'Testing...';
                statusEl.className = 'status-indicator';

                try {
                    let result;

                    if (service === 'plex') {
                        const response = await fetch('/api/test-connection', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                plex_url: document.getElementById('plex-url').value,
                                plex_token: document.getElementById('plex-token').value,
                                library_name: document.getElementById('library-name').value
                            })
                        });
                        result = await response.json();
                    } else if (service === 'telegram') {
                        const response = await fetch('/api/test-telegram', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                telegram_token: document.getElementById('telegram-token').value,
                                telegram_chat_id: document.getElementById('telegram-chat-id').value
                            })
                        });
                        result = await response.json();
                    } else if (service === 'radarr') {
                        const response = await fetch('/api/radarr/test-connection', {
                            method: 'POST'
                        });
                        result = await response.json();
                    } else if (service === 'qbittorrent') {
                        const response = await fetch('/api/qbittorrent/test-connection', {
                            method: 'POST'
                        });
                        result = await response.json();
                    }

                    if (result.success) {
                        statusEl.textContent = `✓ ${result.message || 'Connected'}`;
                        statusEl.className = 'status-indicator success';
                    } else {
                        statusEl.textContent = `✗ ${result.error || 'Connection failed'}`;
                        statusEl.className = 'status-indicator error';
                    }
                } catch (error) {
                    console.error(`Error testing ${service}:`, error);
                    statusEl.textContent = `✗ ${error.message}`;
                    statusEl.className = 'status-indicator error';
                }
            });
        });
    }

    // Save buttons
    function initSaveButtons() {
        const saveButtons = document.querySelectorAll('.save-btn');

        saveButtons.forEach(button => {
            button.addEventListener('click', async () => {
                const tab = button.getAttribute('data-tab');

                try {
                    if (tab === 'connections') {
                        await saveConnectionSettings();
                    } else if (tab === 'notifications') {
                        await saveNotificationSettings();
                    } else if (tab === 'downloads') {
                        await saveDownloadSettings();
                    } else if (tab === 'advanced') {
                        await saveAdvancedSettings();
                    }

                    showNotification('Settings saved successfully', 'success');
                } catch (error) {
                    console.error('Error saving settings:', error);
                    showNotification('Failed to save settings', 'error');
                }
            });
        });
    }

    async function saveConnectionSettings() {
        // Save Plex and Telegram to main settings
        const mainSettings = {
            plex_url: document.getElementById('plex-url').value,
            plex_token: document.getElementById('plex-token').value,
            library_name: document.getElementById('library-name').value,
            telegram_enabled: document.getElementById('telegram-enabled').checked,
            telegram_token: document.getElementById('telegram-token').value,
            telegram_chat_id: document.getElementById('telegram-chat-id').value
        };

        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(mainSettings)
        });

        // Save Radarr settings
        const radarrSettings = {
            url: document.getElementById('radarr-url').value,
            api_key: document.getElementById('radarr-api-key').value,
            root_path: document.getElementById('radarr-root-path').value
        };

        await fetch('/api/radarr/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(radarrSettings)
        });

        // Save qBittorrent settings
        const qbtSettings = {
            host: document.getElementById('qbt-host').value,
            port: parseInt(document.getElementById('qbt-port').value),
            username: document.getElementById('qbt-username').value,
            password: document.getElementById('qbt-password').value,
            category: document.getElementById('qbt-category').value,
            pause_on_add: document.getElementById('qbt-pause-on-add').checked,
            sequential_download: document.getElementById('qbt-sequential').checked
        };

        await fetch('/api/qbittorrent/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(qbtSettings)
        });
    }

    async function saveNotificationSettings() {
        const settings = {
            notify_fel: document.getElementById('notify-fel').checked,
            notify_fel_from_p5: document.getElementById('notify-fel-from-p5').checked,
            notify_fel_from_hdr: document.getElementById('notify-fel-from-hdr').checked,
            notify_fel_duplicates: document.getElementById('notify-fel-duplicates').checked,
            notify_dv: document.getElementById('notify-dv').checked,
            notify_dv_from_hdr: document.getElementById('notify-dv-from-hdr').checked,
            notify_dv_profile_upgrades: document.getElementById('notify-dv-profile-upgrades').checked,
            notify_atmos: document.getElementById('notify-atmos').checked,
            notify_atmos_only_if_no_atmos: document.getElementById('notify-atmos-only-if-no-atmos').checked,
            notify_atmos_with_dv_upgrade: document.getElementById('notify-atmos-with-dv-upgrade').checked,
            notify_resolution: document.getElementById('notify-resolution').checked,
            notify_resolution_only_upgrades: document.getElementById('notify-resolution-only-upgrades').checked,
            notify_only_library_movies: document.getElementById('notify-only-library-movies').checked,
            notify_expire_hours: parseInt(document.getElementById('notify-expire-hours').value),
            notify_download_start: document.getElementById('notify-download-start').checked,
            notify_download_complete: document.getElementById('notify-download-complete').checked,
            notify_download_error: document.getElementById('notify-download-error').checked
        };

        await fetch('/api/settings/notifications', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
    }

    async function saveDownloadSettings() {
        const settings = {
            category: document.getElementById('qbt-category').value,
            pause_on_add: document.getElementById('qbt-pause-on-add').checked,
            sequential_download: document.getElementById('qbt-sequential').checked
        };

        await fetch('/api/qbittorrent/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
    }

    async function saveAdvancedSettings() {
        const settings = {
            collection_enable_dv: document.getElementById('collection-enable-dv').checked,
            collection_name_all_dv: document.getElementById('collection-dv').value,
            collection_enable_p7: document.getElementById('collection-enable-p7').checked,
            collection_name_profile7: document.getElementById('collection-p7').value,
            collection_enable_atmos: document.getElementById('collection-enable-atmos').checked,
            collection_name_truehd_atmos: document.getElementById('collection-atmos').value,
            scan_frequency: parseInt(document.getElementById('scan-frequency').value),
            auto_start: document.getElementById('auto-start').value,
            max_reports_size: parseInt(document.getElementById('max-reports-size').value)
        };

        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
    }

    function showNotification(message, type) {
        // Create a simple notification
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: ${type === 'success' ? '#d4edda' : '#f8d7da'};
            color: ${type === 'success' ? '#155724' : '#721c24'};
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 10000;
            animation: slideIn 0.3s;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', () => {
        initTabs();
        loadSettings();
        initTestButtons();
        initSaveButtons();
    });
})();
