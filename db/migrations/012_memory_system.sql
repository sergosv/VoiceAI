-- Migración 012: Sistema de memoria de largo plazo
-- Permite que los agentes recuerden interacciones pasadas con contactos
-- a través de todos los canales (voz, WhatsApp, web chat).

-- ── 1. Habilitar pgvector ─────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

-- ── 2. Extender tabla contacts ────────────────────────
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS summary_embedding VECTOR(768);
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}';
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS key_facts JSONB DEFAULT '[]';
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS last_interaction_channel TEXT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS average_sentiment TEXT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS first_interaction_at TIMESTAMPTZ;

-- Índice HNSW para búsqueda semántica en perfiles de contacto
CREATE INDEX IF NOT EXISTS idx_contacts_summary_embedding
ON contacts USING hnsw (summary_embedding vector_cosine_ops)
WHERE summary_embedding IS NOT NULL;

-- ── 3. Tabla contact_identifiers ──────────────────────
-- Permite vincular múltiples identidades (teléfono, email, WhatsApp) a un mismo contacto
CREATE TABLE IF NOT EXISTS contact_identifiers (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    identifier_type TEXT NOT NULL
        CHECK (identifier_type IN ('phone', 'email', 'whatsapp', 'web_session', 'custom')),
    identifier_value TEXT NOT NULL,
    is_primary BOOLEAN DEFAULT false,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, identifier_type, identifier_value)
);

CREATE INDEX IF NOT EXISTS idx_contact_identifiers_lookup
ON contact_identifiers(client_id, identifier_type, identifier_value);

CREATE INDEX IF NOT EXISTS idx_contact_identifiers_contact
ON contact_identifiers(contact_id);

-- ── 4. Tabla memories ─────────────────────────────────
-- Memorias episódicas por interacción con embeddings para búsqueda semántica
CREATE TABLE IF NOT EXISTS memories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    channel TEXT NOT NULL DEFAULT 'call'
        CHECK (channel IN ('call', 'whatsapp', 'web_chat', 'outbound_call')),
    agent_id UUID REFERENCES agents(id),
    agent_name TEXT,
    duration_seconds INTEGER,
    sentiment TEXT,
    topics JSONB DEFAULT '[]',
    action_items JSONB DEFAULT '[]',
    extracted_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memories_embedding
ON memories USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_memories_contact
ON memories(contact_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_memories_client
ON memories(client_id, created_at DESC);

-- ── 5. Funciones SQL ──────────────────────────────────

-- Resolver contacto por identificador
CREATE OR REPLACE FUNCTION resolve_contact(
    p_client_id UUID,
    p_identifier_type TEXT,
    p_identifier_value TEXT
) RETURNS UUID AS $$
DECLARE
    v_contact_id UUID;
BEGIN
    SELECT contact_id INTO v_contact_id
    FROM contact_identifiers
    WHERE client_id = p_client_id
      AND identifier_type = p_identifier_type
      AND identifier_value = p_identifier_value
    LIMIT 1;

    RETURN v_contact_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Crear contacto con identificador inicial
CREATE OR REPLACE FUNCTION create_contact_with_identifier(
    p_client_id UUID,
    p_identifier_type TEXT,
    p_identifier_value TEXT,
    p_name TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_contact_id UUID;
BEGIN
    -- Crear el contacto
    INSERT INTO contacts (client_id, phone, name, source, call_count, first_interaction_at)
    VALUES (
        p_client_id,
        CASE WHEN p_identifier_type = 'phone' THEN p_identifier_value ELSE '' END,
        p_name,
        p_identifier_type || '_contact',
        0,
        NOW()
    )
    RETURNING id INTO v_contact_id;

    -- Crear el identificador
    INSERT INTO contact_identifiers (client_id, contact_id, identifier_type, identifier_value, is_primary)
    VALUES (p_client_id, v_contact_id, p_identifier_type, p_identifier_value, true)
    ON CONFLICT DO NOTHING;

    RETURN v_contact_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Vincular identificador adicional a contacto existente
CREATE OR REPLACE FUNCTION link_identifier_to_contact(
    p_client_id UUID,
    p_contact_id UUID,
    p_identifier_type TEXT,
    p_identifier_value TEXT
) RETURNS BOOLEAN AS $$
BEGIN
    INSERT INTO contact_identifiers (client_id, contact_id, identifier_type, identifier_value)
    VALUES (p_client_id, p_contact_id, p_identifier_type, p_identifier_value)
    ON CONFLICT (client_id, identifier_type, identifier_value) DO NOTHING;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Buscar memorias por similitud semántica
CREATE OR REPLACE FUNCTION search_memories(
    p_client_id UUID,
    p_contact_id UUID,
    p_query_embedding VECTOR(768),
    p_count INTEGER DEFAULT 5,
    p_threshold FLOAT DEFAULT 0.7
) RETURNS TABLE (
    id UUID,
    summary TEXT,
    channel TEXT,
    agent_name TEXT,
    sentiment TEXT,
    topics JSONB,
    action_items JSONB,
    extracted_data JSONB,
    created_at TIMESTAMPTZ,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.summary,
        m.channel,
        m.agent_name,
        m.sentiment,
        m.topics,
        m.action_items,
        m.extracted_data,
        m.created_at,
        1 - (m.embedding <=> p_query_embedding)::FLOAT AS similarity
    FROM memories m
    WHERE m.client_id = p_client_id
      AND m.contact_id = p_contact_id
      AND 1 - (m.embedding <=> p_query_embedding) >= p_threshold
    ORDER BY m.embedding <=> p_query_embedding
    LIMIT p_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Obtener memorias recientes de un contacto
CREATE OR REPLACE FUNCTION get_recent_memories(
    p_client_id UUID,
    p_contact_id UUID,
    p_limit INTEGER DEFAULT 5,
    p_channel TEXT DEFAULT NULL
) RETURNS TABLE (
    id UUID,
    summary TEXT,
    channel TEXT,
    agent_name TEXT,
    duration_seconds INTEGER,
    sentiment TEXT,
    topics JSONB,
    action_items JSONB,
    extracted_data JSONB,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.summary,
        m.channel,
        m.agent_name,
        m.duration_seconds,
        m.sentiment,
        m.topics,
        m.action_items,
        m.extracted_data,
        m.created_at
    FROM memories m
    WHERE m.client_id = p_client_id
      AND m.contact_id = p_contact_id
      AND (p_channel IS NULL OR m.channel = p_channel)
    ORDER BY m.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ── 6. Backfill: crear identificadores para contactos existentes ──
INSERT INTO contact_identifiers (client_id, contact_id, identifier_type, identifier_value, is_primary)
SELECT client_id, id, 'phone', phone, true
FROM contacts
WHERE phone IS NOT NULL AND phone != ''
ON CONFLICT DO NOTHING;

-- Inicializar first_interaction_at desde created_at
UPDATE contacts SET first_interaction_at = created_at WHERE first_interaction_at IS NULL;

-- ── 7. RLS ────────────────────────────────────────────
ALTER TABLE contact_identifiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;

-- service_role tiene acceso completo
CREATE POLICY "service_role_contact_identifiers"
ON contact_identifiers FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "service_role_memories"
ON memories FOR ALL
TO service_role
USING (true)
WITH CHECK (true);
