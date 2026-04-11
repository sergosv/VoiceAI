-- 054: Legal hold para grabaciones
-- Permite marcar llamadas que no deben ser eliminadas por el retention worker

ALTER TABLE calls
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS legal_hold_reason TEXT,
    ADD COLUMN IF NOT EXISTS legal_hold_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_calls_legal_hold
    ON calls (legal_hold)
    WHERE legal_hold = TRUE;

COMMENT ON COLUMN calls.legal_hold IS 'Si true, la grabación NO puede ser eliminada por retention policy';
COMMENT ON COLUMN calls.legal_hold_reason IS 'Motivo del hold (investigación, disputa, etc.)';
