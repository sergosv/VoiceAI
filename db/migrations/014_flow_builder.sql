-- Migration 014: Flow Builder
-- Agrega soporte para flujos de conversación visuales en agentes.

-- Modo de conversación: 'prompt' (system prompt libre) o 'flow' (flujo visual)
ALTER TABLE agents
ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'prompt'
CHECK (conversation_mode IN ('prompt', 'flow'));

-- Flujo de conversación en formato React Flow JSON (nodos + edges)
ALTER TABLE agents
ADD COLUMN IF NOT EXISTS conversation_flow JSONB;

-- Index para queries por modo
CREATE INDEX IF NOT EXISTS idx_agents_conversation_mode ON agents (conversation_mode);
