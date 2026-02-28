-- Migration 007: Agregar columna de análisis IA a campaign_calls
-- Ejecutar en Supabase SQL Editor

ALTER TABLE campaign_calls ADD COLUMN IF NOT EXISTS analysis_data JSONB;

-- Índice para filtrar por resultado del análisis
CREATE INDEX IF NOT EXISTS idx_campaign_calls_analysis_result
ON campaign_calls ((analysis_data->>'result'))
WHERE analysis_data IS NOT NULL;

COMMENT ON COLUMN campaign_calls.analysis_data IS 'Análisis IA post-llamada: result, confidence, contact_name, contact_email, objections, next_step, summary, sentiment';
