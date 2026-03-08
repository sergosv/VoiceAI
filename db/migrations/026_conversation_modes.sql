-- Migracion 026: Modos de conversacion (encuesta, quiz, negociacion, entrevista)

-- Expandir constraint de conversation_mode
ALTER TABLE agents DROP CONSTRAINT IF EXISTS agents_conversation_mode_check;
ALTER TABLE agents ADD CONSTRAINT agents_conversation_mode_check
    CHECK (conversation_mode IN ('prompt', 'flow', 'survey', 'quiz', 'negotiation', 'interview'));

-- Config especifica del modo (preguntas, scoring, precios, etc.)
ALTER TABLE agents ADD COLUMN IF NOT EXISTS mode_config JSONB DEFAULT '{}';

-- Tabla de resultados estructurados por sesion
CREATE TABLE IF NOT EXISTS conversation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    mode TEXT NOT NULL CHECK (mode IN ('survey', 'quiz', 'negotiation', 'interview')),
    answers JSONB DEFAULT '[]',
    score NUMERIC(5,2),
    max_score NUMERIC(5,2),
    passed BOOLEAN,
    summary TEXT,
    metadata JSONB DEFAULT '{}',
    completed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conv_results_agent ON conversation_results(agent_id);
CREATE INDEX IF NOT EXISTS idx_conv_results_client ON conversation_results(client_id);
CREATE INDEX IF NOT EXISTS idx_conv_results_call ON conversation_results(call_id);
CREATE INDEX IF NOT EXISTS idx_conv_results_mode ON conversation_results(mode);
