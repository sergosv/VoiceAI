-- ============================================
-- SCHEMA: Voice AI Platform
-- Ejecutar en Supabase SQL Editor
-- ============================================

-- Extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TABLA: clients
-- Un registro por cada cliente/negocio
-- ============================================
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Identidad del negocio
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    business_type TEXT DEFAULT 'generic',

    -- Configuración del agente de voz
    agent_name TEXT NOT NULL,
    language TEXT DEFAULT 'es',
    voice_id TEXT NOT NULL,
    greeting TEXT NOT NULL,
    system_prompt TEXT NOT NULL,

    -- Gemini File Search
    file_search_store_id TEXT,
    file_search_store_name TEXT,

    -- Telefonía Twilio
    phone_number TEXT,
    twilio_phone_sid TEXT,
    sip_trunk_id TEXT,

    -- Configuración avanzada
    max_call_duration_seconds INT DEFAULT 300,
    tools_enabled TEXT[] DEFAULT '{"search_knowledge"}',
    transfer_number TEXT,
    business_hours JSONB,
    after_hours_message TEXT,

    -- Metadata
    is_active BOOLEAN DEFAULT true,
    owner_email TEXT,
    monthly_minutes_limit INT DEFAULT 500,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TABLA: calls
-- Log de cada llamada procesada
-- ============================================
CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,

    -- Info de la llamada
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    caller_number TEXT,
    callee_number TEXT,

    -- LiveKit
    livekit_room_id TEXT,
    livekit_room_name TEXT,

    -- Duración y costos
    duration_seconds INT DEFAULT 0,
    cost_livekit DECIMAL(10,6) DEFAULT 0,
    cost_stt DECIMAL(10,6) DEFAULT 0,
    cost_llm DECIMAL(10,6) DEFAULT 0,
    cost_tts DECIMAL(10,6) DEFAULT 0,
    cost_telephony DECIMAL(10,6) DEFAULT 0,
    cost_total DECIMAL(10,6) DEFAULT 0,

    -- Resultado
    status TEXT DEFAULT 'completed' CHECK (status IN ('completed', 'failed', 'transferred', 'no_answer', 'busy')),
    summary TEXT,
    transcript JSONB,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TABLA: documents
-- Documentos subidos al File Search de cada cliente
-- ============================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,

    filename TEXT NOT NULL,
    file_type TEXT,
    file_size_bytes INT,

    -- Gemini File Search
    gemini_file_id TEXT,
    gemini_file_uri TEXT,
    indexing_status TEXT DEFAULT 'pending',

    -- Metadata
    description TEXT,
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TABLA: usage_daily
-- Tracking diario de uso por cliente
-- ============================================
CREATE TABLE usage_daily (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,

    date DATE NOT NULL,
    total_calls INT DEFAULT 0,
    total_minutes DECIMAL(10,2) DEFAULT 0,
    total_cost DECIMAL(10,4) DEFAULT 0,

    inbound_calls INT DEFAULT 0,
    outbound_calls INT DEFAULT 0,

    UNIQUE(client_id, date)
);

-- ============================================
-- INDEXES
-- ============================================
CREATE INDEX idx_clients_phone ON clients(phone_number);
CREATE INDEX idx_clients_slug ON clients(slug);
CREATE INDEX idx_clients_active ON clients(is_active);
CREATE INDEX idx_calls_client ON calls(client_id);
CREATE INDEX idx_calls_started ON calls(started_at);
CREATE INDEX idx_calls_client_date ON calls(client_id, started_at);
CREATE INDEX idx_documents_client ON documents(client_id);
CREATE INDEX idx_usage_client_date ON usage_daily(client_id, date);

-- ============================================
-- RLS (Row Level Security) — para Fase 2
-- ============================================
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_daily ENABLE ROW LEVEL SECURITY;

-- Política temporal: service_role tiene acceso total
CREATE POLICY "Service role full access" ON clients FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON calls FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON documents FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON usage_daily FOR ALL USING (true) WITH CHECK (true);

-- ============================================
-- FUNCTIONS
-- ============================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Obtener config de cliente por número de teléfono
CREATE OR REPLACE FUNCTION get_client_by_phone(phone TEXT)
RETURNS TABLE (
    id UUID,
    name TEXT,
    slug TEXT,
    agent_name TEXT,
    language TEXT,
    voice_id TEXT,
    greeting TEXT,
    system_prompt TEXT,
    file_search_store_id TEXT,
    tools_enabled TEXT[],
    max_call_duration_seconds INT,
    transfer_number TEXT,
    business_hours JSONB,
    after_hours_message TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id, c.name, c.slug, c.agent_name, c.language,
        c.voice_id, c.greeting, c.system_prompt,
        c.file_search_store_id, c.tools_enabled,
        c.max_call_duration_seconds, c.transfer_number,
        c.business_hours, c.after_hours_message
    FROM clients c
    WHERE c.phone_number = phone AND c.is_active = true;
END;
$$ LANGUAGE plpgsql;
