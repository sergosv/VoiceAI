-- 050: Scheduled Callbacks — permite al agente prometer "te llamo a las X"
-- y que el sistema realmente lo haga.

CREATE TABLE IF NOT EXISTS scheduled_callbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'America/Mexico_City',
    context TEXT,                          -- resumen de la conversación previa
    origin_call_id UUID REFERENCES calls(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    last_attempt_at TIMESTAMPTZ,
    result_call_id UUID REFERENCES calls(id) ON DELETE SET NULL,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices para el scheduler
CREATE INDEX IF NOT EXISTS idx_scheduled_callbacks_pending
    ON scheduled_callbacks (scheduled_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_scheduled_callbacks_client
    ON scheduled_callbacks (client_id, status);

CREATE INDEX IF NOT EXISTS idx_scheduled_callbacks_agent
    ON scheduled_callbacks (agent_id, status);

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_scheduled_callbacks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_scheduled_callbacks_updated_at ON scheduled_callbacks;
CREATE TRIGGER trg_scheduled_callbacks_updated_at
    BEFORE UPDATE ON scheduled_callbacks
    FOR EACH ROW
    EXECUTE FUNCTION update_scheduled_callbacks_updated_at();

COMMENT ON TABLE scheduled_callbacks IS 'Callbacks programados por el agente de voz durante llamadas';
COMMENT ON COLUMN scheduled_callbacks.context IS 'Resumen de la conversación original para que el agente tenga contexto al devolver la llamada';
COMMENT ON COLUMN scheduled_callbacks.origin_call_id IS 'Llamada original donde se prometió el callback';
COMMENT ON COLUMN scheduled_callbacks.result_call_id IS 'Llamada generada por el callback (si se completó)';
