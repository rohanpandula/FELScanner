// DOM Elements
const setupWizard = document.getElementById('setup-wizard');
const mainDashboard = document.getElementById('main-dashboard');
const statusBadge = document.getElementById('status-badge');
const scanProgressContainer = document.getElementById('scan-progress-container');
const scanProgress = document.getElementById('scan-progress');
const totalMovies = document.getElementById('total-movies');
const dvMovies = document.getElementById('dv-movies');
const p7Movies = document.getElementById('p7-movies');
const atmosMovies = document.getElementById('atmos-movies');
const heroTotalMetric = document.getElementById('hero-total-metric');
const heroDvMetric = document.getElementById('hero-dv-metric');
const heroP7Metric = document.getElementById('hero-p7-metric');
const heroAtmosMetric = document.getElementById('hero-atmos-metric');
const lastScanTime = document.getElementById('last-scan-time');
const lastScanTimeMobile = document.getElementById('last-scan-time-mobile');
const nextScanContainer = document.getElementById('next-scan-container');
const nextScanContainerMobile = document.getElementById('next-scan-container-mobile');
const nextScanTime = document.getElementById('next-scan-time');
const nextScanTimeMobile = document.getElementById('next-scan-time-mobile');
const startScanBtn = document.getElementById('start-scan-btn');
const verifyCollectionsBtn = document.getElementById('verify-collections-btn');
const startMonitorBtn = document.getElementById('start-monitor-btn');
const stopMonitorBtn = document.getElementById('stop-monitor-btn');
const heroMonitorStatus = document.getElementById('hero-monitor-status');
const heroMonitorCaption = document.getElementById('hero-monitor-caption');
const heroMonitorSubcaption = document.getElementById('hero-monitor-subcaption');
const noChangesAlert = document.getElementById('no-changes-alert');
const changesContainer = document.getElementById('changes-container');
const collectionTabs = document.getElementById('collection-tabs');
const collectionContents = document.getElementById('collection-contents');
const reportsTable = document.getElementById('reports-table');
const viewAllReports = document.getElementById('view-all-reports');

const setupProgressFill = document.getElementById('setup-progress-fill');
const setupProgressSteps = document.querySelectorAll('.setup-progress-step');
const buddyCard = document.getElementById('onboarding-buddy');
const buddyEmoji = document.getElementById('buddy-emoji');
const buddyTitle = document.getElementById('buddy-title');
const buddyMessage = document.getElementById('buddy-message');
const buddyChecklist = document.getElementById('buddy-checklist');
const buddyFooterText = document.getElementById('buddy-footer-text');

// Setup Wizard Elements
const setupSteps = document.querySelectorAll('.setup-step');
const nextStepBtns = document.querySelectorAll('.next-step');
const prevStepBtns = document.querySelectorAll('.prev-step');
const testPlexBtn = document.getElementById('test-plex-btn');
const plexSuccess = document.getElementById('plex-success');
const plexError = document.getElementById('plex-error');
const telegramEnabled = document.getElementById('telegram-enabled');
const telegramSettings = document.getElementById('telegram-settings');
const testTelegramBtn = document.getElementById('test-telegram-btn');
const telegramSuccess = document.getElementById('telegram-success');
const telegramError = document.getElementById('telegram-error');

// Settings Elements
const settingsForm = document.getElementById('settings-form');
const settingsPlexUrl = document.getElementById('settings-plex-url');
const settingsPlexToken = document.getElementById('settings-plex-token');
const settingsLibraryName = document.getElementById('settings-library-name');
const settingsCollectionDv = document.getElementById('settings-collection-dv');
const settingsCollectionP7 = document.getElementById('settings-collection-p7');
const settingsCollectionAtmos = document.getElementById('settings-collection-atmos');
const settingsReportsSize = document.getElementById('settings-reports-size');
const settingsScanFrequency = document.getElementById('settings-scan-frequency');
const settingsTelegramEnabled = document.getElementById('settings-telegram-enabled');
const settingsTelegramContainer = document.getElementById('settings-telegram-container');
const settingsTelegramToken = document.getElementById('settings-telegram-token');
const settingsTelegramChatId = document.getElementById('settings-telegram-chat-id');
const settingsNotifyAll = document.getElementById('settings-notify-all');
const settingsNotifyNew = document.getElementById('settings-notify-new');
const settingsNotifyDv = document.getElementById('settings-notify-dv');
const settingsNotifyP7 = document.getElementById('settings-notify-p7');
const settingsNotifyAtmos = document.getElementById('settings-notify-atmos');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const resetSettingsBtn = document.getElementById('reset-settings-btn');
const settingsEnableDv = document.getElementById('settings-enable-dv');
const settingsEnableP7 = document.getElementById('settings-enable-p7');
const settingsEnableAtmos = document.getElementById('settings-enable-atmos');

// Constants
const POLL_INTERVAL = 5000;  // 5 seconds

// State
let isPolling = false;
let pollTimer = null;
let currentCollectionTab = 'dv'; // Default tab: dv, p7 or atmos
let activeSetupStepIndex = 0;
let buddyCelebrationTimer = null;

// Global variable to store rounding preference
window.useWholeNumbers = true;

const onboardingSteps = [
    {
        emoji: '👋',
        title: 'Connect to Plex',
        message: 'Add your Plex server URL, token, and library name so FELScanner knows exactly where to look.',
        checklist: [
            'Paste the full Plex URL including the port number',
            'Grab your Plex token from the account dashboard',
            'Enter the exact library name you want to scan'
        ]
    },
    {
        emoji: '🎬',
        title: 'Curate your collections',
        message: 'Choose descriptive names for Dolby Vision, Profile 7, and Atmos collections so Plex stays organised.',
        checklist: [
            'Pick intuitive titles for each collection',
            'Adjust the report storage limit to suit your disk space',
            'Keep collection names unique for easier filtering'
        ]
    },
    {
        emoji: '📣',
        title: 'Optional notifications',
        message: 'Enable Telegram alerts to celebrate new Dolby Vision arrivals or Atmos upgrades automatically.',
        checklist: [
            'Toggle Telegram alerts if you want instant updates',
            'Paste your bot token and chat ID',
            'Send a test message to confirm everything works'
        ]
    }
];

const buddyCelebrations = {
    plexSuccess: {
        emoji: '🎉',
        title: 'Connection verified',
        message: 'Plex responded perfectly. Continue to your collection preferences whenever you are ready.',
        checklist: [
            'Double-check your collection naming next',
            'Keep the wizard open while adjusting settings'
        ]
    },
    telegramSuccess: {
        emoji: '📬',
        title: 'Telegram is ready',
        message: 'Notifications will fly the moment we spot new Dolby Vision, FEL, or Atmos content.',
        checklist: [
            'Stay subscribed to receive future updates',
            'You can always toggle alerts from Settings later'
        ]
    },
    saving: {
        emoji: '🚀',
        title: 'Finishing setup…',
        message: 'We are storing your preferences and preparing the dashboard. This only takes a moment.',
        checklist: [
            'Please keep this tab open while we save',
            'The dashboard will reload automatically when done'
        ]
    }
};

function applyBuddyContent(content, { celebrate = false, temporary = false } = {}) {
    if (!buddyTitle || !content) {
        return;
    }

    if (buddyEmoji && content.emoji) {
        buddyEmoji.textContent = content.emoji;
    }

    buddyTitle.textContent = content.title || '';
    buddyMessage.textContent = content.message || '';

    if (buddyChecklist) {
        if (Array.isArray(content.checklist) && content.checklist.length) {
            buddyChecklist.innerHTML = content.checklist
                .map(item => `<li><span class="icon"><i class="fas fa-check-circle"></i></span><span>${item}</span></li>`)
                .join('');
        } else {
            buddyChecklist.innerHTML = '';
        }
    }

    if (buddyCard) {
        buddyCard.classList.toggle('celebrating', celebrate);
    }

    clearTimeout(buddyCelebrationTimer);

    if (temporary) {
        buddyCelebrationTimer = setTimeout(() => {
            updateOnboardingBuddy(activeSetupStepIndex);
        }, 6000);
    }
}

function updateOnboardingBuddy(stepIndex) {
    if (!buddyTitle) {
        return;
    }

    const index = Math.max(0, Math.min(stepIndex, onboardingSteps.length - 1));
    const content = onboardingSteps[index];
    activeSetupStepIndex = index;
    applyBuddyContent(content);
}

function showBuddyCelebration(key, { temporary = true } = {}) {
    const celebration = buddyCelebrations[key];
    if (!celebration) {
        return;
    }

    applyBuddyContent(celebration, { celebrate: true, temporary });
}

function updateSetupProgress(index) {
    if (!setupProgressSteps.length) {
        return;
    }

    const maxIndex = setupProgressSteps.length - 1;
    const clampedIndex = Math.max(0, Math.min(index, maxIndex));

    setupProgressSteps.forEach((step, stepIndex) => {
        const isActive = stepIndex === clampedIndex;
        const isCompleted = stepIndex < index;
        step.classList.toggle('active', isActive);
        step.classList.toggle('completed', isCompleted);
        step.setAttribute('aria-current', isActive ? 'step' : 'false');
        step.setAttribute('data-completed', isCompleted);
    });

    if (setupProgressFill) {
        const percent = maxIndex === 0 ? 100 : Math.min(100, (index / maxIndex) * 100);
        setupProgressFill.style.width = `${Math.max(0, percent)}%`;
    }
}

function showSetupStep(index) {
    if (!setupSteps.length) {
        return;
    }

    const targetIndex = Math.max(0, Math.min(index, setupSteps.length - 1));

    setupSteps.forEach((step, stepIndex) => {
        const isActive = stepIndex === targetIndex;
        step.classList.toggle('active', isActive);
        step.style.display = isActive ? 'block' : 'none';
        step.setAttribute('aria-hidden', isActive ? 'false' : 'true');
    });

    activeSetupStepIndex = targetIndex;
    updateSetupProgress(targetIndex);
    updateOnboardingBuddy(targetIndex);
}

function initializeWizard() {
    if (!setupSteps.length) {
        return;
    }

    showSetupStep(activeSetupStepIndex);

    setupProgressSteps.forEach((button, index) => {
        button.addEventListener('click', () => {
            if (index <= activeSetupStepIndex) {
                showSetupStep(index);
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initializeWizard();
});

// IPTScanner Functionality
let iptTorrents = [];
let iptMessageLog = [];

// Initially fetch IPT settings and data when tab is clicked
document.getElementById('iptscanner-tab').addEventListener('click', function() {
    fetchIPTData();
});

// Refresh button click handler
document.getElementById('iptscanner-refresh').addEventListener('click', function() {
    this.disabled = true;
    this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
    fetchIPTData(true).finally(() => {
        this.disabled = false;
        this.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh';
    });
});

// Test IPT login button
document.getElementById('test-ipt-login').addEventListener('click', async function() {
    const uid = document.getElementById('settings-ipt-uid').value;
    const passkey = document.getElementById('settings-ipt-pass').value;
    
    if (!uid || !passkey) {
        showToast('Please enter both UID and Pass cookie values', 'warning');
        return;
    }
    
    // Show loading state
    this.disabled = true;
    this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
    
    try {
        const response = await fetch('/api/iptscanner/test-login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ uid, passkey })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Login successful! Cookies have been saved.', 'success');
        } else {
            showToast('Login failed: ' + (data.error || data.message || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error testing login:', error);
        showToast('Error testing login: ' + error.message, 'error');
    } finally {
        // Reset button state
        this.disabled = false;
        this.innerHTML = 'Test Login';
    }
});

// Test Run IPT Scanner button
document.getElementById('test-run-ipt-scanner').addEventListener('click', async function() {
    try {
        // Show loading state
        this.disabled = true;
        this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        
        const response = await fetch('/api/iptscanner/test-run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('IPT scanner test run completed successfully! Check logs for details.', 'success');
        } else {
            showToast('IPT scanner test run failed: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error running IPT scanner test:', error);
        showToast('Error running IPT scanner: ' + error.message, 'error');
    } finally {
        // Reset button state
        this.disabled = false;
        this.innerHTML = 'Test Run Scanner';
    }
});

// Hook into the settings form to make sure IPT settings are saved
const originalSaveSettings = document.getElementById('save-settings-btn').onclick;
document.getElementById('save-settings-btn').onclick = async function(e) {
    // Collect IPT settings
    const iptSettings = {
        enabled: document.getElementById('settings-ipt-enabled').checked,
        searchTerm: document.getElementById('settings-ipt-search').value,
        checkInterval: document.getElementById('settings-ipt-check-interval').value,
        headless: document.getElementById('settings-ipt-headless').value === 'true',
        dataPath: document.getElementById('settings-ipt-data-path').value,
        userDataDir: document.getElementById('settings-ipt-userdata-dir').value,
        debug: document.getElementById('settings-ipt-debug').checked,
        uid: document.getElementById('settings-ipt-uid').value,
        pass: document.getElementById('settings-ipt-pass').value
    };
    
    // Save IPT settings first
    try {
        const response = await fetch('/api/iptscanner/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(iptSettings)
        });
        
        if (!response.ok) {
            throw new Error('Failed to save IPTScanner settings');
        }
    } catch (error) {
        console.error('Error saving IPTScanner settings:', error);
    }
    
    // Then call the original save settings function
    if (typeof originalSaveSettings === 'function') {
        return originalSaveSettings.call(this, e);
    }
};

// Fetch IPT data from the server
async function fetchIPTData(forceRefresh = false) {
    try {
        // First, load settings
        await loadIPTSettings();
        
        // Then check cookie status
        await checkCookieStatus();
        
        // Then load torrent data
        const response = await fetch(`/api/iptscanner/torrents${forceRefresh ? '?refresh=true' : ''}`);
        const data = await response.json();
        
        if (data.error) {
            logIPTMessage(`Error: ${data.error}`);
            return;
        }
        
        // Update UI with the data
        updateIPTUI(data);
    } catch (error) {
        console.error('Error fetching IPT data:', error);
        logIPTMessage(`Error fetching data: ${error.message}`);
    }
}

// Check if cookies are stored and valid
async function checkCookieStatus() {
    try {
        // First check if the cookies.json file exists and is valid
        const cookieStatusEl = document.getElementById('ipt-cookie-status');
        const cookieStatusTextEl = document.getElementById('ipt-cookie-status-text');
        
        if (!cookieStatusEl || !cookieStatusTextEl) return;
        
        // Show status indicator while checking
        cookieStatusEl.style.display = 'block';
        cookieStatusEl.className = 'alert alert-info mb-3';
        cookieStatusTextEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking cookie status...';
        
        // Check if cookies.json exists by trying to load torrents
        const response = await fetch('/api/iptscanner/torrents?check_only=true');
        const data = await response.json();
        
        if (!data.error) {
            // Cookies exist and work
            cookieStatusEl.className = 'alert alert-success mb-3';
            cookieStatusTextEl.innerHTML = '<i class="fas fa-check-circle"></i> IPTorrents cookies are stored and working.';
        } else if (data.error && data.error.includes('No cookies')) {
            // Cookies don't exist
            cookieStatusEl.className = 'alert alert-warning mb-3';
            cookieStatusTextEl.innerHTML = '<i class="fas fa-exclamation-triangle"></i> No IPTorrents cookies found. Please enter your cookies above.';
        } else {
            // Cookies exist but may be invalid
            cookieStatusEl.className = 'alert alert-danger mb-3';
            cookieStatusTextEl.innerHTML = `<i class="fas fa-times-circle"></i> Cookie error: ${data.error}`;
        }
    } catch (error) {
        console.error('Error checking cookie status:', error);
        
        // Show error in the status
        const cookieStatusEl = document.getElementById('ipt-cookie-status');
        const cookieStatusTextEl = document.getElementById('ipt-cookie-status-text');
        
        if (cookieStatusEl && cookieStatusTextEl) {
            cookieStatusEl.style.display = 'block';
            cookieStatusEl.className = 'alert alert-danger mb-3';
            cookieStatusTextEl.innerHTML = '<i class="fas fa-times-circle"></i> Error checking cookie status.';
        }
    }
}

// Load IPT settings
async function loadIPTSettings() {
    try {
        const response = await fetch('/api/iptscanner/settings');
        const settings = await response.json();
        
        // Update UI with settings
        document.getElementById('ipt-search-term').textContent = settings.searchTerm || 'BL+EL+RPU';
        document.getElementById('ipt-schedule').textContent = cronToHumanReadable(settings.checkInterval);
        document.getElementById('ipt-last-check').textContent = settings.lastUpdateTime 
            ? formatDateTime(settings.lastUpdateTime) 
            : 'Never';
        
        // Update settings form
        document.getElementById('settings-ipt-enabled').checked = settings.enabled !== false;
        document.getElementById('settings-ipt-search').value = settings.searchTerm || 'BL+EL+RPU';
        
        // Convert cron to dropdown selection
        const interval = cronToValue(settings.checkInterval);
        if (interval) {
            document.getElementById('settings-ipt-check-interval').value = interval;
        }
        
        document.getElementById('settings-ipt-headless').value = settings.headless !== false ? 'true' : 'false';
        document.getElementById('settings-ipt-data-path').value = settings.dataPath || '';
        document.getElementById('settings-ipt-userdata-dir').value = settings.userDataDir || '';
        document.getElementById('settings-ipt-debug').checked = settings.debug === true;
        
        // Cookie values should only be shown if explicitly requested for security
        if (settings.uid) document.getElementById('settings-ipt-uid').placeholder = '••••••••• (stored)';
        if (settings.pass) document.getElementById('settings-ipt-pass').placeholder = '••••••••• (stored)';
        
        return settings;
    } catch (error) {
        console.error('Error loading IPT settings:', error);
        return {};
    }
}

// Update IPT UI with torrent data
function updateIPTUI(data) {
    // Update last check time
    if (data.lastCheck) {
        document.getElementById('ipt-last-check').textContent = data.lastCheck ? formatDateTime(data.lastCheck) : 'Never';
    }
    
    // Update search term if available
    if (data.searchTerm) {
        document.getElementById('ipt-search-term').textContent = data.searchTerm;
    }
    
    // Update torrents table
    iptTorrents = data.torrents || [];
    const tableBody = document.getElementById('ipt-torrents-table');
    tableBody.innerHTML = '';
    
    if (iptTorrents.length === 0) {
        document.getElementById('ipt-no-torrents').style.display = 'block';
        tableBody.innerHTML = '<tr><td colspan="6" class="text-center">No torrents found.</td></tr>';
        return;
    }
    
    document.getElementById('ipt-no-torrents').style.display = 'none';
    
    iptTorrents.forEach((torrent, index) => {
        const row = document.createElement('tr');
        row.className = 'align-middle'; // Vertically center all content
        
        // Add a darker highlight class for new torrents that fits the dark theme
        if (torrent.isNew) {
            // Replace table-success with a darker class that fits the dark theme
            row.classList.add('bg-dark', 'border-success');
            // Add a subtle indicator that it's new without changing the background color
            row.style.borderLeft = '4px solid var(--bs-success)';
        }
        
        // Number column
        const numCell = document.createElement('td');
        numCell.textContent = index + 1;
        numCell.className = 'text-center';
        
        // Title column - make it a clickable link
        const titleCell = document.createElement('td');
        titleCell.style.wordBreak = 'break-word';
        
        // Create a link for the title
        const titleLink = document.createElement('a');
        titleLink.href = '#';
        titleLink.className = 'text-decoration-none'; // No underline
        titleLink.innerHTML = torrent.name;
        titleLink.title = "Open torrent details";
        titleLink.style.color = 'var(--bs-body-color)'; // Use the theme's text color
        
        // Add click handler for the title link
        titleLink.addEventListener('click', (e) => {
            e.preventDefault();
            if (torrent.link) {
                window.open(torrent.link, '_blank');
            } else {
                alert('Torrent link not available');
            }
        });
        
        titleCell.appendChild(titleLink);
        
        // Add NEW badge if it's a new torrent
        if (torrent.isNew) {
            const newBadge = document.createElement('span');
            newBadge.className = 'badge bg-success ms-2';
            newBadge.textContent = 'New';
            titleCell.appendChild(newBadge);
        }
        
        // Size column
        const sizeCell = document.createElement('td');
        sizeCell.textContent = torrent.size;
        sizeCell.className = 'text-center';
        
        // Seeds/Leech column
        const seedsCell = document.createElement('td');
        seedsCell.className = 'text-center';
        
        // Use more subdued colors for the seeds/leechers count
        const seedClass = torrent.seeders > 10 ? 'text-success' : 
                         torrent.seeders > 5 ? 'text-warning' : 'text-danger';
        const leechClass = 'text-secondary'; // More subdued color for leechers
        
        seedsCell.innerHTML = `<span class="${seedClass}">${torrent.seeders}</span> / <span class="${leechClass}">${torrent.leechers}</span>`;
        
        // Added column
        const addedCell = document.createElement('td');
        addedCell.textContent = torrent.added;
        addedCell.className = 'text-center';
        
        // Actions column - simplified to just download button
        const actionsCell = document.createElement('td');
        actionsCell.className = 'text-center';
        
        // Add row to table
        row.appendChild(numCell);
        row.appendChild(titleCell);
        row.appendChild(sizeCell);
        row.appendChild(seedsCell);
        row.appendChild(addedCell);
        row.appendChild(actionsCell);
        
        // Add row to table
        tableBody.appendChild(row);
    });
    
    // Update log
    if (data.log && data.log.length > 0) {
        iptMessageLog = data.log;
        updateIPTLog();
    }
}

// Update the IPT log display
function updateIPTLog() {
    const logContainer = document.getElementById('ipt-log');
    
    if (iptMessageLog.length === 0) {
        logContainer.innerHTML = '<div class="text-muted">No activity recorded yet.</div>';
        return;
    }
    
    logContainer.innerHTML = '';
    
    // Show most recent messages first
    const recentMessages = iptMessageLog.slice(-10).reverse();
    
    recentMessages.forEach(message => {
        const msgElement = document.createElement('div');
        msgElement.className = 'log-entry mb-1';
        msgElement.innerHTML = message;
        logContainer.appendChild(msgElement);
    });
}

// Log a message to the IPT log
function logIPTMessage(message) {
    const timestamp = new Date().toLocaleString();
    const formattedMessage = `<span class="text-secondary">[${timestamp}]</span> ${message}`;
    iptMessageLog.push(formattedMessage);
    
    // Limit log size
    if (iptMessageLog.length > 100) {
        iptMessageLog.shift();
    }
    
    updateIPTLog();
}

// Helper function to convert cron to human readable
function cronToHumanReadable(cronExpression) {
    if (!cronExpression) return 'Not set';
    
    // "0 */2 * * *" format (every 2 hours)
    const parts = cronExpression.split(' ');
    
    if (parts[0] === '0' && parts[1].startsWith('*/')) {
        const hours = parseInt(parts[1].substring(2));
        return `Every ${hours} hour${hours > 1 ? 's' : ''}`;
    }
    
    if (parts[0] === '*/') {
        const minutes = parseInt(parts[0].substring(2));
        return `Every ${minutes} minute${minutes > 1 ? 's' : ''}`;
    }
    
    // Default fallback for other schedules
    return cronExpression;
}

// Helper function to convert cron to dropdown value
function cronToValue(cronExpression) {
    if (!cronExpression) return '2hour';
    
    const parts = cronExpression.split(' ');
    
    // Handle "*/n * * * *" format (every n minutes)
    if (parts[0].startsWith('*/')) {
        const minutes = parseInt(parts[0].substring(2));
        if (minutes === 15) return '15min';
        if (minutes === 30) return '30min';
    }
    
    // Handle "0 */n * * *" format (every n hours)
    if (parts[0] === '0' && parts[1].startsWith('*/')) {
        const hours = parseInt(parts[1].substring(2));
        if (hours === 1) return '1hour';
        if (hours === 2) return '2hour';
        if (hours === 6) return '6hour';
        if (hours === 12) return '12hour';
    }
    
    // Handle "0 0 * * *" format (once daily)
    if (parts[0] === '0' && parts[1] === '0') {
        return '1day';
    }
    
    return '2hour'; // Default
}

// Helper function to convert dropdown value to cron
function valueToCron(value) {
    switch (value) {
        case '15min': return '*/15 * * * *';
        case '30min': return '*/30 * * * *';
        case '1hour': return '0 */1 * * *';
        case '2hour': return '0 */2 * * *';
        case '6hour': return '0 */6 * * *';
        case '12hour': return '0 */12 * * *';
        case '1day': return '0 0 * * *';
        default: return '0 */2 * * *';
    }
}

// Fetch rounding preference from settings
async function fetchRoundingPreference() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        window.useWholeNumbers = settings.use_whole_numbers !== false; // Default to true if not specified
        console.log(`Number formatting set to use whole numbers: ${window.useWholeNumbers}`);
    } catch (error) {
        console.error('Failed to fetch number formatting preference:', error);
        // Default to true if we can't fetch the setting
        window.useWholeNumbers = true;
    }
}

// Initial Setup
document.addEventListener('DOMContentLoaded', async () => {
    // Check if the dashboard is already visible (set by server-side script)
    const dashboardAlreadyVisible = window.getComputedStyle(mainDashboard).display === 'block';
    
    if (!dashboardAlreadyVisible) {
        await checkSetup();
    } else {
        console.log('Dashboard already visible, skipping checkSetup call');
        isPolling = true;
    }
    
    loadReports();
    
    // Load settings first
    await loadSettings();
    
    // AFTER settings are loaded, set up Telegram test button
    setupSettingsTelegramTest();
    
    if (isPolling) {
        startPolling();
    }
    
    // Add click event listeners to the stat cards
    setupStatCardClickHandlers();
    
    // Set up clickable settings
    setupClickableSettings();
    
    // Call this function when the page loads
    fetchRoundingPreference();
});

// Set up the Telegram test button in settings
function setupSettingsTelegramTest() {
    console.log('Setting up Telegram test button handler');
    const testBtn = document.getElementById('settings-test-telegram-btn');
    if (!testBtn) {
        console.error('Telegram test button not found in the DOM!');
        return;
    }
    
    console.log('Found Telegram test button, attaching event listener');
    
    // Also make sure Telegram container is visible when enabled
    const telegramEnabledCheckbox = document.getElementById('settings-telegram-enabled');
    const telegramContainer = document.getElementById('settings-telegram-container');
    
    if (telegramEnabledCheckbox && telegramContainer) {
        telegramEnabledCheckbox.addEventListener('change', function() {
            telegramContainer.style.display = this.checked ? 'block' : 'none';
            console.log('Telegram container visibility updated:', this.checked);
        });
    }
    
    testBtn.addEventListener('click', async function() {
        console.log('Telegram test button clicked');
        const token = document.getElementById('settings-telegram-token').value;
        const chatId = document.getElementById('settings-telegram-chat-id').value;
        const successEl = document.getElementById('settings-telegram-success');
        const errorEl = document.getElementById('settings-telegram-error');
        
        // Reset alerts
        if (successEl) successEl.style.display = 'none';
        if (errorEl) errorEl.style.display = 'none';
        
        if (!token || !chatId) {
            if (errorEl) {
                errorEl.textContent = 'Please fill in both Bot Token and Chat ID fields';
                errorEl.style.display = 'block';
            }
            return;
        }
        
        // Show loading state
        this.disabled = true;
        const originalText = this.innerHTML;
        this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
        
        try {
            const response = await fetch('/api/test-telegram', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ token, chat_id: chatId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                if (successEl) {
                    successEl.textContent = 'Test message sent successfully! Check your Telegram.';
                    successEl.style.display = 'block';
                } else {
                    showToast('Test message sent successfully!', 'success');
                }
            } else {
                if (errorEl) {
                    errorEl.textContent = data.error || 'Failed to send test message';
                    errorEl.style.display = 'block';
                } else {
                    showToast('Failed to send test message: ' + (data.error || 'Unknown error'), 'error');
                }
            }
        } catch (error) {
            console.error('Error testing Telegram:', error);
            if (errorEl) {
                errorEl.textContent = 'Connection error: ' + error.message;
                errorEl.style.display = 'block';
            } else {
                showToast('Connection error: ' + error.message, 'error');
            }
        } finally {
            // Reset button state
            this.disabled = false;
            this.innerHTML = originalText;
        }
    });
}

// Check if setup is completed
async function checkSetup() {
    try {
        // Add cache-busting query parameter and ensure we're not using cached responses
        const response = await fetch('/api/check-setup?t=' + Date.now(), {
            method: 'GET',
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Setup status response:', data);
        
        if (data.setup_completed) {
            console.log('Setup is completed, showing dashboard');
            setupWizard.style.display = 'none';
            mainDashboard.style.display = 'block';
            isPolling = true;
        } else {
            console.log('Setup is not completed, showing wizard');
            setupWizard.style.display = 'block';
            mainDashboard.style.display = 'none';
            isPolling = false;
        }
    } catch (error) {
        console.error('Error checking setup:', error);
        // On error, default to showing the dashboard to avoid getting stuck in setup
        setupWizard.style.display = 'none';
        mainDashboard.style.display = 'block';
        isPolling = true;
    }
}

// Setup Wizard Functions
nextStepBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const currentStep = btn.closest('.setup-step');
        const currentIndex = Array.from(setupSteps).indexOf(currentStep);

        if (currentIndex < setupSteps.length - 1) {
            showSetupStep(currentIndex + 1);
        } else if (currentIndex === setupSteps.length - 1) {
            completeSetup();
        }
    });
});

prevStepBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const currentStep = btn.closest('.setup-step');
        const currentIndex = Array.from(setupSteps).indexOf(currentStep);

        if (currentIndex > 0) {
            showSetupStep(currentIndex - 1);
        }
    });
});

// Test Plex Connection
testPlexBtn.addEventListener('click', async () => {
    const plexUrl = document.getElementById('plex-url').value;
    const plexToken = document.getElementById('plex-token').value;
    const libraryName = document.getElementById('library-name').value;
    
    if (!plexUrl || !plexToken || !libraryName) {
        plexError.textContent = 'Please fill in all fields';
        plexError.style.display = 'block';
        plexSuccess.style.display = 'none';
        return;
    }
    
    try {
        // Trim whitespace from all input values
        const plexUrlTrimmed = plexUrl.trim();
        const plexTokenTrimmed = plexToken.trim();
        const libraryNameTrimmed = libraryName.trim();
        
        const response = await fetch('/api/test-connection', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                plex_url: plexUrlTrimmed, 
                plex_token: plexTokenTrimmed, 
                library_name: libraryNameTrimmed 
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            plexSuccess.textContent = `Connection successful! Found ${data.movie_count} movies.`;
            plexSuccess.style.display = 'block';
            plexError.style.display = 'none';

            // Show the Next button
            const nextBtn = testPlexBtn.nextElementSibling;
            nextBtn.style.display = 'inline-block';

            showBuddyCelebration('plexSuccess');
        } else {
            plexError.textContent = data.error || 'Connection failed';
            plexError.style.display = 'block';
            plexSuccess.style.display = 'none';
        }
    } catch (error) {
        plexError.textContent = 'Connection error';
        plexError.style.display = 'block';
        plexSuccess.style.display = 'none';
    }
});

// Toggle Telegram Settings
telegramEnabled.addEventListener('change', () => {
    telegramSettings.style.display = telegramEnabled.checked ? 'block' : 'none';
});

// Test Telegram Settings
testTelegramBtn.addEventListener('click', async () => {
    const token = document.getElementById('telegram-token').value;
    const chatId = document.getElementById('telegram-chat-id').value;
    
    if (!token || !chatId) {
        telegramError.textContent = 'Please fill in all fields';
        telegramError.style.display = 'block';
        telegramSuccess.style.display = 'none';
        return;
    }
    
    try {
        const response = await fetch('/api/test-telegram', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token, chat_id: chatId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            telegramSuccess.textContent = 'Test message sent successfully!';
            telegramSuccess.style.display = 'block';
            telegramError.style.display = 'none';

            showBuddyCelebration('telegramSuccess');
        } else {
            telegramError.textContent = data.error || 'Failed to send test message';
            telegramError.style.display = 'block';
            telegramSuccess.style.display = 'none';
        }
    } catch (error) {
        telegramError.textContent = 'Connection error';
        telegramError.style.display = 'block';
        telegramSuccess.style.display = 'none';
    }
});

// Complete Setup
const completeSetup = async () => {
    const wizardData = {
        plex_url: document.getElementById('plex-url').value.trim(),
        plex_token: document.getElementById('plex-token').value.trim(),
        library_name: document.getElementById('library-name').value.trim(),
        collection_name_all_dv: document.getElementById('collection-dv').value.trim(),
        collection_name_profile7: document.getElementById('collection-p7').value.trim(),
        collection_name_truehd_atmos: document.getElementById('collection-atmos').value.trim(),
        max_reports_size: parseInt(document.getElementById('reports-size').value.trim()),
        telegram_enabled: document.getElementById('telegram-enabled').checked,
        telegram_token: document.getElementById('telegram-token').value.trim(),
        telegram_chat_id: document.getElementById('telegram-chat-id').value.trim(),
        auto_start: 'none'  // Default to none
    };

    updateSetupProgress(setupSteps.length);
    showBuddyCelebration('saving', { temporary: false });

    try {
        // Try the api/setup endpoint first
        let response = await fetch('/api/setup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(wizardData)
        });
        
        // If the first endpoint fails with 404, try the alternative endpoint
        if (response.status === 404) {
            console.log('Endpoint /api/setup not found, trying /api/save-wizard');
            response = await fetch('/api/save-wizard', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(wizardData)
            });
        }
        
        const data = await response.json();
        
        if (data.success) {
            window.location.reload();
        } else {
            showToast('Setup failed: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Setup error: ' + error.message, 'error');
    }
};

// Dashboard Functions
// Start polling for status updates
function startPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
    }
    
    updateStatus();
    pollTimer = setInterval(updateStatus, POLL_INTERVAL);
}

// Stop polling
function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

// Update status from API
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        updateStatusUI(data);
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

// Update UI with status data
function updateStatusUI(data) {
    const status = data.status || {};
    const results = data.results || {};
    const changes = data.collection_changes || {};
    let formattedLastScan = null;
    let formattedNextScan = null;
    let heroCaptionSet = false;

    // Update status badge
    if (results.status) {
        statusBadge.textContent = capitalizeFirstLetter(results.status);
        statusBadge.className = 'status-badge ' + results.status.toLowerCase();

        // Show progress bar if scanning
        if (results.status.toLowerCase() === 'scanning' || results.status.toLowerCase() === 'verifying') {
            scanProgressContainer.style.display = 'block';
            scanProgress.style.width = `${results.scan_progress}%`;
            scanProgress.textContent = `${results.scan_progress}%`;
        } else {
            scanProgressContainer.style.display = 'none';
        }

        if (heroMonitorStatus) {
            const normalized = results.status.toLowerCase();
            heroMonitorStatus.textContent = capitalizeFirstLetter(results.status);
            heroMonitorStatus.className = `hero-status-chip ${normalized || 'idle'}`;

            if (normalized === 'scanning' || normalized === 'verifying') {
                heroMonitorStatus.setAttribute('aria-live', 'assertive');
                if (heroMonitorCaption && typeof results.scan_progress !== 'undefined') {
                    heroMonitorCaption.textContent = `In progress · ${results.scan_progress}% complete`;
                    heroCaptionSet = true;
                }
            } else {
                heroMonitorStatus.setAttribute('aria-live', 'polite');
            }
        }
    } else if (heroMonitorStatus) {
        heroMonitorStatus.textContent = 'Idle';
        heroMonitorStatus.className = 'hero-status-chip idle';
        heroMonitorStatus.setAttribute('aria-live', 'polite');
    }

    // Update stats
    if (typeof results.total !== 'undefined') {
        totalMovies.textContent = results.total;
        if (heroTotalMetric) {
            heroTotalMetric.textContent = Number(results.total).toLocaleString();
        }
    }
    if (typeof results.dv_count !== 'undefined') {
        dvMovies.textContent = results.dv_count;
        if (heroDvMetric) {
            heroDvMetric.textContent = Number(results.dv_count).toLocaleString();
        }
    }
    if (typeof results.p7_count !== 'undefined') {
        p7Movies.textContent = results.p7_count;
        if (heroP7Metric) {
            heroP7Metric.textContent = Number(results.p7_count).toLocaleString();
        }
    }
    if (typeof results.atmos_count !== 'undefined') {
        atmosMovies.textContent = results.atmos_count;
        if (heroAtmosMetric) {
            heroAtmosMetric.textContent = Number(results.atmos_count).toLocaleString();
        }
    }

    // Update scan times
    if (status.last_scan_time) {
        formattedLastScan = formatDateTime(status.last_scan_time);
        lastScanTime.textContent = formattedLastScan;
        if (lastScanTimeMobile) {
            lastScanTimeMobile.textContent = formattedLastScan;
        }
    } else {
        lastScanTime.textContent = 'Never';
        if (lastScanTimeMobile) {
            lastScanTimeMobile.textContent = 'Never';
        }
    }

    // Update next scan time (if in monitor mode)
    if (status.next_scan_time) {
        formattedNextScan = formatDateTime(status.next_scan_time);
        nextScanContainer.style.display = 'inline-flex';
        nextScanTime.textContent = formattedNextScan;
        if (nextScanContainerMobile) {
            nextScanContainerMobile.style.display = 'block';
        }
        if (nextScanTimeMobile) {
            nextScanTimeMobile.textContent = formattedNextScan;
        }
    } else {
        nextScanContainer.style.display = 'none';
        if (nextScanContainerMobile) {
            nextScanContainerMobile.style.display = 'none';
        }
        if (nextScanTimeMobile) {
            nextScanTimeMobile.textContent = '—';
        }
    }

    if (heroMonitorCaption && !heroCaptionSet) {
        heroMonitorCaption.textContent = formattedLastScan
            ? `Last scan · ${formattedLastScan}`
            : 'Waiting for the first scan';
    }

    if (heroMonitorSubcaption) {
        if (results.status && (results.status.toLowerCase() === 'scanning' || results.status.toLowerCase() === 'verifying')) {
            heroMonitorSubcaption.textContent = 'Streaming live progress updates';
        } else if (formattedNextScan) {
            heroMonitorSubcaption.textContent = `Next scan · ${formattedNextScan}`;
        } else if (results.status && results.status.toLowerCase() === 'monitoring') {
            heroMonitorSubcaption.textContent = 'Monitoring is active';
        } else {
            heroMonitorSubcaption.textContent = 'No schedule yet';
        }
    }

    // Update monitor buttons
    if (results.status && results.status.toLowerCase() === 'monitoring') {
        startMonitorBtn.style.display = 'none';
        stopMonitorBtn.style.display = 'block';
    } else {
        startMonitorBtn.style.display = 'block';
        stopMonitorBtn.style.display = 'none';
    }
    
    // Update buttons based on scanning status
    const isScanning = status.is_scanning || false;
    startScanBtn.disabled = isScanning;
    verifyCollectionsBtn.disabled = isScanning;
    startMonitorBtn.disabled = isScanning;
    
    // Update collection changes
    updateChangesUI(changes);
}

// Update collection changes UI with tabs
function updateChangesUI(changes) {
    const addedItems = changes.added_items || [];
    const removedItems = changes.removed_items || [];
    
    if (addedItems.length === 0 && removedItems.length === 0) {
        noChangesAlert.style.display = 'flex';
        changesContainer.style.display = 'none';
        return;
    }

    noChangesAlert.style.display = 'none';
    changesContainer.style.display = 'block';
    
    // Setup collection tabs
    setupCollectionTabs();
    
    // Filter items for current collection tab
    const collectionName = getCollectionNameByTab(currentCollectionTab);
    const filteredAddedItems = addedItems.filter(item => item.collection === collectionName);
    const filteredRemovedItems = removedItems.filter(item => item.collection === collectionName);
    
    // Update the content for the current tab
    updateCollectionTab(filteredAddedItems, filteredRemovedItems);
}

// Setup collection tabs
function setupCollectionTabs() {
    // Clear existing tabs
    while (collectionTabs.firstChild) {
        collectionTabs.removeChild(collectionTabs.firstChild);
    }
    
    // Create tabs for each collection
    const tabs = [
        { id: 'dv', label: 'Dolby Vision' },
        { id: 'p7', label: 'Profile 7 FEL' },
        { id: 'atmos', label: 'TrueHD Atmos' }
    ];
    
    tabs.forEach(tab => {
        const tabEl = document.createElement('button');
        tabEl.className = `collection-tab ${currentCollectionTab === tab.id ? 'active' : ''}`;
        tabEl.dataset.tab = tab.id;
        tabEl.textContent = tab.label;
        tabEl.addEventListener('click', () => switchCollectionTab(tab.id));
        collectionTabs.appendChild(tabEl);
    });
}

// Switch collection tab
function switchCollectionTab(tabId) {
    // Update active tab
    currentCollectionTab = tabId;
    
    // Update tab UI
    const tabs = document.querySelectorAll('.collection-tab');
    tabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabId);
    });
    
    // Fetch and update data for selected tab
    updateStatus();
}

// Update collection tab content
function updateCollectionTab(addedItems, removedItems) {
    // Clear existing content
    while (collectionContents.firstChild) {
        collectionContents.removeChild(collectionContents.firstChild);
    }
    
    // Create sections for added and removed items
    if (addedItems.length > 0) {
        const addedSection = createCollectionSection('Added Items', addedItems, 'added');
        collectionContents.appendChild(addedSection);
    }
    
    if (removedItems.length > 0) {
        const removedSection = createCollectionSection('Removed Items', removedItems, 'removed');
        collectionContents.appendChild(removedSection);
    }
    
    if (addedItems.length === 0 && removedItems.length === 0) {
        const noChangesMsg = document.createElement('div');
        noChangesMsg.className = 'alert alert-info';
        noChangesMsg.textContent = `No changes for ${getCollectionNameByTab(currentCollectionTab)}`;
        collectionContents.appendChild(noChangesMsg);
    }
}

// Create a section for collection items
function createCollectionSection(title, items, type) {
    const section = document.createElement('div');
    section.className = 'collection-section mb-4';
    
    const heading = document.createElement('h5');
    heading.className = 'mb-3';
    heading.textContent = title;
    section.appendChild(heading);
    
    const list = document.createElement('div');
    list.className = 'list-group';
    
    items.forEach(item => {
        const listItem = document.createElement('div');
        listItem.className = `list-group-item ${type === 'added' ? 'list-group-item-success' : 'list-group-item-danger'}`;
        
        // Create title element
        const titleEl = document.createElement('h5');
        titleEl.className = 'mb-1';
        titleEl.textContent = item.title;
        
        // Create meta info container
        const metaInfo = document.createElement('div');
        metaInfo.className = 'movie-meta-info small text-muted';
        
        // Add year if available
        if (item.year) {
            const yearEl = document.createElement('span');
            yearEl.className = 'me-3';
            yearEl.innerHTML = `<i class="fa fa-calendar"></i> ${item.year}`;
            metaInfo.appendChild(yearEl);
        }
        
        // Add file size if available
        if (item.file_size) {
            const sizeEl = document.createElement('span');
            sizeEl.className = 'me-3';
            sizeEl.innerHTML = `<i class="fa fa-file"></i> ${formatFileSize(item.file_size)}`;
            metaInfo.appendChild(sizeEl);
        }
        
        // Add relative time
        const timeEl = document.createElement('span');
        timeEl.className = 'text-end';
        timeEl.innerHTML = `<i class="fa fa-clock"></i> ${formatTimeSince(item.time)}`;
        metaInfo.appendChild(timeEl);
        
        // Append to list item
        listItem.appendChild(titleEl);
        listItem.appendChild(metaInfo);
        list.appendChild(listItem);
    });
    
    section.appendChild(list);
    return section;
}

// Get collection name based on current tab
function getCollectionNameByTab(tabId) {
    const collectionNames = {
        'dv': document.getElementById('settings-collection-dv').value || 'All Dolby Vision',
        'p7': document.getElementById('settings-collection-p7').value || 'DV FEL Profile 7',
        'atmos': document.getElementById('settings-collection-atmos').value || 'TrueHD Atmos'
    };
    
    return collectionNames[tabId];
}

// Format relative time
function formatTimeSince(dateString) {
    const now = new Date();
    const time = new Date(dateString);
    const diff = Math.floor((now - time) / 1000); // difference in seconds
    
    if (diff < 60) return `${diff} seconds ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    if (diff < 2592000) return `${Math.floor(diff / 86400)} days ago`;
    if (diff < 31536000) return `${Math.floor(diff / 2592000)} months ago`;
    return `${Math.floor(diff / 31536000)} years ago`;
}

// Load reports
async function loadReports(all = false) {
    try {
        const url = all ? '/api/reports?full=true' : '/api/reports';
        const response = await fetch(url);
        const reports = await response.json();
        
        reportsTable.innerHTML = '';
        
        if (reports.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `<td colspan="4" class="text-center">No reports available</td>`;
            reportsTable.appendChild(row);
            return;
        }
        
        reports.forEach(report => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="reports-date">${formatDateTime(report.date)}</td>
                <td>${report.filename}</td>
                <td class="reports-size">${formatFileSize(report.size)}</td>
                <td class="reports-actions">
                    <a href="/api/reports/${report.filename}" target="_blank" class="btn btn-sm btn-outline-primary">View</a>
                </td>
            `;
            reportsTable.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading reports:', error);
    }
}

// Load settings
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        if (!response.ok) {
            throw new Error(`HTTP Error: ${response.status}`);
        }
        const settings = await response.json();
        
        // Update Plex connection settings
        document.getElementById('settings-plex-url').value = settings.plex_url || '';
        document.getElementById('settings-plex-token').value = settings.plex_token || '';
        document.getElementById('settings-library-name').value = settings.library_name || '';
        
        // Update collection settings
        document.getElementById('settings-collection-dv').value = settings.collection_name_all_dv || '';
        document.getElementById('settings-collection-p7').value = settings.collection_name_profile7 || '';
        document.getElementById('settings-collection-atmos').value = settings.collection_name_truehd_atmos || '';
        
        // Update collection enable/disable checkboxes
        document.getElementById('settings-enable-dv').checked = settings.collection_enable_dv !== false;
        document.getElementById('settings-enable-p7').checked = settings.collection_enable_p7 !== false;
        document.getElementById('settings-enable-atmos').checked = settings.collection_enable_atmos !== false;
        
        // Update general settings
        document.getElementById('settings-reports-size').value = settings.max_reports_size || 5;
        document.getElementById('settings-scan-frequency').value = settings.scan_frequency || 24;
        
        // Update number formatting setting
        const useWholeNumbersCheckbox = document.getElementById('settings-use-whole-numbers');
        if (useWholeNumbersCheckbox) {
            useWholeNumbersCheckbox.checked = settings.use_whole_numbers !== false;
        }
        
        // Update global setting variable
        window.useWholeNumbers = settings.use_whole_numbers !== false;
        
        // Update Telegram settings
        const telegramEnabled = settings.telegram_enabled || false;
        document.getElementById('settings-telegram-enabled').checked = telegramEnabled;
        document.getElementById('settings-telegram-token').value = settings.telegram_token || '';
        document.getElementById('settings-telegram-chat-id').value = settings.telegram_chat_id || '';
        
        // Show/hide Telegram settings based on enabled state
        const telegramContainer = document.getElementById('settings-telegram-container');
        if (telegramContainer) {
            telegramContainer.style.display = telegramEnabled ? 'block' : 'none';
        }
        
        // Update notification preferences
        document.getElementById('settings-notify-all').checked = settings.telegram_notify_all_updates || false;
        document.getElementById('settings-notify-new').checked = settings.telegram_notify_new_movies !== false;
        document.getElementById('settings-notify-dv').checked = settings.telegram_notify_dv !== false;
        document.getElementById('settings-notify-p7').checked = settings.telegram_notify_p7 !== false;
        document.getElementById('settings-notify-atmos').checked = settings.telegram_notify_atmos !== false;
        
        console.log('Settings loaded successfully');
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

// Event Listeners
// Start Scan
startScanBtn.addEventListener('click', async () => {
    try {
        startScanBtn.disabled = true;
        startScanBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Starting...';
        
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ operation: 'scan' })
        });
        const data = await response.json();
        
        if (!data.success) {
            showToast('Failed to start scan: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Error starting scan: ' + error.message, 'error');
    } finally {
        // Will be re-enabled when status updates
        startScanBtn.innerHTML = '<i class="fa fa-sync-alt"></i> Start Scan';
    }
});

// Verify Collections
verifyCollectionsBtn.addEventListener('click', async () => {
    try {
        verifyCollectionsBtn.disabled = true;
        verifyCollectionsBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Verifying...';
        
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ operation: 'verify' })
        });
        const data = await response.json();
        
        if (!data.success) {
            showToast('Failed to start verification: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Error starting verification: ' + error.message, 'error');
    } finally {
        // Will be re-enabled when status updates
        verifyCollectionsBtn.innerHTML = '<i class="fa fa-check-circle"></i> Verify Collections';
    }
});

// Start Monitor
startMonitorBtn.addEventListener('click', async () => {
    try {
        startMonitorBtn.disabled = true;
        startMonitorBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Starting...';
        
        const response = await fetch('/api/monitor', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ action: 'start' })
        });
        const data = await response.json();
        
        if (!data.success) {
            showToast('Failed to start monitor: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Error starting monitor: ' + error.message, 'error');
    } finally {
        // Will be re-enabled when status updates
        startMonitorBtn.innerHTML = '<i class="fa fa-play-circle"></i> Start Monitor';
    }
});

// Stop Monitor
stopMonitorBtn.addEventListener('click', async () => {
    try {
        stopMonitorBtn.disabled = true;
        stopMonitorBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Stopping...';
        
        const response = await fetch('/api/monitor', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ action: 'stop' })
        });
        const data = await response.json();
        
        if (!data.success) {
            showToast('Failed to stop monitor: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Error stopping monitor: ' + error.message, 'error');
    } finally {
        // Will be re-enabled when status updates
        stopMonitorBtn.innerHTML = '<i class="fa fa-stop-circle"></i> Stop Monitor';
    }
});

// View All Reports
viewAllReports.addEventListener('click', () => {
    loadReports(true);
    viewAllReports.style.display = 'none';
});

// Toggle Telegram Settings in settings form
settingsTelegramEnabled.addEventListener('change', () => {
    settingsTelegramContainer.style.display = settingsTelegramEnabled.checked ? 'block' : 'none';
});

// Save Settings
saveSettingsBtn.addEventListener('click', async () => {
    // Get form values
    const settings = {
        plex_url: document.getElementById('settings-plex-url').value,
        plex_token: document.getElementById('settings-plex-token').value,
        library_name: document.getElementById('settings-library-name').value,
        collection_name_all_dv: document.getElementById('settings-collection-dv').value,
        collection_name_profile7: document.getElementById('settings-collection-p7').value,
        collection_name_truehd_atmos: document.getElementById('settings-collection-atmos').value,
        collection_enable_dv: document.getElementById('settings-enable-dv').checked,
        collection_enable_p7: document.getElementById('settings-enable-p7').checked,
        collection_enable_atmos: document.getElementById('settings-enable-atmos').checked,
        max_reports_size: parseInt(document.getElementById('settings-reports-size').value),
        scan_frequency: parseInt(document.getElementById('settings-scan-frequency').value),
        use_whole_numbers: document.getElementById('settings-use-whole-numbers').checked,
        telegram_enabled: document.getElementById('settings-telegram-enabled').checked,
        telegram_token: document.getElementById('settings-telegram-token').value,
        telegram_chat_id: document.getElementById('settings-telegram-chat-id').value,
        telegram_notify_all_updates: document.getElementById('settings-notify-all').checked,
        telegram_notify_new_movies: document.getElementById('settings-notify-new').checked,
        telegram_notify_dv: document.getElementById('settings-notify-dv').checked,
        telegram_notify_p7: document.getElementById('settings-notify-p7').checked,
        telegram_notify_atmos: document.getElementById('settings-notify-atmos').checked
    };
    
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Settings saved successfully', 'success');
        } else {
            showToast('Error saving settings', 'error');
        }
    } catch (error) {
        showToast('Error saving settings: ' + error.message, 'error');
    }
});

// Reset Settings
resetSettingsBtn.addEventListener('click', async () => {
    const confirmed = await showConfirmToast('Are you sure you want to reset all settings to default values?');
    if (!confirmed) {
        return;
    }
    
    try {
        const response = await fetch('/api/settings/reset', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Settings reset successfully', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showToast('Failed to reset settings: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Error resetting settings: ' + error.message, 'error');
    }
});

// Helper Functions
function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

function formatDateTime(dateString) {
    if (!dateString) return 'Never';
    
    try {
        const date = new Date(dateString);
        // The date object internally keeps the full timestamp precision 
        // but we display a friendlier format
        return date.toLocaleString();
    } catch (e) {
        return dateString;
    }
}

// Format a number for display
function formatNumber(value, decimals = 2) {
    if (typeof value !== 'number') return value;
    if (window.useWholeNumbers) {
        return Math.round(value).toString();
    }
    return value.toFixed(decimals);
}

// Format bitrate for display
function formatBitrate(mbps) {
    if (!mbps || isNaN(mbps)) return 'Unknown';
    
    if (window.useWholeNumbers) {
        return `${Math.round(mbps)} Mbps`;
    } else {
        return `${mbps.toFixed(1)} Mbps`;
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    if (!bytes) return 'Unknown';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    const value = bytes / Math.pow(k, i);
    
    if (window.useWholeNumbers) {
        return Math.round(value) + ' ' + sizes[i];
    } else {
        return value.toFixed(2) + ' ' + sizes[i];
    }
}

// Format and deduplicate audio tracks information
function cleanupAudioTracks(audioString) {
    if (!audioString || audioString === 'Unknown') return 'Unknown';
    
    // Split by commas to get individual tracks
    const tracks = audioString.split(',').map(track => track.trim());
    
    // Remove duplicate entries and clean up
    const uniqueTracks = [];
    const seen = new Set();
    
    tracks.forEach(track => {
        // Special handling for TRUEHD Atmos which should always be prioritized
        if (track.includes('TRUEHD Atmos')) {
            if (!seen.has('TRUEHD Atmos')) {
                uniqueTracks.push('TRUEHD Atmos');
                seen.add('TRUEHD Atmos');
            }
            return;
        }
        
        // Fix repeated codec names like "AC3 AC3 6.1"
        let cleanTrack = track;
        const repeatMatch = track.match(/^(\w+)\s+\1\s+(.+)$/);
        if (repeatMatch) {
            cleanTrack = `${repeatMatch[1]} ${repeatMatch[2]}`;
        }
        
        // Add to results if not already seen
        if (!seen.has(cleanTrack)) {
            uniqueTracks.push(cleanTrack);
            seen.add(cleanTrack);
        }
    });
    
    // Join the unique tracks back together
    return uniqueTracks.join(', ');
}

// Set up click handlers for stat cards
function setupStatCardClickHandlers() {
    const statCards = document.querySelectorAll('.stat-card.clickable');
    statCards.forEach(card => {
        card.addEventListener('click', () => {
            const collection = card.getAttribute('data-collection');
            if (collection) {
                loadMovieList(collection);
            }
        });
    });
}

// Load movie list and show in modal
async function loadMovieList(collection) {
    // Set modal title based on collection type
    const modalTitle = document.getElementById('movieListModalLabel');
    let title = 'Movie List';
    let endpoint = '';
    let showDvProfile = false;
    
    switch(collection) {
        case 'dv':
            title = 'Dolby Vision Movies';
            endpoint = '/api/collection/dvmovies';
            showDvProfile = true;
            break;
        case 'p7':
            title = 'Profile 7 FEL Movies';
            endpoint = '/api/collection/p7movies';
            showDvProfile = false;  // Hide for P7 collection - all are Profile 7 by definition
            break;
        case 'atmos':
            title = 'TrueHD Atmos Movies';
            endpoint = '/api/collection/atmosmovies';
            showDvProfile = true;
            break;
    }
    
    modalTitle.textContent = title;
    
    // Show/hide the DV Profile column based on collection type
    const dvProfileCol = document.querySelector('th.dv-profile-col');
    if (dvProfileCol) {
        dvProfileCol.style.display = showDvProfile ? 'table-cell' : 'none';
    }
    
    // Show loading indicator
    const loadingElement = document.querySelector('.modal-loading');
    const contentElement = document.querySelector('.movie-list-content');
    const noMoviesMsg = document.getElementById('no-movies-message');
    
    if (loadingElement && contentElement) {
        loadingElement.style.display = 'block';
        contentElement.style.display = 'none';
        noMoviesMsg.style.display = 'none';
    }
    
    // Create and show the modal
    const movieModal = new bootstrap.Modal(document.getElementById('movieListModal'));
    movieModal.show();
    
    try {
        // Fetch movies from the API
        const response = await fetch(endpoint);
        const data = await response.json();
        
        if (data.error) {
            console.error('Error loading movies:', data.error);
            noMoviesMsg.textContent = 'Error loading movies: ' + data.error;
            noMoviesMsg.style.display = 'block';
            if (loadingElement) loadingElement.style.display = 'none';
            return;
        }
        
        // Debug logging to check the structure of the received data
        console.log('API response data:', data);
        if (data.movies && data.movies.length > 0) {
            console.log('Sample movie data:', data.movies[0]);
        }
        
        // Store the movies in a global variable for sorting
        window.movieListData = data.movies || [];
        
        // Initialize sorting state - always reset to title sort when opening a new collection
        window.sortConfig = {
            column: 'title',
            direction: 'asc'
        };
        
        // Reset all sort indicators
        document.querySelectorAll('.sortable').forEach(col => {
            col.classList.remove('sort-asc', 'sort-desc');
            const icon = col.querySelector('i');
            if (icon) {
                icon.className = 'fa fa-sort';
            }
        });
        
        // Set initial sort indicator 
        const titleColumn = document.querySelector('.sortable[data-sort="title"]');
        if (titleColumn) {
            titleColumn.classList.add('sort-asc');
            const icon = titleColumn.querySelector('i');
            if (icon) {
                icon.className = 'fa fa-sort-up';
            }
        }
        
        // Set up sort column click handlers
        setupSortColumns();
        
        // Display the movies with initial sort (alphabetical by title)
        displayMovieList(window.movieListData, showDvProfile);
        
        // Show content
        if (contentElement) contentElement.style.display = 'block';
        
    } catch (error) {
        console.error('Error fetching movie list:', error);
        noMoviesMsg.textContent = 'Error loading movies: ' + error.message;
        noMoviesMsg.style.display = 'block';
    } finally {
        // Hide loading indicator
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
    }
}

// Setup sort column click handlers
function setupSortColumns() {
    const sortableColumns = document.querySelectorAll('.sortable');
    
    // Initial sort indicators
    if (window.sortConfig) {
        const activeColumn = document.querySelector(`.sortable[data-sort="${window.sortConfig.column}"]`);
        if (activeColumn) {
            activeColumn.classList.add(window.sortConfig.direction === 'asc' ? 'sort-asc' : 'sort-desc');
        }
    }
    
    sortableColumns.forEach(column => {
        column.addEventListener('click', () => {
            const sortColumn = column.getAttribute('data-sort');
            
            // Toggle sort direction if clicking the same column
            if (window.sortConfig.column === sortColumn) {
                window.sortConfig.direction = window.sortConfig.direction === 'asc' ? 'desc' : 'asc';
            } else {
                window.sortConfig.column = sortColumn;
                window.sortConfig.direction = 'asc';
            }
            
            // Update visual indicators
            sortableColumns.forEach(col => {
                col.classList.remove('sort-asc', 'sort-desc');
                // Remove the icons too
                const icons = col.querySelectorAll('i');
                icons.forEach(icon => {
                    icon.className = 'fa fa-sort';
                });
            });
            
            // Add appropriate sort class
            column.classList.add(window.sortConfig.direction === 'asc' ? 'sort-asc' : 'sort-desc');
            
            // Update icon in the column header
            const icon = column.querySelector('i');
            if (icon) {
                icon.className = window.sortConfig.direction === 'asc' 
                    ? 'fa fa-sort-up' 
                    : 'fa fa-sort-down';
            }
            
            // Console log to debug
            console.log(`Sorting by ${window.sortConfig.column} in ${window.sortConfig.direction} order`);
            
            // Re-sort and display the list
            const showDvProfile = document.querySelector('th.dv-profile-col').style.display !== 'none';
            displayMovieList(window.movieListData, showDvProfile);
        });
    });
}

// Display the movie list with current sort configuration
function displayMovieList(movies, showDvProfile) {
    if (!movies || !Array.isArray(movies)) {
        console.error('Invalid movies data:', movies);
        return;
    }
    
    // Clear existing table rows
    const tableBody = document.getElementById('movie-list-table');
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    if (movies.length === 0) {
        document.getElementById('no-movies-message').style.display = 'block';
        return;
    }
    
    // Debug log to see data structure
    console.log('Sample movie data:', movies[0]);
    
    // Sort the movies based on current sort configuration
    const sortedMovies = [...movies].sort((a, b) => {
        let aValue, bValue;
        
        switch (window.sortConfig.column) {
            case 'title':
                aValue = (a.title || '').toLowerCase();
                bValue = (b.title || '').toLowerCase();
                break;
            case 'year':
                // Handle year sorting
                aValue = parseInt(a.year) || parseInt(a.extra_data?.year) || 0;
                bValue = parseInt(b.year) || parseInt(b.extra_data?.year) || 0;
                break;
            case 'profile':
                aValue = a.dv_profile || '0';
                bValue = b.dv_profile || '0';
                break;
            case 'audio':
                aValue = a.audio || '';
                bValue = b.audio || '';
                break;
            case 'bitrate':
                // Get numeric bitrate for sorting
                aValue = parseFloat(a.bitrate) || parseFloat(a.extra_data?.video_bitrate_raw) || 0;
                bValue = parseFloat(b.bitrate) || parseFloat(b.extra_data?.video_bitrate_raw) || 0;
                break;
            case 'size':
                // Handle size sorting
                aValue = parseInt(a.file_size) || parseInt(a.extra_data?.file_size) || 0;
                bValue = parseInt(b.file_size) || parseInt(b.extra_data?.file_size) || 0;
                break;
            case 'added':
                aValue = a.added_at || '';
                bValue = b.added_at || '';
                break;
            default:
                aValue = a.title.toLowerCase();
                bValue = b.title.toLowerCase();
        }
        
        // Compare based on sort direction - fix to handle equality properly
        if (window.sortConfig.direction === 'asc') {
            if (aValue < bValue) return -1;
            if (aValue > bValue) return 1;
            return 0;
        } else {
            if (aValue > bValue) return -1;
            if (aValue < bValue) return 1;
            return 0;
        }
    });
    
    // Add each movie to the table
    sortedMovies.forEach(movie => {
        const row = document.createElement('tr');
        
        // Extract year - handle multiple possible locations
        let yearValue = '';
        // Try direct year property first 
        if (movie.year) {
            yearValue = movie.year;
        } 
        // Then try extra_data.year
        else if (movie.extra_data && movie.extra_data.year) {
            yearValue = movie.extra_data.year;
        }
        // Make sure year is just a 4-digit number
        if (yearValue && String(yearValue).length > 4) {
            // Try to extract year from ISO date or similar
            try {
                const date = new Date(yearValue);
                yearValue = date.getFullYear();
            } catch (e) {
                // If parsing fails, use the first 4 characters if they're all digits
                const yearMatch = String(yearValue).match(/^\d{4}/);
                if (yearMatch) {
                    yearValue = yearMatch[0];
                }
            }
        }
        
        // Format file size
        let fileSize = 'Unknown';
        if (movie.file_size) {
            fileSize = formatFileSize(movie.file_size);
        } else if (movie.extra_data && movie.extra_data.file_size) {
            fileSize = formatFileSize(movie.extra_data.file_size);
        }
        
        // Get audio tracks
        let audioValue = movie.audio || 'Unknown';
        // Apply cleanup to format and deduplicate audio tracks
        audioValue = cleanupAudioTracks(audioValue);
        
        // Format bitrate
        let bitrateValue = 'Unknown';
        if (movie.bitrate && !movie.bitrate.includes('Unknown')) {
            // Extract numeric value if it's a string like "45.5 Mbps"
            const match = movie.bitrate.match(/(\d+\.?\d*)/);
            if (match) {
                bitrateValue = formatBitrate(parseFloat(match[1]));
            } else {
                bitrateValue = movie.bitrate;
            }
        } else if (movie.extra_data && movie.extra_data.video_bitrate_raw) {
            bitrateValue = formatBitrate(movie.extra_data.video_bitrate_raw);
        }
        
        // Format date from ISO string to readable format
        let formattedDate = '';
        if (movie.added_at) {
            const date = new Date(movie.added_at);
            formattedDate = date.toLocaleDateString();
        }
        
        // Create the row with all columns in the correct order
        const titleCell = document.createElement('td');
        titleCell.textContent = movie.title || '';
        
        const yearCell = document.createElement('td');
        yearCell.textContent = yearValue;
        
        const profileCell = document.createElement('td');
        profileCell.textContent = movie.dv_profile || '';
        profileCell.style.display = showDvProfile ? 'table-cell' : 'none';
        profileCell.className = 'dv-profile-col';
        
        const audioCell = document.createElement('td');
        audioCell.textContent = audioValue;
        audioCell.className = 'audio-col';
        
        const bitrateCell = document.createElement('td');
        bitrateCell.textContent = bitrateValue;
        bitrateCell.className = 'bitrate-col';
        
        const sizeCell = document.createElement('td');
        sizeCell.textContent = fileSize;
        sizeCell.className = 'size-col';
        
        const dateCell = document.createElement('td');
        dateCell.textContent = formattedDate;
        
        row.appendChild(titleCell);
        row.appendChild(yearCell);
        row.appendChild(profileCell);
        row.appendChild(audioCell);
        row.appendChild(bitrateCell);
        row.appendChild(sizeCell);
        row.appendChild(dateCell);
        
        tableBody.appendChild(row);
    });
}

// Toast notification functions to replace browser alerts
function showToast(message, type = 'info') {
    // Generate a unique ID for the toast
    const toastId = 'toast-' + Date.now();
    
    // Determine toast color based on type
    let bgClass = 'bg-primary';
    let icon = 'info-circle';
    
    if (type === 'success') {
        bgClass = 'bg-success';
        icon = 'check-circle';
    } else if (type === 'error') {
        bgClass = 'bg-danger';
        icon = 'exclamation-circle';
    } else if (type === 'warning') {
        bgClass = 'bg-warning';
        icon = 'exclamation-triangle';
    }
    
    // Create toast HTML
    const toastHtml = `
        <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header ${bgClass} text-white">
                <i class="fas fa-${icon} me-2"></i>
                <strong class="me-auto">${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    // Add toast to container
    const toastContainer = document.querySelector('.toast-container');
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    // Initialize and show the toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 5000
    });
    
    toast.show();
    
    // Return the toast instance in case we need to reference it later
    return toast;
}

// Confirmation toast that returns a Promise
function showConfirmToast(message) {
    return new Promise((resolve) => {
        // Generate a unique ID for the toast
        const toastId = 'confirm-toast-' + Date.now();
        
        // Create toast HTML with confirmation buttons
        const toastHtml = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="false">
                <div class="toast-header bg-primary text-white">
                    <i class="fas fa-question-circle me-2"></i>
                    <strong class="me-auto">Confirmation</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                    <div class="mt-2 pt-2 border-top d-flex justify-content-end">
                        <button type="button" class="btn btn-secondary btn-sm me-2 confirm-no">No</button>
                        <button type="button" class="btn btn-primary btn-sm confirm-yes">Yes</button>
                    </div>
                </div>
            </div>
        `;
        
        // Add toast to container
        const toastContainer = document.querySelector('.toast-container');
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        // Initialize the toast
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement);
        
        // Add event listeners for buttons
        const confirmYesBtn = toastElement.querySelector('.confirm-yes');
        const confirmNoBtn = toastElement.querySelector('.confirm-no');
        const closeBtn = toastElement.querySelector('.btn-close');
        
        confirmYesBtn.addEventListener('click', () => {
            toast.hide();
            resolve(true);
        });
        
        confirmNoBtn.addEventListener('click', () => {
            toast.hide();
            resolve(false);
        });
        
        closeBtn.addEventListener('click', () => {
            resolve(false);
        });
        
        // Show the toast
        toast.show();
    });
}

// Set up clickable settings
function setupClickableSettings() {
    // Add style for clickable settings
    const style = document.createElement('style');
    style.textContent = `
        .clickable-setting {
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .clickable-setting:hover {
            color: #63b3ed !important;
        }
        .clickable-setting:hover .fa-edit {
            color: #63b3ed !important;
        }
        .interval-option {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            padding: 8px;
            border-radius: 4px;
        }
        .interval-option:hover {
            background-color: rgba(255, 255, 255, 0.05);
        }
        .interval-option input {
            margin-right: 10px;
        }
    `;
    document.head.appendChild(style);
    
    // Add click handler for schedule interval
    const scheduleEl = document.getElementById('ipt-schedule');
    if (scheduleEl) {
        scheduleEl.addEventListener('click', () => {
            openIntervalEditModal();
        });
    }
}

// Open interval edit modal
function openIntervalEditModal() {
    // Create modal HTML
    const modalId = 'interval-edit-modal';
    
    // Check if modal already exists
    if (document.getElementById(modalId)) {
        // Just show the existing modal
        const existingModal = new bootstrap.Modal(document.getElementById(modalId));
        existingModal.show();
        return;
    }
    
    // Create the modal
    const modalHtml = `
        <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}-label" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content bg-dark">
                    <div class="modal-header">
                        <h5 class="modal-title" id="${modalId}-label">Edit Check Interval</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <p>Choose how often to check for new torrents:</p>
                        
                        <div class="interval-options">
                            <!-- Minutes -->
                            <div class="interval-option">
                                <input type="radio" id="interval-15min" name="interval-type" value="15min">
                                <label for="interval-15min">Every 15 minutes</label>
                            </div>
                            <div class="interval-option">
                                <input type="radio" id="interval-30min" name="interval-type" value="30min">
                                <label for="interval-30min">Every 30 minutes</label>
                            </div>
                            
                            <!-- Hours -->
                            <div class="interval-option">
                                <input type="radio" id="interval-1hour" name="interval-type" value="1hour">
                                <label for="interval-1hour">Every hour</label>
                            </div>
                            <div class="interval-option">
                                <input type="radio" id="interval-2hour" name="interval-type" value="2hour">
                                <label for="interval-2hour">Every 2 hours</label>
                            </div>
                            <div class="interval-option">
                                <input type="radio" id="interval-6hour" name="interval-type" value="6hour">
                                <label for="interval-6hour">Every 6 hours</label>
                            </div>
                            <div class="interval-option">
                                <input type="radio" id="interval-12hour" name="interval-type" value="12hour">
                                <label for="interval-12hour">Every 12 hours</label>
                            </div>
                            
                            <!-- Days -->
                            <div class="interval-option">
                                <input type="radio" id="interval-1day" name="interval-type" value="1day">
                                <label for="interval-1day">Once daily</label>
                            </div>
                            
                            <!-- Custom -->
                            <div class="interval-option">
                                <input type="radio" id="interval-custom" name="interval-type" value="custom">
                                <label for="interval-custom">Custom interval:</label>
                                <div class="input-group ms-2">
                                    <input type="number" id="custom-interval-value" class="form-control form-control-sm" min="1" value="2">
                                    <select id="custom-interval-unit" class="form-select form-select-sm">
                                        <option value="minute">minutes</option>
                                        <option value="hour" selected>hours</option>
                                        <option value="day">days</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" id="save-interval-btn">Save Changes</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Append modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Get currently selected interval and set the radio button
    const selectEl = document.getElementById('settings-ipt-check-interval');
    const currentInterval = selectEl ? selectEl.value : '2hour';
    
    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById(modalId));
    modal.show();
    
    // Set current selection
    const radioEl = document.getElementById(`interval-${currentInterval}`);
    if (radioEl) {
        radioEl.checked = true;
    } else {
        // If not found, select custom and set values
        const customRadio = document.getElementById('interval-custom');
        customRadio.checked = true;
        
        // Try to parse the custom value
        try {
            const cronVal = document.getElementById('ipt-schedule').textContent.trim();
            if (cronVal.toLowerCase().includes('hour')) {
                const hours = parseInt(cronVal.match(/\d+/)[0]);
                document.getElementById('custom-interval-value').value = hours;
                document.getElementById('custom-interval-unit').value = 'hour';
            } else if (cronVal.toLowerCase().includes('minute')) {
                const minutes = parseInt(cronVal.match(/\d+/)[0]);
                document.getElementById('custom-interval-value').value = minutes;
                document.getElementById('custom-interval-unit').value = 'minute';
            } else if (cronVal.toLowerCase().includes('day')) {
                const days = parseInt(cronVal.match(/\d+/)[0]) || 1;
                document.getElementById('custom-interval-value').value = days;
                document.getElementById('custom-interval-unit').value = 'day';
            }
        } catch (e) {
            console.error('Error parsing custom interval:', e);
        }
    }
    
    // Add save button handler
    document.getElementById('save-interval-btn').addEventListener('click', async () => {
        // Get selected interval
        let intervalValue;
        const selectedRadio = document.querySelector('input[name="interval-type"]:checked');
        
        if (selectedRadio.value === 'custom') {
            // Get custom interval
            const value = document.getElementById('custom-interval-value').value;
            const unit = document.getElementById('custom-interval-unit').value;
            
            // Convert to cron
            let cronValue;
            if (unit === 'minute') {
                // Don't allow values less than 5 minutes to avoid rate limiting
                const minutes = Math.max(5, parseInt(value));
                cronValue = `*/${minutes} * * * *`;
            } else if (unit === 'hour') {
                const hours = parseInt(value);
                if (hours === 1) {
                    cronValue = '0 */1 * * *';
                } else {
                    cronValue = `0 */${hours} * * *`;
                }
            } else if (unit === 'day') {
                const days = parseInt(value);
                if (days === 1) {
                    cronValue = '0 0 * * *';
                } else {
                    cronValue = `0 0 */${days} * *`;
                }
            }
            
            intervalValue = cronValue;
        } else {
            // Use standard interval
            intervalValue = valueToCron(selectedRadio.value);
            
            // Update dropdown in settings
            const selectEl = document.getElementById('settings-ipt-check-interval');
            if (selectEl) {
                selectEl.value = selectedRadio.value;
            }
        }
        
        // Save the new interval
        try {
            // Get current settings
            const response = await fetch('/api/iptscanner/settings');
            const settings = await response.json();
            
            // Update interval
            settings.checkInterval = intervalValue;
            
            // Save settings
            const saveResponse = await fetch('/api/iptscanner/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settings)
            });
            
            if (saveResponse.ok) {
                // Update UI
                document.getElementById('ipt-schedule').textContent = cronToHumanReadable(intervalValue);
                // Add back the edit icon
                document.getElementById('ipt-schedule').innerHTML += ' <i class="fas fa-edit ms-1 text-secondary"></i>';
                showToast('Interval updated successfully!', 'success');
            } else {
                showToast('Failed to update interval', 'error');
            }
            
            // Close modal
            modal.hide();
            
            // Refresh data
            fetchIPTData();
        } catch (error) {
            console.error('Error saving interval:', error);
            showToast('Error saving interval: ' + error.message, 'error');
        }
    });
}

// Add direct click handler for Telegram test button
document.addEventListener('DOMContentLoaded', () => {
    // This is a backup event handler in case the setupSettingsTelegramTest doesn't work
    const telegramTestBtn = document.getElementById('settings-test-telegram-btn');
    if (telegramTestBtn) {
        console.log('Adding backup click handler for Telegram test button');
        
        telegramTestBtn.onclick = async function() {
            console.log('Telegram test button clicked (backup handler)');
            const token = document.getElementById('settings-telegram-token').value;
            const chatId = document.getElementById('settings-telegram-chat-id').value;
            const successEl = document.getElementById('settings-telegram-success');
            const errorEl = document.getElementById('settings-telegram-error');
            
            // Reset alerts
            if (successEl) successEl.style.display = 'none';
            if (errorEl) errorEl.style.display = 'none';
            
            if (!token || !chatId) {
                if (errorEl) {
                    errorEl.textContent = 'Please fill in both Bot Token and Chat ID fields';
                    errorEl.style.display = 'block';
                }
                return;
            }
            
            // Show loading state
            this.disabled = true;
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
            
            try {
                const response = await fetch('/api/test-telegram', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ token, chat_id: chatId })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    if (successEl) {
                        successEl.textContent = 'Test message sent successfully! Check your Telegram.';
                        successEl.style.display = 'block';
                    } else {
                        showToast('Test message sent successfully!', 'success');
                    }
                } else {
                    if (errorEl) {
                        errorEl.textContent = data.error || 'Failed to send test message';
                        errorEl.style.display = 'block';
                    } else {
                        showToast('Failed to send test message: ' + (data.error || 'Unknown error'), 'error');
                    }
                }
            } catch (error) {
                console.error('Error testing Telegram:', error);
                if (errorEl) {
                    errorEl.textContent = 'Connection error: ' + error.message;
                    errorEl.style.display = 'block';
                } else {
                    showToast('Connection error: ' + error.message, 'error');
                }
            } finally {
                // Reset button state
                this.disabled = false;
                this.innerHTML = originalText;
            }
        };
    }
});
