-- Migration 022: Separate GHL configs from WhatsApp configs
-- GHL es multi-canal (WhatsApp, SMS, WebChat, Facebook, Instagram, Email)
-- y necesita su propia config independiente de WhatsApp/Evolution.

-- ── ghl_configs ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS ghl_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    -- GHL credentials
    ghl_location_id TEXT NOT NULL,
    ghl_api_key TEXT,

    -- Messaging config (independiente de whatsapp_configs)
    auto_reply BOOLEAN NOT NULL DEFAULT true,
    greeting TEXT,
    session_timeout_minutes INT NOT NULL DEFAULT 30,
    media_response TEXT NOT NULL DEFAULT 'Solo puedo procesar mensajes de texto por ahora.',
    is_paused BOOLEAN NOT NULL DEFAULT false,
    paused_message TEXT NOT NULL DEFAULT 'En este momento un agente humano esta atendiendo. Te responderemos pronto.',
    away_message TEXT NOT NULL DEFAULT 'En este momento no estamos disponibles. Te responderemos en horario de atencion.',
    schedule JSONB,

    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(agent_id)
);

CREATE INDEX idx_ghl_configs_client ON ghl_configs(client_id);
CREATE INDEX idx_ghl_configs_location ON ghl_configs(ghl_location_id);

-- ── ghl_conversations ───────────────────────────────
CREATE TABLE IF NOT EXISTS ghl_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id UUID NOT NULL REFERENCES ghl_configs(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    remote_phone TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'whatsapp',
    ghl_contact_id TEXT,
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    flow_state JSONB,
    variables JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed', 'expired')),
    is_human_controlled BOOLEAN NOT NULL DEFAULT false,
    message_count INT NOT NULL DEFAULT 0,
    last_message_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ghl_conv_config_phone ON ghl_conversations(config_id, remote_phone);
CREATE INDEX idx_ghl_conv_status ON ghl_conversations(status) WHERE status = 'active';
CREATE INDEX idx_ghl_conv_contact ON ghl_conversations(contact_id) WHERE contact_id IS NOT NULL;
CREATE INDEX idx_ghl_conv_last_msg ON ghl_conversations(last_message_at DESC);

-- ── ghl_messages ────────────────────────────────────
CREATE TABLE IF NOT EXISTS ghl_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES ghl_conversations(id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    content TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'text' CHECK (message_type IN ('text', 'image', 'audio', 'video', 'document', 'system')),
    channel TEXT,
    tool_calls JSONB,
    provider_message_id TEXT,
    status TEXT NOT NULL DEFAULT 'sent' CHECK (status IN ('sent', 'delivered', 'read', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ghl_msg_conversation ON ghl_messages(conversation_id, created_at);

-- ── Triggers updated_at ──────────────────────────────────

CREATE TRIGGER trg_ghl_configs_updated
    BEFORE UPDATE ON ghl_configs
    FOR EACH ROW EXECUTE FUNCTION update_whatsapp_updated_at();

CREATE TRIGGER trg_ghl_conversations_updated
    BEFORE UPDATE ON ghl_conversations
    FOR EACH ROW EXECUTE FUNCTION update_whatsapp_updated_at();

-- ── RLS ──────────────────────────────────────────────────

ALTER TABLE ghl_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ghl_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ghl_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY ghl_configs_service ON ghl_configs
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY ghl_conversations_service ON ghl_conversations
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY ghl_messages_service ON ghl_messages
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ── Migrate existing GHL data ────────────────────────────

INSERT INTO ghl_configs (id, client_id, agent_id, ghl_location_id, ghl_api_key,
    auto_reply, greeting, session_timeout_minutes, media_response,
    is_paused, paused_message, away_message, schedule, is_active, created_at, updated_at)
SELECT id, client_id, agent_id, ghl_location_id, ghl_api_key,
    auto_reply, greeting, session_timeout_minutes, media_response,
    COALESCE(is_paused, false),
    COALESCE(paused_message, 'En este momento un agente humano esta atendiendo. Te responderemos pronto.'),
    COALESCE(away_message, 'En este momento no estamos disponibles. Te responderemos en horario de atencion.'),
    schedule, is_active, created_at, updated_at
FROM whatsapp_configs
WHERE provider = 'gohighlevel' AND ghl_location_id IS NOT NULL;

-- Remove GHL rows from whatsapp_configs
DELETE FROM whatsapp_configs WHERE provider = 'gohighlevel';

-- Clean up: remove GHL-specific columns from whatsapp_configs
ALTER TABLE whatsapp_configs DROP COLUMN IF EXISTS ghl_location_id;
ALTER TABLE whatsapp_configs DROP COLUMN IF EXISTS ghl_api_key;

-- Update provider CHECK constraint to only allow 'evolution'
ALTER TABLE whatsapp_configs DROP CONSTRAINT IF EXISTS whatsapp_configs_provider_check;
ALTER TABLE whatsapp_configs ADD CONSTRAINT whatsapp_configs_provider_check CHECK (provider IN ('evolution'));
