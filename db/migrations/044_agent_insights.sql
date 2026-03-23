-- Insights automáticos generados del análisis cross-call
-- El sistema analiza periódicamente las llamadas de cada agente
-- y genera insights: preguntas frecuentes, temas recurrentes, sugerencias

CREATE TABLE IF NOT EXISTS agent_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    -- Tipo de insight
    insight_type TEXT NOT NULL CHECK (insight_type IN (
        'faq',              -- Pregunta frecuente detectada
        'topic_trend',      -- Tema recurrente
        'drop_point',       -- Punto donde las llamadas se cortan/frustran
        'prompt_suggestion', -- Sugerencia de mejora al system prompt
        'tool_usage',       -- Patrón de uso de tools
        'sentiment_pattern'  -- Patrón de sentimiento
    )),
    -- Contenido del insight
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    -- Datos de soporte
    evidence JSONB DEFAULT '{}',
    -- Para faq: la respuesta sugerida que el agente debería dar
    suggested_response TEXT,
    -- Para prompt_suggestion: el texto sugerido
    suggested_prompt_addition TEXT,
    -- Métricas
    frequency INT DEFAULT 1,         -- cuántas veces se detectó
    confidence FLOAT DEFAULT 0.5,    -- 0-1 confianza del insight
    -- Estado
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'applied', 'dismissed')),
    -- Periodo analizado
    analyzed_from TIMESTAMPTZ,
    analyzed_to TIMESTAMPTZ,
    calls_analyzed INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_insights_agent
    ON agent_insights(agent_id, insight_type) WHERE status = 'active';

ALTER TABLE agent_insights ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_insights_select ON agent_insights
    FOR SELECT USING (
        auth.uid() IN (
            SELECT u.auth_user_id FROM users u
            WHERE u.role = 'admin' OR u.client_id = agent_insights.client_id
        )
    );

CREATE POLICY agent_insights_all ON agent_insights
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.auth_user_id FROM users u WHERE u.role = 'admin'
        )
    );

COMMENT ON TABLE agent_insights IS 'Insights automáticos del análisis cross-call: FAQs, tendencias, sugerencias de prompt';
