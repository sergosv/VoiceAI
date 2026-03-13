-- Migración 041: Actualizar costos por proveedor a rates reales 2026
-- Los valores anteriores eran placeholders que no reflejaban costos de producción

UPDATE pricing_config SET
    cost_livekit_per_min = 0.004000,    -- LiveKit Cloud real
    cost_twilio_per_min = 0.013000,     -- Twilio SIP México (ya correcto)
    cost_stt_per_min = 0.004300,        -- Deepgram Nova-3 pay-as-you-go
    cost_llm_per_min = 0.003000,        -- Gemini Flash promedio por minuto
    cost_tts_per_min = 0.006000,        -- Cartesia Sonic-3 promedio por minuto
    cost_mcp_per_min = 0.000000         -- MCP no tiene costo directo
WHERE TRUE;
