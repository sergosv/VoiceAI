-- Migration 010: Orchestration mode (Modo Inteligente)
-- Permite que múltiples agentes operen en el mismo número telefónico,
-- con un coordinador ADK que rutea por intención en tiempo real.

-- clients: modo de orquestación
ALTER TABLE clients ADD COLUMN IF NOT EXISTS orchestration_mode TEXT DEFAULT 'simple';
ALTER TABLE clients ADD COLUMN IF NOT EXISTS orchestrator_model TEXT DEFAULT 'gemini-2.0-flash';
ALTER TABLE clients ADD COLUMN IF NOT EXISTS orchestrator_prompt TEXT;

-- agents: metadata para el coordinador
ALTER TABLE agents ADD COLUMN IF NOT EXISTS role_description TEXT;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS orchestrator_enabled BOOLEAN DEFAULT true;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS orchestrator_priority INTEGER DEFAULT 0;

-- calls: tracking de ruteo por turno
ALTER TABLE calls ADD COLUMN IF NOT EXISTS agent_turns JSONB DEFAULT '[]'::jsonb;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_clients_orchestration
  ON clients(orchestration_mode) WHERE orchestration_mode = 'intelligent';

CREATE INDEX IF NOT EXISTS idx_agents_orchestrator
  ON agents(client_id, orchestrator_enabled) WHERE orchestrator_enabled = true;
