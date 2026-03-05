-- Migration 017: WhatsApp schedule + pause control
-- Agrega horario de operacion, pausa manual, y mensaje fuera de horario

ALTER TABLE whatsapp_configs
    ADD COLUMN IF NOT EXISTS is_paused BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS schedule JSONB,
    ADD COLUMN IF NOT EXISTS away_message TEXT NOT NULL DEFAULT 'En este momento no estamos disponibles. Te responderemos en horario de atencion.',
    ADD COLUMN IF NOT EXISTS paused_message TEXT NOT NULL DEFAULT 'En este momento un agente humano esta atendiendo. Te responderemos pronto.';

-- schedule formato ejemplo:
-- {
--   "timezone": "America/Mexico_City",
--   "mon": {"active": true, "start": "09:00", "end": "18:00"},
--   "tue": {"active": true, "start": "09:00", "end": "18:00"},
--   "wed": {"active": true, "start": "09:00", "end": "18:00"},
--   "thu": {"active": true, "start": "09:00", "end": "18:00"},
--   "fri": {"active": true, "start": "09:00", "end": "17:00"},
--   "sat": {"active": false},
--   "sun": {"active": false}
-- }
