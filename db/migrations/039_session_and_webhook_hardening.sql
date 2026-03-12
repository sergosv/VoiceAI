-- Migración 039: Session invalidation + webhook DLQ

-- 1. password_changed_at para invalidar sesiones después de cambio de password
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ DEFAULT NULL;
COMMENT ON COLUMN users.password_changed_at IS 'Timestamp del último cambio de password; JWTs emitidos antes de esta fecha son inválidos';

-- 2. Webhook DLQ: status en deliveries para rastrear entregas agotadas
ALTER TABLE webhook_deliveries ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
COMMENT ON COLUMN webhook_deliveries.status IS 'Estado: pending, delivered, failed, dead_letter';

-- Índice para listar DLQ fácilmente
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_status
    ON webhook_deliveries(status) WHERE status = 'dead_letter';
