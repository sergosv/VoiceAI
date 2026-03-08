-- Migration 023: Conversation Lifecycle Management
-- Timeouts por canal, resumen automático, cierre por IA/timeout/manual.

-- ── ghl_configs: timeouts por canal ─────────────────────
ALTER TABLE ghl_configs
  ADD COLUMN IF NOT EXISTS channel_timeouts JSONB NOT NULL DEFAULT '{
    "webchat": 10, "whatsapp": 60, "sms": 60,
    "facebook": 30, "instagram": 30, "email": 1440
  }'::jsonb;

-- ── Campos de cierre en ambas tablas de conversaciones ──

ALTER TABLE whatsapp_conversations
  ADD COLUMN IF NOT EXISTS summary TEXT,
  ADD COLUMN IF NOT EXISTS result TEXT,
  ADD COLUMN IF NOT EXISTS closed_by TEXT CHECK (closed_by IN ('ai', 'timeout', 'manual'));

ALTER TABLE ghl_conversations
  ADD COLUMN IF NOT EXISTS summary TEXT,
  ADD COLUMN IF NOT EXISTS result TEXT,
  ADD COLUMN IF NOT EXISTS closed_by TEXT CHECK (closed_by IN ('ai', 'timeout', 'manual'));
