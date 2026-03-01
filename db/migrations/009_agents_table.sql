-- Migration 009: Multi-agent per client
-- Cada client (negocio) puede tener N agentes, cada uno con su propio
-- teléfono, prompt, voz y configuración de pipeline.

-- 1. Tabla agents
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    phone_number TEXT,
    phone_sid TEXT,
    livekit_sip_trunk_id TEXT,
    system_prompt TEXT NOT NULL DEFAULT '',
    greeting TEXT NOT NULL DEFAULT '',
    examples TEXT,
    voice_config JSONB NOT NULL DEFAULT '{}',
    llm_config JSONB NOT NULL DEFAULT '{}',
    stt_config JSONB NOT NULL DEFAULT '{}',
    agent_mode TEXT NOT NULL DEFAULT 'pipeline' CHECK (agent_mode IN ('pipeline', 'realtime')),
    agent_type TEXT NOT NULL DEFAULT 'inbound' CHECK (agent_type IN ('inbound', 'outbound', 'both')),
    transfer_number TEXT,
    after_hours_message TEXT,
    max_call_duration_seconds INT DEFAULT 300,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(client_id, slug),
    UNIQUE(phone_number)
);

-- 2. agent_id en calls y campaigns (nullable para backward compat)
ALTER TABLE calls ADD COLUMN agent_id UUID REFERENCES agents(id) ON DELETE SET NULL;
ALTER TABLE campaigns ADD COLUMN agent_id UUID REFERENCES agents(id) ON DELETE SET NULL;

-- 3. Indexes
CREATE INDEX idx_agents_client ON agents(client_id);
CREATE INDEX idx_agents_phone ON agents(phone_number);
CREATE INDEX idx_agents_active ON agents(client_id, is_active);
CREATE INDEX idx_calls_agent ON calls(agent_id);
CREATE INDEX idx_campaigns_agent ON campaigns(agent_id);

-- 4. Trigger updated_at (reusar function existente)
CREATE TRIGGER set_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 5. RLS
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_agents" ON agents FOR ALL USING (auth.role() = 'service_role');

-- 6. Migrar datos: crear agent default por cada client existente
INSERT INTO agents (
    client_id, name, slug, phone_number, phone_sid, livekit_sip_trunk_id,
    system_prompt, greeting, examples, voice_config, llm_config, stt_config,
    agent_mode, transfer_number, after_hours_message, max_call_duration_seconds
)
SELECT
    c.id,
    c.agent_name,
    'default',
    c.phone_number,
    c.twilio_phone_sid,
    c.sip_trunk_id,
    COALESCE(c.system_prompt, ''),
    COALESCE(c.greeting, ''),
    c.conversation_examples,
    jsonb_build_object(
        'provider', COALESCE(c.tts_provider, 'cartesia'),
        'voice_id', c.voice_id,
        'api_key', c.tts_api_key,
        'realtime_voice', COALESCE(c.realtime_voice, 'alloy'),
        'realtime_model', COALESCE(c.realtime_model, 'gpt-4o-realtime-preview'),
        'realtime_api_key', c.realtime_api_key
    ),
    jsonb_build_object(
        'provider', COALESCE(c.llm_provider, 'google'),
        'api_key', c.llm_api_key
    ),
    jsonb_build_object(
        'provider', COALESCE(c.stt_provider, 'deepgram'),
        'api_key', c.stt_api_key
    ),
    COALESCE(c.voice_mode, 'pipeline'),
    c.transfer_number,
    c.after_hours_message,
    c.max_call_duration_seconds
FROM clients c;

-- 7. Backfill agent_id en calls y campaigns existentes
UPDATE calls SET agent_id = (
    SELECT a.id FROM agents a WHERE a.client_id = calls.client_id LIMIT 1
) WHERE agent_id IS NULL;

UPDATE campaigns SET agent_id = (
    SELECT a.id FROM agents a WHERE a.client_id = campaigns.client_id LIMIT 1
) WHERE agent_id IS NULL;
