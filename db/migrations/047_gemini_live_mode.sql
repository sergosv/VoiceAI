-- Migration 047: Add gemini_live to agent_mode CHECK constraint
-- Permite usar Gemini 3.1 Flash Live como provider de audio-to-audio nativo

-- Eliminar constraint existente y recrear con nuevo valor
ALTER TABLE agents DROP CONSTRAINT IF EXISTS agents_agent_mode_check;
ALTER TABLE agents ADD CONSTRAINT agents_agent_mode_check
    CHECK (agent_mode IN ('pipeline', 'realtime', 'gemini_live'));
