-- 060: provider_health_events — log persistente de salud de providers externos
--
-- Propósito: dedup de alertas. Sin esta tabla, un monitor en memoria pierde
-- estado en cada deploy/restart de Coolify-Railway y envía emails duplicados.
--
-- Uso actual (MVP): Twilio parent account health (tarea cada 5 min).
-- Futuro: Gemini, Cartesia, Deepgram, LiveKit, Stripe — mismo patrón.
--
-- Patrón de alertas: se alerta SOLO en transiciones healthy↔unhealthy.
-- Durante el estado estable (caído o sano), no se duplican alertas.

CREATE TABLE IF NOT EXISTS provider_health_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,              -- 'twilio_parent', 'gemini', 'cartesia', etc.
    status TEXT NOT NULL,                -- 'healthy' | 'unhealthy'
    severity TEXT,                       -- 'critical' | 'warning' | NULL (para healthy)
    error_type TEXT,                     -- 'parent_not_active' | 'auth_failed' | 'api_error' | 'timeout' | NULL
    details JSONB DEFAULT '{}'::jsonb,
    alerted BOOLEAN NOT NULL DEFAULT false,  -- true si se envió email por este evento
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE provider_health_events IS
    'Log persistente de salud de providers externos. Dedup de alertas vía transiciones healthy↔unhealthy.';
COMMENT ON COLUMN provider_health_events.provider IS
    'Identificador del provider monitoreado. Ejemplos: twilio_parent, gemini, cartesia.';
COMMENT ON COLUMN provider_health_events.status IS
    'healthy | unhealthy. Solo 2 valores para dedup simple.';
COMMENT ON COLUMN provider_health_events.severity IS
    'critical | warning | NULL. critical=acción inmediata requerida, warning=investigar, NULL=status healthy.';
COMMENT ON COLUMN provider_health_events.error_type IS
    'Clasificación del fallo. parent_not_active, auth_failed (401/403), api_error (5xx), timeout.';
COMMENT ON COLUMN provider_health_events.alerted IS
    'Flag para verificar que se envió email. Útil para reintentos si Resend falló.';

-- Constraints
ALTER TABLE provider_health_events
    DROP CONSTRAINT IF EXISTS chk_phe_status,
    DROP CONSTRAINT IF EXISTS chk_phe_severity;

ALTER TABLE provider_health_events
    ADD CONSTRAINT chk_phe_status CHECK (status IN ('healthy', 'unhealthy')),
    ADD CONSTRAINT chk_phe_severity CHECK (
        severity IS NULL OR severity IN ('critical', 'warning')
    );

-- Índice para consulta rápida del "último evento por provider"
CREATE INDEX IF NOT EXISTS idx_phe_provider_created
    ON provider_health_events (provider, created_at DESC);
