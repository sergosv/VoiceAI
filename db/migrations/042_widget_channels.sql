-- Agregar widget_channels a agents para configurar qué canales habilita el widget
-- Valores posibles en el array: 'chat', 'voice'
ALTER TABLE agents ADD COLUMN IF NOT EXISTS widget_channels TEXT[] DEFAULT ARRAY['voice'];

COMMENT ON COLUMN agents.widget_channels IS 'Canales habilitados en el widget embeddable: chat, voice, o ambos';
