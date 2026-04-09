-- 051: Do-Not-Call (DNC) list — protección contra llamadas a números bloqueados

CREATE TABLE IF NOT EXISTS dnc_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    reason TEXT,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'user_request', 'escalation', 'import')),
    added_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Un número solo puede estar una vez por cliente
CREATE UNIQUE INDEX IF NOT EXISTS idx_dnc_client_phone
    ON dnc_entries (client_id, phone);

CREATE INDEX IF NOT EXISTS idx_dnc_phone
    ON dnc_entries (phone);

COMMENT ON TABLE dnc_entries IS 'Lista de números que no deben recibir llamadas outbound';
COMMENT ON COLUMN dnc_entries.source IS 'Origen: manual (dashboard), user_request (usuario pidió no llamar), escalation (agente detectó molestia), import (carga masiva)';
