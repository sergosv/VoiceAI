-- Migración 021: Agentes proactivos — scheduler de acciones programadas
-- Dos fuentes: reglas de negocio (dashboard) + instrucciones conversacionales (tool)

-- ── Agents: proactive config ──
ALTER TABLE agents ADD COLUMN IF NOT EXISTS proactive_config jsonb DEFAULT NULL;
COMMENT ON COLUMN agents.proactive_config IS 'Config de agente proactivo: {enabled, rules[{type, delay_minutes, channel, message, schedule, max_attempts}]}';

-- ── Tabla scheduled_actions ──
CREATE TABLE IF NOT EXISTS scheduled_actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id uuid NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    client_id uuid NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    rule_type text NOT NULL,
    channel text NOT NULL CHECK (channel IN ('call', 'whatsapp', 'sms')),
    target_number text NOT NULL,
    target_contact_id uuid REFERENCES contacts(id) ON DELETE SET NULL,
    message text,
    metadata jsonb DEFAULT '{}',
    scheduled_at timestamptz NOT NULL,
    status text DEFAULT 'pending' CHECK (status IN ('pending', 'executing', 'completed', 'failed', 'cancelled')),
    attempts int DEFAULT 0,
    max_attempts int DEFAULT 2,
    last_attempt_at timestamptz,
    result text,
    source text DEFAULT 'rule' CHECK (source IN ('rule', 'conversation', 'manual')),
    source_call_id uuid REFERENCES calls(id) ON DELETE SET NULL,
    created_at timestamptz DEFAULT now()
);

-- Índices para el worker de polling
CREATE INDEX IF NOT EXISTS idx_scheduled_actions_pending
    ON scheduled_actions (scheduled_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_scheduled_actions_agent
    ON scheduled_actions (agent_id, status);

CREATE INDEX IF NOT EXISTS idx_scheduled_actions_client
    ON scheduled_actions (client_id, status);

CREATE INDEX IF NOT EXISTS idx_scheduled_actions_contact
    ON scheduled_actions (target_contact_id)
    WHERE target_contact_id IS NOT NULL;

-- RLS
ALTER TABLE scheduled_actions ENABLE ROW LEVEL SECURITY;
