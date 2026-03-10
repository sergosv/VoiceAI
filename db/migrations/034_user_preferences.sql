-- ============================================
-- MIGRATION 034: User preferences columns
-- Agrega timezone y language al usuario
-- ============================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'America/Mexico_City';
ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'es';

COMMENT ON COLUMN users.timezone IS 'Zona horaria preferida del usuario (IANA)';
COMMENT ON COLUMN users.language IS 'Idioma preferido de la interfaz: es, en';
