-- Migración 037: Campos de grabación en calls
-- recording_key almacena el object key en R2 (separado de recording_url para presigned URLs)

ALTER TABLE calls ADD COLUMN IF NOT EXISTS recording_key TEXT;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS recording_duration_seconds INT;

COMMENT ON COLUMN calls.recording_key IS 'R2 object key para el archivo de grabación';
COMMENT ON COLUMN calls.recording_duration_seconds IS 'Duración de la grabación en segundos';

CREATE INDEX IF NOT EXISTS idx_calls_recording_key ON calls(recording_key) WHERE recording_key IS NOT NULL;
