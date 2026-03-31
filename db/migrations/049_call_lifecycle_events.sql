-- Migration 049: Call Lifecycle Events
-- Trazabilidad completa del ciclo de vida de cada llamada:
-- quién colgó, cuánto sonó vs cuánto habló, qué pasó en cada momento.

-- ============================================
-- Nuevos campos en calls para métricas de lifecycle
-- ============================================
ALTER TABLE calls ADD COLUMN IF NOT EXISTS agent_id UUID REFERENCES agents(id) ON DELETE SET NULL;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS ring_duration_seconds INT;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS talk_duration_seconds INT;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS disconnect_reason TEXT CHECK (
    disconnect_reason IS NULL OR disconnect_reason IN (
        'caller_hangup',       -- El usuario/caller colgó
        'agent_hangup',        -- El agente terminó la llamada
        'transfer',            -- Se transfirió a otro destino
        'no_answer',           -- Nadie contestó (outbound timeout)
        'busy',                -- Línea ocupada
        'timeout_inactivity',  -- Timeout por silencio/inactividad
        'timeout_max_duration',-- Se alcanzó duración máxima
        'error_sip',           -- Error de protocolo SIP
        'error_media',         -- Error de audio/media
        'error_agent',         -- Error en el agente (crash)
        'rejected',            -- Llamada rechazada
        'voicemail'            -- Entró a buzón de voz
    )
);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS disconnect_by TEXT CHECK (
    disconnect_by IS NULL OR disconnect_by IN ('caller', 'agent', 'system', 'transfer')
);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS disposition TEXT CHECK (
    disposition IS NULL OR disposition IN (
        'completed',           -- Conversación completa
        'short_call',          -- Contestó pero colgó rápido (<15s de conversación)
        'abandoned',           -- Colgó antes de que el agente hablara
        'no_answer',           -- No contestó
        'busy',                -- Ocupado
        'voicemail',           -- Buzón de voz
        'transferred',         -- Transferida exitosamente
        'error'                -- Error técnico
    )
);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS first_speech_at TIMESTAMPTZ;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS answered_at TIMESTAMPTZ;

-- ============================================
-- Tabla: call_events
-- Timeline de eventos del ciclo de vida de cada llamada
-- ============================================
CREATE TABLE IF NOT EXISTS call_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID REFERENCES calls(id) ON DELETE CASCADE,
    room_name TEXT NOT NULL,
    event TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_call_events_call_id ON call_events(call_id);
CREATE INDEX IF NOT EXISTS idx_call_events_room_name ON call_events(room_name);
CREATE INDEX IF NOT EXISTS idx_call_events_event ON call_events(event);

-- Comentarios para documentar los eventos posibles
COMMENT ON TABLE call_events IS 'Timeline de eventos del ciclo de vida de cada llamada';
COMMENT ON COLUMN call_events.event IS 'Eventos: call_initiated, sip_ringing, sip_answered, agent_ready, first_speech_user, first_speech_agent, user_hangup, agent_hangup, transfer_started, transfer_completed, call_ended, error';
