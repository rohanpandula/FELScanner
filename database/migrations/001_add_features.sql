-- Migration 001: Add release_group_preferences and activity_log tables
-- Features: Release Group Reputation (#6), Activity Feed (#9)

-- ============================================================================
-- RELEASE_GROUP_PREFERENCES TABLE
-- User preferences and aggregated stats for release groups
-- ============================================================================
CREATE TABLE IF NOT EXISTS release_group_preferences (
    id SERIAL PRIMARY KEY,
    group_name VARCHAR(200) NOT NULL UNIQUE,
    is_preferred BOOLEAN DEFAULT FALSE,
    is_blocked BOOLEAN DEFAULT FALSE,
    priority INTEGER DEFAULT 0,             -- Higher = more preferred
    avg_file_size_gb DECIMAL(10, 2),
    total_releases_seen INTEGER DEFAULT 0,
    total_downloads INTEGER DEFAULT 0,
    avg_quality_score DECIMAL(10, 2),
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,
    metadata JSONB                          -- Extra stats (profile breakdown, etc.)
);

CREATE INDEX idx_release_group_name ON release_group_preferences(group_name);
CREATE INDEX idx_release_group_preferred ON release_group_preferences(is_preferred) WHERE is_preferred = TRUE;
CREATE INDEX idx_release_group_priority ON release_group_preferences(priority DESC);

-- ============================================================================
-- ACTIVITY_LOG TABLE
-- Chronological feed of all significant events
-- ============================================================================
CREATE TABLE IF NOT EXISTS activity_log (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,        -- 'movie_added', 'movie_upgraded', 'movie_removed',
                                            -- 'download_approved', 'download_declined',
                                            -- 'scan_completed', 'collection_changed',
                                            -- 'upgrade_available', 'ipt_scan'
    title VARCHAR(500) NOT NULL,            -- Short description of the event
    description TEXT,                        -- Longer details
    severity VARCHAR(20) DEFAULT 'info',    -- 'info', 'success', 'warning', 'error'
    movie_id INTEGER REFERENCES movies(id) ON DELETE SET NULL,
    movie_title VARCHAR(500),
    movie_year INTEGER,
    related_id VARCHAR(100),                -- Generic FK (scan_id, download_id, etc.)
    related_type VARCHAR(50),               -- What related_id refers to
    quality_before VARCHAR(100),            -- For upgrade events
    quality_after VARCHAR(100),             -- For upgrade events
    metadata JSONB,                         -- Event-specific data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_activity_event_type ON activity_log(event_type);
CREATE INDEX idx_activity_created_at ON activity_log(created_at DESC);
CREATE INDEX idx_activity_movie_id ON activity_log(movie_id);
CREATE INDEX idx_activity_severity ON activity_log(severity);
CREATE INDEX idx_activity_metadata ON activity_log USING GIN(metadata);

COMMENT ON TABLE release_group_preferences IS 'User preferences and aggregated stats for torrent release groups';
COMMENT ON TABLE activity_log IS 'Chronological feed of all significant events in FELScanner';
