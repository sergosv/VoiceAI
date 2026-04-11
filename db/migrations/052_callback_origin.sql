-- 052: Origen de scheduled_callbacks
-- Saber si el callback se prometió en una llamada inbound o en una campaña outbound,
-- para usar el system_prompt correcto al ejecutarlo.

ALTER TABLE scheduled_callbacks
    ADD COLUMN IF NOT EXISTS origin_type TEXT
        CHECK (origin_type IN ('inbound', 'outbound', 'campaign')),
    ADD COLUMN IF NOT EXISTS campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_scheduled_callbacks_origin_type
    ON scheduled_callbacks (origin_type);

COMMENT ON COLUMN scheduled_callbacks.origin_type IS 'Origen del callback: inbound (cliente nos llamó), outbound (llamada manual), campaign (campaña outbound)';
COMMENT ON COLUMN scheduled_callbacks.campaign_id IS 'Si origin_type=campaign, ID de la campaña para recuperar el script';
