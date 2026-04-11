-- 055: Timestamp de borrado de grabación para reporte de retención

ALTER TABLE calls
    ADD COLUMN IF NOT EXISTS recording_deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_calls_recording_deleted_at
    ON calls (recording_deleted_at)
    WHERE recording_deleted_at IS NOT NULL;

COMMENT ON COLUMN calls.recording_deleted_at IS 'Timestamp cuando la grabación fue eliminada (retention o manual)';
