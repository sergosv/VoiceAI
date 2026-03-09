-- Migración 029: Campo recording_url en calls
-- Permite almacenar la URL de grabación de LiveKit Egress o storage externo

ALTER TABLE calls ADD COLUMN IF NOT EXISTS recording_url TEXT;

COMMENT ON COLUMN calls.recording_url IS 'URL de la grabación de audio (LiveKit Egress → S3/GCS)';
