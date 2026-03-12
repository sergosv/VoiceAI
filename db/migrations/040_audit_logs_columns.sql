-- Migration 040: Fix audit_logs column names
-- The table was created with entity_type/entity_id but code uses resource_type/resource_id

ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS resource_type TEXT;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS resource_id TEXT;

-- Migrate existing data from old columns if they have data
UPDATE audit_logs SET resource_type = entity_type WHERE resource_type IS NULL AND entity_type IS NOT NULL;
UPDATE audit_logs SET resource_id = entity_id WHERE resource_id IS NULL AND entity_id IS NOT NULL;

-- Index for admin audit log queries
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);
