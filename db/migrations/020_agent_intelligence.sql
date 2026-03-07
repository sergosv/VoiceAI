-- Migración 020: Inteligencia de agentes
-- Agrega configs de inteligencia a agents y datos realtime a calls

-- ── Agents: configs de inteligencia ──
ALTER TABLE agents ADD COLUMN IF NOT EXISTS sentiment_config jsonb DEFAULT NULL;
COMMENT ON COLUMN agents.sentiment_config IS 'Config de sentimiento en tiempo real: {enabled, escalation_threshold, auto_transfer, notify_on_negative}';

ALTER TABLE agents ADD COLUMN IF NOT EXISTS intent_config jsonb DEFAULT NULL;
COMMENT ON COLUMN agents.intent_config IS 'Config de intent extraction: {enabled, custom_intents, track_unresolved}';

ALTER TABLE agents ADD COLUMN IF NOT EXISTS guardrails_config jsonb DEFAULT NULL;
COMMENT ON COLUMN agents.guardrails_config IS 'Config de guardrails: {enabled, prohibited_topics, blocked_patterns, require_disclaimer}';

ALTER TABLE agents ADD COLUMN IF NOT EXISTS language_detection_config jsonb DEFAULT NULL;
COMMENT ON COLUMN agents.language_detection_config IS 'Config de detección de idioma: {enabled, supported_languages, detection_turns}';

ALTER TABLE agents ADD COLUMN IF NOT EXISTS quality_config jsonb DEFAULT NULL;
COMMENT ON COLUMN agents.quality_config IS 'Config de quality scoring: {enabled, min_score_alert, score_criteria}';

-- ── Calls: datos realtime de inteligencia ──
ALTER TABLE calls ADD COLUMN IF NOT EXISTS sentiment_realtime jsonb DEFAULT NULL;
COMMENT ON COLUMN calls.sentiment_realtime IS 'Timeline de sentimiento en tiempo real por turno';

ALTER TABLE calls ADD COLUMN IF NOT EXISTS intent_realtime jsonb DEFAULT NULL;
COMMENT ON COLUMN calls.intent_realtime IS 'Intents detectados por turno + intent principal';

ALTER TABLE calls ADD COLUMN IF NOT EXISTS quality_score integer DEFAULT NULL;
COMMENT ON COLUMN calls.quality_score IS 'Score de calidad de la llamada (0-100)';

-- ── RPC: Búsqueda semántica de memorias por embedding ──
CREATE OR REPLACE FUNCTION search_memories_by_embedding(
    p_client_id uuid,
    p_contact_id uuid,
    p_embedding vector(768),
    p_limit int DEFAULT 3,
    p_min_similarity float DEFAULT 0.3
)
RETURNS TABLE (
    id uuid,
    summary text,
    channel text,
    agent_name text,
    sentiment text,
    topics jsonb,
    action_items jsonb,
    created_at timestamptz,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        m.id,
        m.summary,
        m.channel,
        m.agent_name,
        m.sentiment,
        m.topics,
        m.action_items,
        m.created_at,
        1 - (m.embedding <=> p_embedding) AS similarity
    FROM memories m
    WHERE m.client_id = p_client_id
      AND m.contact_id = p_contact_id
      AND m.embedding IS NOT NULL
      AND 1 - (m.embedding <=> p_embedding) >= p_min_similarity
    ORDER BY m.embedding <=> p_embedding
    LIMIT p_limit;
$$;
