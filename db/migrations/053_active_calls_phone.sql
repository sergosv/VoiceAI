-- 053: Agregar phone a active_calls para validar concurrencia con mismo número

ALTER TABLE active_calls
    ADD COLUMN IF NOT EXISTS phone TEXT;

CREATE INDEX IF NOT EXISTS idx_active_calls_phone
    ON active_calls (phone);

COMMENT ON COLUMN active_calls.phone IS 'Número de teléfono normalizado (E.164) para evitar llamadas duplicadas';
