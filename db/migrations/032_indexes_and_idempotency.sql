-- Migration 032: Missing indexes + payment idempotency constraint
-- Fixes identified in fourth-pass audit

-- Indexes para búsquedas frecuentes por teléfono en calls
CREATE INDEX IF NOT EXISTS idx_calls_caller_number ON calls(caller_number);
CREATE INDEX IF NOT EXISTS idx_calls_callee_number ON calls(callee_number);

-- Index para búsquedas de campaign_calls por teléfono + campaign
CREATE INDEX IF NOT EXISTS idx_campaign_calls_phone ON campaign_calls(campaign_id, phone);

-- Idempotencia en pagos: evitar doble crédito por mismo payment_id
CREATE UNIQUE INDEX IF NOT EXISTS uk_credit_tx_payment
    ON credit_transactions(payment_provider, payment_id)
    WHERE payment_id IS NOT NULL;

-- Cleanup: index para sweep de active_calls stale
CREATE INDEX IF NOT EXISTS idx_active_calls_started ON active_calls(started_at);
