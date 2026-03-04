-- Migration 016: WhatsApp Channel
-- Tablas para canal WhatsApp bidireccional (GHL + Evolution API)

-- ── whatsapp_configs ─────────────────────────────────────
-- Config de proveedor WhatsApp por agente
CREATE TABLE IF NOT EXISTS whatsapp_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('gohighlevel', 'evolution')),

    -- GHL credentials
    ghl_location_id TEXT,
    ghl_api_key TEXT,

    -- Evolution API credentials
    evo_instance_id TEXT,
    evo_api_url TEXT,
    evo_api_key TEXT,

    -- Shared config
    phone_number TEXT,
    auto_reply BOOLEAN NOT NULL DEFAULT true,
    greeting TEXT,
    session_timeout_minutes INT NOT NULL DEFAULT 30,
    media_response TEXT NOT NULL DEFAULT 'Solo puedo procesar mensajes de texto por ahora.',

    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(agent_id)
);

CREATE INDEX idx_whatsapp_configs_client ON whatsapp_configs(client_id);
CREATE INDEX idx_whatsapp_configs_ghl_location ON whatsapp_configs(ghl_location_id) WHERE ghl_location_id IS NOT NULL;
CREATE INDEX idx_whatsapp_configs_evo_instance ON whatsapp_configs(evo_instance_id) WHERE evo_instance_id IS NOT NULL;

-- ── whatsapp_conversations ───────────────────────────────
-- Sesiones persistentes de chat WhatsApp
CREATE TABLE IF NOT EXISTS whatsapp_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id UUID NOT NULL REFERENCES whatsapp_configs(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    remote_phone TEXT NOT NULL,
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    flow_state JSONB,
    variables JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed', 'expired')),
    message_count INT NOT NULL DEFAULT 0,
    last_message_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_wa_conv_config_phone ON whatsapp_conversations(config_id, remote_phone);
CREATE INDEX idx_wa_conv_status ON whatsapp_conversations(status) WHERE status = 'active';
CREATE INDEX idx_wa_conv_contact ON whatsapp_conversations(contact_id) WHERE contact_id IS NOT NULL;
CREATE INDEX idx_wa_conv_last_msg ON whatsapp_conversations(last_message_at DESC);

-- ── whatsapp_messages ────────────────────────────────────
-- Log de cada mensaje WhatsApp
CREATE TABLE IF NOT EXISTS whatsapp_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES whatsapp_conversations(id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    content TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'text' CHECK (message_type IN ('text', 'image', 'audio', 'video', 'document', 'system')),
    tool_calls JSONB,
    provider_message_id TEXT,
    status TEXT NOT NULL DEFAULT 'sent' CHECK (status IN ('sent', 'delivered', 'read', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_wa_msg_conversation ON whatsapp_messages(conversation_id, created_at);
CREATE INDEX idx_wa_msg_direction ON whatsapp_messages(conversation_id, direction);

-- ── Triggers updated_at ──────────────────────────────────

CREATE OR REPLACE FUNCTION update_whatsapp_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_whatsapp_configs_updated
    BEFORE UPDATE ON whatsapp_configs
    FOR EACH ROW EXECUTE FUNCTION update_whatsapp_updated_at();

CREATE TRIGGER trg_whatsapp_conversations_updated
    BEFORE UPDATE ON whatsapp_conversations
    FOR EACH ROW EXECUTE FUNCTION update_whatsapp_updated_at();

-- ── RLS ──────────────────────────────────────────────────

ALTER TABLE whatsapp_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_messages ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS
CREATE POLICY whatsapp_configs_service ON whatsapp_configs
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY whatsapp_conversations_service ON whatsapp_conversations
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY whatsapp_messages_service ON whatsapp_messages
    FOR ALL TO service_role USING (true) WITH CHECK (true);
