-- FELScanner PostgreSQL Database Schema
-- Version: 2.0.0

-- Create database extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- MOVIES TABLE
-- Core movie metadata from Plex library scans
-- ============================================================================
CREATE TABLE IF NOT EXISTS movies (
    id SERIAL PRIMARY KEY,
    rating_key VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    year INTEGER,
    dv_profile VARCHAR(10),                  -- '4', '5', '7', '8', '9', NULL for non-DV
    dv_fel BOOLEAN DEFAULT FALSE,            -- TRUE if Profile 7 with FEL
    has_atmos BOOLEAN DEFAULT FALSE,         -- TRUE if TrueHD Atmos
    has_truehd BOOLEAN DEFAULT FALSE,        -- TRUE if any TrueHD audio
    resolution VARCHAR(20),                  -- '2160p', '1080p', '720p', etc.
    bitrate_mbps DECIMAL(10, 2),            -- Video bitrate in Mbps
    file_size_gb DECIMAL(10, 2),            -- File size in GB
    audio_tracks JSONB,                      -- Array of audio track metadata
    video_codec VARCHAR(50),                 -- 'hevc', 'h264', 'av1', etc.
    extra_data JSONB,                        -- Additional metadata (collections, versions, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_scanned_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for movies table
CREATE INDEX idx_movies_rating_key ON movies(rating_key);
CREATE INDEX idx_movies_title ON movies USING btree (title);
CREATE INDEX idx_movies_year ON movies(year);
CREATE INDEX idx_movies_dv_profile ON movies(dv_profile);
CREATE INDEX idx_movies_dv_fel ON movies(dv_fel) WHERE dv_fel = TRUE;
CREATE INDEX idx_movies_has_atmos ON movies(has_atmos) WHERE has_atmos = TRUE;
CREATE INDEX idx_movies_has_truehd ON movies(has_truehd) WHERE has_truehd = TRUE;
CREATE INDEX idx_movies_extra_data ON movies USING GIN(extra_data);
CREATE INDEX idx_movies_audio_tracks ON movies USING GIN(audio_tracks);
-- Composite index for collection queries
CREATE INDEX idx_movies_dv_profile_fel ON movies(dv_profile, dv_fel);
CREATE INDEX idx_movies_updated_at ON movies(updated_at DESC);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_movies_updated_at BEFORE UPDATE ON movies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- PENDING_DOWNLOADS TABLE
-- Tracks download approval requests awaiting user action
-- ============================================================================
CREATE TABLE IF NOT EXISTS pending_downloads (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(100) UNIQUE NOT NULL,
    movie_id INTEGER REFERENCES movies(id) ON DELETE SET NULL,
    movie_title VARCHAR(500) NOT NULL,
    year INTEGER,
    torrent_url TEXT NOT NULL,
    torrent_hash VARCHAR(100),
    magnet_link TEXT,
    target_folder TEXT,
    quality_type VARCHAR(50),               -- 'fel', 'dv', 'hdr'
    upgrade_reason TEXT,                     -- Human-readable upgrade description
    status VARCHAR(20) DEFAULT 'pending',    -- 'pending', 'approved', 'declined', 'expired', 'completed', 'error'
    telegram_message_id BIGINT,
    download_data JSONB,                     -- Full request details
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    approved_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB
);

-- Indexes for pending_downloads
CREATE INDEX idx_pending_status ON pending_downloads(status);
CREATE INDEX idx_pending_created ON pending_downloads(created_at DESC);
CREATE INDEX idx_pending_expires ON pending_downloads(expires_at);
CREATE INDEX idx_pending_movie_id ON pending_downloads(movie_id);
CREATE INDEX idx_pending_request_id ON pending_downloads(request_id);
-- Partial index for active pending downloads
CREATE INDEX idx_pending_active ON pending_downloads(created_at DESC)
    WHERE status = 'pending' AND expires_at > NOW();

-- ============================================================================
-- DOWNLOAD_HISTORY TABLE
-- Audit trail for all download approval actions
-- ============================================================================
CREATE TABLE IF NOT EXISTS download_history (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(100) NOT NULL,
    movie_id INTEGER REFERENCES movies(id) ON DELETE SET NULL,
    movie_title VARCHAR(500),
    quality_type VARCHAR(50),
    torrent_hash VARCHAR(100),
    status VARCHAR(20),                      -- 'downloading', 'completed', 'error'
    action_type VARCHAR(20),                 -- 'approved', 'declined', 'expired', 'completed', 'error'
    user_action BOOLEAN DEFAULT FALSE,       -- TRUE if user initiated
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    duration_seconds INTEGER,
    error_message TEXT,
    metadata JSONB
);

-- Indexes for download_history
CREATE INDEX idx_history_movie_id ON download_history(movie_id);
CREATE INDEX idx_history_request_id ON download_history(request_id);
CREATE INDEX idx_history_completed_at ON download_history(completed_at DESC);
CREATE INDEX idx_history_action_type ON download_history(action_type);
CREATE INDEX idx_history_metadata ON download_history USING GIN(metadata);

-- ============================================================================
-- SCAN_HISTORY TABLE
-- Tracks all scan operations for analytics and debugging
-- ============================================================================
CREATE TABLE IF NOT EXISTS scan_history (
    id SERIAL PRIMARY KEY,
    scan_type VARCHAR(20) NOT NULL,          -- 'full', 'verify', 'monitor', 'incremental'
    status VARCHAR(20) NOT NULL,             -- 'running', 'completed', 'error', 'cancelled'
    total_movies INTEGER DEFAULT 0,
    dv_count INTEGER DEFAULT 0,
    p7_count INTEGER DEFAULT 0,
    fel_count INTEGER DEFAULT 0,
    atmos_count INTEGER DEFAULT 0,
    truehd_count INTEGER DEFAULT 0,
    changes_detected INTEGER DEFAULT 0,
    movies_added INTEGER DEFAULT 0,
    movies_removed INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    error_message TEXT,
    metadata JSONB
);

-- Indexes for scan_history
CREATE INDEX idx_scan_history_started_at ON scan_history(started_at DESC);
CREATE INDEX idx_scan_history_scan_type ON scan_history(scan_type);
CREATE INDEX idx_scan_history_status ON scan_history(status);
CREATE INDEX idx_scan_history_completed_at ON scan_history(completed_at DESC);

-- Trigger to auto-calculate duration
CREATE OR REPLACE FUNCTION calculate_scan_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND NEW.started_at IS NOT NULL THEN
        NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at))::INTEGER;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_scan_duration BEFORE UPDATE ON scan_history
    FOR EACH ROW EXECUTE FUNCTION calculate_scan_duration();

-- ============================================================================
-- SETTINGS TABLE
-- Key-value store for application configuration (replaces settings.json)
-- ============================================================================
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    category VARCHAR(50),                    -- 'plex', 'telegram', 'qbittorrent', 'radarr', 'general'
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by VARCHAR(100)
);

-- Index for settings
CREATE INDEX idx_settings_category ON settings(category);
CREATE INDEX idx_settings_updated_at ON settings(updated_at DESC);

-- Trigger for settings updated_at
CREATE TRIGGER update_settings_updated_at BEFORE UPDATE ON settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- CONNECTION_STATUS TABLE
-- Persists service health check results
-- ============================================================================
CREATE TABLE IF NOT EXISTS connection_status (
    service VARCHAR(50) PRIMARY KEY,         -- 'plex', 'telegram', 'qbittorrent', 'radarr', 'iptorrents'
    status VARCHAR(20),                      -- 'connected', 'disconnected', 'error', 'unknown'
    message TEXT,
    last_check_at TIMESTAMP WITH TIME ZONE,
    next_check_at TIMESTAMP WITH TIME ZONE,
    check_interval_minutes INTEGER,
    consecutive_failures INTEGER DEFAULT 0,
    metadata JSONB                           -- Service-specific data (version, counts, etc.)
);

-- Index for connection_status
CREATE INDEX idx_connection_last_check ON connection_status(last_check_at DESC);

-- ============================================================================
-- METADATA_CACHE TABLE
-- Replaces metadata-cache.json for movie detail caching
-- ============================================================================
CREATE TABLE IF NOT EXISTS metadata_cache (
    rating_key VARCHAR(50) PRIMARY KEY,
    summary_data JSONB,                      -- Basic movie info from Plex
    ffprobe_data JSONB,                      -- Detailed stream analysis
    last_refreshed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    refresh_count INTEGER DEFAULT 1,
    cache_version INTEGER DEFAULT 1
);

-- Index for metadata_cache
CREATE INDEX idx_metadata_last_refreshed ON metadata_cache(last_refreshed_at DESC);
CREATE INDEX idx_metadata_rating_key ON metadata_cache(rating_key);

-- ============================================================================
-- COLLECTION_CHANGES TABLE (NEW)
-- Tracks collection membership changes for audit/rollback
-- ============================================================================
CREATE TABLE IF NOT EXISTS collection_changes (
    id SERIAL PRIMARY KEY,
    collection_name VARCHAR(200) NOT NULL,
    movie_id INTEGER REFERENCES movies(id) ON DELETE CASCADE,
    rating_key VARCHAR(50),
    movie_title VARCHAR(500),
    change_type VARCHAR(20) NOT NULL,        -- 'added', 'removed'
    reason TEXT,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    scan_id INTEGER REFERENCES scan_history(id) ON DELETE SET NULL
);

-- Indexes for collection_changes
CREATE INDEX idx_collection_changes_collection ON collection_changes(collection_name);
CREATE INDEX idx_collection_changes_movie_id ON collection_changes(movie_id);
CREATE INDEX idx_collection_changes_changed_at ON collection_changes(changed_at DESC);
CREATE INDEX idx_collection_changes_scan_id ON collection_changes(scan_id);

-- ============================================================================
-- NOTIFICATION_QUEUE TABLE (NEW)
-- Persists Telegram notification queue for reliability
-- ============================================================================
CREATE TABLE IF NOT EXISTS notification_queue (
    id SERIAL PRIMARY KEY,
    notification_type VARCHAR(50),           -- 'scan_complete', 'download_approved', 'error', etc.
    message TEXT NOT NULL,
    priority INTEGER DEFAULT 5,              -- 1=highest, 10=lowest
    status VARCHAR(20) DEFAULT 'pending',    -- 'pending', 'sent', 'failed'
    telegram_message_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sent_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB
);

-- Indexes for notification_queue
CREATE INDEX idx_notification_status ON notification_queue(status);
CREATE INDEX idx_notification_priority ON notification_queue(priority, created_at);
CREATE INDEX idx_notification_created ON notification_queue(created_at DESC);
-- Partial index for pending notifications
CREATE INDEX idx_notification_pending ON notification_queue(priority, created_at)
    WHERE status = 'pending';

-- ============================================================================
-- SCHEDULED_TASKS TABLE (NEW)
-- Tracks APScheduler job state for persistence
-- ============================================================================
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id VARCHAR(100) PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,          -- 'scan', 'monitor', 'connection_check', 'cleanup'
    status VARCHAR(20),                      -- 'scheduled', 'running', 'completed', 'failed'
    next_run_time TIMESTAMP WITH TIME ZONE,
    last_run_time TIMESTAMP WITH TIME ZONE,
    run_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    avg_duration_seconds DECIMAL(10, 2),
    metadata JSONB
);

-- Indexes for scheduled_tasks
CREATE INDEX idx_scheduled_next_run ON scheduled_tasks(next_run_time);
CREATE INDEX idx_scheduled_task_type ON scheduled_tasks(task_type);

-- ============================================================================
-- DEFAULT SETTINGS
-- Insert default configuration values
-- ============================================================================
INSERT INTO settings (key, value, category, description) VALUES
    ('plex_url', '""', 'plex', 'Plex server URL'),
    ('plex_token', '""', 'plex', 'Plex authentication token'),
    ('library_name', '"Movies"', 'plex', 'Plex library name to scan'),

    ('collection_dv_enabled', 'true', 'collections', 'Enable All Dolby Vision collection'),
    ('collection_dv_name', '"All Dolby Vision"', 'collections', 'Name for DV collection'),
    ('collection_p7_enabled', 'true', 'collections', 'Enable Profile 7 FEL collection'),
    ('collection_p7_name', '"DV FEL Profile 7"', 'collections', 'Name for P7 collection'),
    ('collection_atmos_enabled', 'true', 'collections', 'Enable TrueHD Atmos collection'),
    ('collection_atmos_name', '"TrueHD Atmos"', 'collections', 'Name for Atmos collection'),

    ('scan_frequency_hours', '24', 'general', 'Hours between automatic scans'),
    ('monitor_interval_minutes', '1', 'general', 'Minutes between monitor checks'),
    ('auto_start_mode', '"none"', 'general', 'Auto-start behavior: none, scan, monitor'),

    ('telegram_enabled', 'false', 'telegram', 'Enable Telegram notifications'),
    ('telegram_token', '""', 'telegram', 'Telegram bot token'),
    ('telegram_chat_id', '""', 'telegram', 'Telegram chat ID'),

    ('notify_fel', 'true', 'notifications', 'Notify on FEL upgrades'),
    ('notify_fel_from_p5', 'true', 'notifications', 'Notify P5→P7 FEL upgrades'),
    ('notify_fel_from_hdr', 'true', 'notifications', 'Notify HDR→P7 FEL upgrades'),
    ('notify_dv_profile_upgrades', 'true', 'notifications', 'Notify DV profile upgrades'),
    ('notify_atmos', 'false', 'notifications', 'Notify Atmos additions'),
    ('notify_atmos_only_if_no_atmos', 'true', 'notifications', 'Notify Atmos only if missing'),
    ('notify_resolution', 'false', 'notifications', 'Notify resolution upgrades'),
    ('notify_only_library_movies', 'true', 'notifications', 'Only notify for library movies'),
    ('notify_expire_hours', '24', 'notifications', 'Hours before approval expires')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- VIEWS
-- Convenient pre-aggregated views for common queries
-- ============================================================================

-- View: DV Profile Distribution
CREATE OR REPLACE VIEW vw_dv_profile_distribution AS
SELECT
    dv_profile,
    COUNT(*) as count,
    ROUND(AVG(bitrate_mbps), 2) as avg_bitrate_mbps,
    ROUND(AVG(file_size_gb), 2) as avg_file_size_gb
FROM movies
WHERE dv_profile IS NOT NULL
GROUP BY dv_profile
ORDER BY dv_profile;

-- View: Recent Scan Summary
CREATE OR REPLACE VIEW vw_recent_scan_summary AS
SELECT
    id,
    scan_type,
    status,
    total_movies,
    dv_count,
    p7_count,
    fel_count,
    atmos_count,
    started_at,
    completed_at,
    duration_seconds
FROM scan_history
ORDER BY started_at DESC
LIMIT 10;

-- View: Active Downloads
CREATE OR REPLACE VIEW vw_active_downloads AS
SELECT
    pd.id,
    pd.request_id,
    pd.movie_title,
    pd.year,
    pd.quality_type,
    pd.upgrade_reason,
    pd.status,
    pd.created_at,
    pd.expires_at,
    EXTRACT(EPOCH FROM (pd.expires_at - NOW()))::INTEGER as seconds_until_expiry,
    m.dv_profile as current_dv_profile,
    m.dv_fel as current_dv_fel,
    m.has_atmos as current_has_atmos
FROM pending_downloads pd
LEFT JOIN movies m ON pd.movie_id = m.id
WHERE pd.status = 'pending' AND pd.expires_at > NOW()
ORDER BY pd.created_at DESC;

-- View: Library Statistics
CREATE OR REPLACE VIEW vw_library_stats AS
SELECT
    COUNT(*) as total_movies,
    COUNT(*) FILTER (WHERE dv_profile IS NOT NULL) as dv_count,
    COUNT(*) FILTER (WHERE dv_profile = '7' AND dv_fel = TRUE) as p7_fel_count,
    COUNT(*) FILTER (WHERE dv_profile = '5') as p5_count,
    COUNT(*) FILTER (WHERE has_atmos = TRUE) as atmos_count,
    COUNT(*) FILTER (WHERE has_truehd = TRUE) as truehd_count,
    COUNT(*) FILTER (WHERE dv_profile = '7' AND dv_fel = TRUE AND has_atmos = TRUE) as p7_atmos_count,
    ROUND(AVG(bitrate_mbps) FILTER (WHERE dv_profile IS NOT NULL), 2) as avg_dv_bitrate,
    ROUND(AVG(file_size_gb) FILTER (WHERE dv_profile IS NOT NULL), 2) as avg_dv_file_size,
    MAX(last_scanned_at) as last_scan_time
FROM movies;

-- ============================================================================
-- COMMENTS
-- Document table/column purposes
-- ============================================================================

COMMENT ON TABLE movies IS 'Core movie metadata from Plex library scans with DV profile detection';
COMMENT ON TABLE pending_downloads IS 'Download approval requests awaiting user action via Telegram';
COMMENT ON TABLE download_history IS 'Audit trail for all download approval actions';
COMMENT ON TABLE scan_history IS 'Complete history of all scan operations';
COMMENT ON TABLE settings IS 'Application configuration key-value store';
COMMENT ON TABLE connection_status IS 'Service health check status persistence';
COMMENT ON TABLE metadata_cache IS 'Cached Plex metadata and ffprobe analysis results';
COMMENT ON TABLE collection_changes IS 'Audit trail of Plex collection membership changes';
COMMENT ON TABLE notification_queue IS 'Persistent Telegram notification queue';
COMMENT ON TABLE scheduled_tasks IS 'APScheduler job state tracking';

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
