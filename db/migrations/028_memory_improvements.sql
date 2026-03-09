-- Migración 028: Mejoras al sistema de memoria
-- 1. Temporal decay en búsqueda semántica (memorias viejas pierden peso)
-- 2. Columnas para detección de contradicciones e intent primario

-- ── 1. Nuevas columnas en memories ──
ALTER TABLE memories ADD COLUMN IF NOT EXISTS contradiction_flags JSONB DEFAULT NULL;
COMMENT ON COLUMN memories.contradiction_flags IS 'Contradicciones detectadas con datos previos del contacto: [{old_fact, new_fact, field}]';

ALTER TABLE memories ADD COLUMN IF NOT EXISTS primary_intent TEXT DEFAULT NULL;
COMMENT ON COLUMN memories.primary_intent IS 'Intent principal detectado en la conversación';

-- ── 2. Reemplazar RPC con temporal decay ──
CREATE OR REPLACE FUNCTION search_memories_by_embedding(
    p_client_id UUID,
    p_contact_id UUID,
    p_embedding vector(768),
    p_limit INT DEFAULT 5,
    p_min_similarity FLOAT DEFAULT 0.3
)
RETURNS TABLE (
    id UUID,
    summary TEXT,
    channel TEXT,
    agent_name TEXT,
    sentiment TEXT,
    topics JSONB,
    action_items JSONB,
    created_at TIMESTAMPTZ,
    similarity FLOAT,
    recency_score FLOAT
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
        m.created_at,
        (1 - (m.embedding <=> p_embedding))::FLOAT AS similarity,
        ((1 - (m.embedding <=> p_embedding)) * EXP(-EXTRACT(EPOCH FROM (NOW() - m.created_at)) / (180 * 86400)))::FLOAT AS recency_score
    FROM memories m
    WHERE m.client_id = p_client_id
      AND m.contact_id = p_contact_id
      AND m.embedding IS NOT NULL
      AND (1 - (m.embedding <=> p_embedding)) >= p_min_similarity
    ORDER BY recency_score DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;
