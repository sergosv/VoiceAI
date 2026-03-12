-- Migración 038: Estado de grabación para tracking de fallos
-- Permite distinguir entre grabaciones pendientes, completadas y fallidas

ALTER TABLE calls ADD COLUMN IF NOT EXISTS recording_status TEXT DEFAULT NULL;

COMMENT ON COLUMN calls.recording_status IS 'Estado de la grabación: pending, completed, failed, deleted';

CREATE INDEX IF NOT EXISTS idx_calls_recording_status
    ON calls(recording_status) WHERE recording_status IS NOT NULL;
