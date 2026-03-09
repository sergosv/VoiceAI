-- Migration 031: Critical production hardening
-- 1. Concurrent call limits per client
-- 2. Encrypted API key marker
-- 3. Active call tracking

-- Límite de llamadas concurrentes por cliente
ALTER TABLE clients ADD COLUMN IF NOT EXISTS max_concurrent_calls INT DEFAULT 5;

-- Tracking de llamadas activas (para enforcar límites)
CREATE TABLE IF NOT EXISTS active_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    agent_id UUID,
    room_name TEXT NOT NULL UNIQUE,
    started_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_active_calls_client ON active_calls(client_id);

-- Audit log para acciones admin (GDPR + compliance)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    client_id UUID,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    details JSONB DEFAULT '{}',
    ip_address TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_client ON audit_logs(client_id, created_at DESC);
