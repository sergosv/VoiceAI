-- Migración 025: Voces clonadas por cliente
-- Tabla para rastrear voces clonadas en Cartesia/ElevenLabs, aisladas por client_id

CREATE TABLE IF NOT EXISTS cloned_voices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    provider TEXT NOT NULL DEFAULT 'cartesia'
        CHECK (provider IN ('cartesia', 'elevenlabs')),
    external_voice_id TEXT NOT NULL,          -- ID en Cartesia/ElevenLabs
    name TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'es',
    description TEXT DEFAULT '',
    sample_url TEXT,                           -- URL del audio original subido
    duration_seconds REAL,                     -- Duración del audio fuente
    status TEXT NOT NULL DEFAULT 'ready'
        CHECK (status IN ('processing', 'ready', 'failed')),
    metadata JSONB DEFAULT '{}',              -- Info extra del provider
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_cloned_voices_client ON cloned_voices(client_id);
CREATE INDEX IF NOT EXISTS idx_cloned_voices_provider ON cloned_voices(provider, external_voice_id);

-- Trigger updated_at
CREATE TRIGGER cloned_voices_updated_at
    BEFORE UPDATE ON cloned_voices
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
