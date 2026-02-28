-- Migration 008: Mejora de calidad conversacional y manejo de datos
-- Feature 2: conversation_examples para few-shot
ALTER TABLE clients ADD COLUMN IF NOT EXISTS conversation_examples TEXT;

-- Feature 6: tracking de contactos
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS call_count INT DEFAULT 0;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS last_call_at TIMESTAMPTZ;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS lead_score INT DEFAULT 0;

-- Feature 5: análisis IA universal en calls
ALTER TABLE calls ADD COLUMN IF NOT EXISTS sentimiento TEXT;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS intencion TEXT;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS lead_score INT;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS siguiente_accion TEXT;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS resumen_ia TEXT;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS preguntas_sin_respuesta JSONB;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contacts_lead_score ON contacts(client_id, lead_score DESC) WHERE lead_score > 0;
CREATE INDEX IF NOT EXISTS idx_contacts_last_call ON contacts(client_id, last_call_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_calls_sentimiento ON calls(client_id, sentimiento) WHERE sentimiento IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_calls_lead_score ON calls(client_id, lead_score DESC) WHERE lead_score IS NOT NULL;
