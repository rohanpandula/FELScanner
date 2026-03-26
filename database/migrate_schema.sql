-- Migration to update movies table schema to match v2 model
-- Adds missing columns needed by the application

BEGIN;

-- Add missing columns to movies table
ALTER TABLE movies
  ADD COLUMN IF NOT EXISTS sort_title VARCHAR(500),
  ADD COLUMN IF NOT EXISTS original_title VARCHAR(500),
  ADD COLUMN IF NOT EXISTS hdr_type VARCHAR(50),
  ADD COLUMN IF NOT EXISTS dv_bl_compatible BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS audio_codec VARCHAR(50),
  ADD COLUMN IF NOT EXISTS audio_channels VARCHAR(20),
  ADD COLUMN IF NOT EXISTS file_path TEXT,
  ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT,
  ADD COLUMN IF NOT EXISTS container VARCHAR(20),
  ADD COLUMN IF NOT EXISTS in_dv_collection BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS in_p7_collection BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS in_atmos_collection BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS version_count INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS best_version_index INTEGER;

-- Add indexes for new columns
CREATE INDEX IF NOT EXISTS idx_movies_hdr_type ON movies(hdr_type);
CREATE INDEX IF NOT EXISTS idx_movies_in_dv_collection ON movies(in_dv_collection) WHERE in_dv_collection = TRUE;
CREATE INDEX IF NOT EXISTS idx_movies_in_p7_collection ON movies(in_p7_collection) WHERE in_p7_collection = TRUE;
CREATE INDEX IF NOT EXISTS idx_movies_in_atmos_collection ON movies(in_atmos_collection) WHERE in_atmos_collection = TRUE;

COMMIT;
