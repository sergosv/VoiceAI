-- Migración 046: Asistente Personal — nuevo tipo de agente
-- Agrega categoría de agente, whitelist de callers, memoria estructurada con pgvector,
-- y configuración de email por agente PA.

-- ── 1. Campo de categoría en agents ─────────────────────
ALTER TABLE agents ADD COLUMN IF NOT EXISTS agent_category TEXT NOT NULL DEFAULT 'service'
  CHECK (agent_category IN ('service', 'personal_assistant'));

COMMENT ON COLUMN agents.agent_category IS 'Categoría: service (atención) o personal_assistant';

-- ── 2. Whitelist de callers autorizados ─────────────────
CREATE TABLE IF NOT EXISTS pa_authorized_callers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    phone_number TEXT NOT NULL,
    label TEXT,                    -- "Mi celular", "Oficina"
    is_owner BOOLEAN DEFAULT false,
    reminder_delivery TEXT DEFAULT 'both'
      CHECK (reminder_delivery IN ('call', 'whatsapp', 'both')),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(agent_id, phone_number)
);

CREATE INDEX IF NOT EXISTS idx_pa_auth_callers_agent
  ON pa_authorized_callers(agent_id);
CREATE INDEX IF NOT EXISTS idx_pa_auth_callers_phone
  ON pa_authorized_callers(phone_number);

-- ── 3. Memoria estructurada del PA (pgvector) ──────────
CREATE TABLE IF NOT EXISTS pa_memory_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL
      CHECK (item_type IN ('fact', 'preference', 'task', 'note', 'reminder')),
    content TEXT NOT NULL,
    embedding VECTOR(768),
    metadata JSONB DEFAULT '{}',
    is_completed BOOLEAN DEFAULT false,
    is_deleted BOOLEAN DEFAULT false,
    source_call_id UUID REFERENCES calls(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON COLUMN pa_memory_items.metadata IS
  'Campos opcionales: priority, due_date, completed_at, tags[], category, title';

-- Índice HNSW para búsqueda semántica
CREATE INDEX IF NOT EXISTS idx_pa_memory_embedding
  ON pa_memory_items USING hnsw (embedding vector_cosine_ops)
  WHERE embedding IS NOT NULL AND NOT is_deleted;

-- Índice para queries por tipo
CREATE INDEX IF NOT EXISTS idx_pa_memory_agent_type
  ON pa_memory_items(agent_id, item_type)
  WHERE NOT is_deleted;

-- Índice para tasks/reminders activos
CREATE INDEX IF NOT EXISTS idx_pa_memory_tasks
  ON pa_memory_items(agent_id, is_completed, created_at DESC)
  WHERE item_type IN ('task', 'reminder') AND NOT is_deleted;

-- Trigger updated_at
CREATE TRIGGER set_pa_memory_items_updated_at
  BEFORE UPDATE ON pa_memory_items
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── 4. Config de email por agente PA ────────────────────
CREATE TABLE IF NOT EXISTS pa_email_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE UNIQUE,
    from_name TEXT NOT NULL,       -- "Asistente de Dr. García"
    from_email TEXT NOT NULL,      -- Dirección verificada en Resend
    reply_to TEXT,                 -- Email real del dueño
    signature TEXT,                -- Firma del email
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER set_pa_email_config_updated_at
  BEFORE UPDATE ON pa_email_config
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── 5. Función de búsqueda semántica en memoria PA ─────
CREATE OR REPLACE FUNCTION search_pa_memory(
    p_agent_id UUID,
    p_query_embedding VECTOR(768),
    p_item_types TEXT[] DEFAULT NULL,
    p_limit INTEGER DEFAULT 10,
    p_min_similarity FLOAT DEFAULT 0.3
) RETURNS TABLE (
    id UUID,
    item_type TEXT,
    content TEXT,
    metadata JSONB,
    is_completed BOOLEAN,
    created_at TIMESTAMPTZ,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id, m.item_type, m.content, m.metadata,
        m.is_completed, m.created_at,
        (1 - (m.embedding <=> p_query_embedding))::FLOAT AS similarity
    FROM pa_memory_items m
    WHERE m.agent_id = p_agent_id
      AND NOT m.is_deleted
      AND (p_item_types IS NULL OR m.item_type = ANY(p_item_types))
      AND m.embedding IS NOT NULL
      AND (1 - (m.embedding <=> p_query_embedding)) >= p_min_similarity
    ORDER BY m.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ── 6. RLS ──────────────────────────────────────────────
ALTER TABLE pa_authorized_callers ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_memory_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_email_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_pa_authorized_callers"
  ON pa_authorized_callers FOR ALL
  USING (auth.role() = 'service_role');

CREATE POLICY "service_role_pa_memory_items"
  ON pa_memory_items FOR ALL
  USING (auth.role() = 'service_role');

CREATE POLICY "service_role_pa_email_config"
  ON pa_email_config FOR ALL
  USING (auth.role() = 'service_role');
