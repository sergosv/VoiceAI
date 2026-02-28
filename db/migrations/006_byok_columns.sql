-- Migration 006: BYOK (Bring Your Own Key) columns para voice pipeline
-- Permite a cada cliente configurar su propio pipeline de voz

ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS voice_mode TEXT DEFAULT 'pipeline'
    CHECK (voice_mode IN ('pipeline', 'realtime')),
  ADD COLUMN IF NOT EXISTS stt_provider TEXT DEFAULT 'deepgram'
    CHECK (stt_provider IN ('deepgram', 'google', 'openai')),
  ADD COLUMN IF NOT EXISTS llm_provider TEXT DEFAULT 'google'
    CHECK (llm_provider IN ('google', 'openai', 'anthropic')),
  ADD COLUMN IF NOT EXISTS tts_provider TEXT DEFAULT 'cartesia'
    CHECK (tts_provider IN ('cartesia', 'elevenlabs', 'openai')),
  ADD COLUMN IF NOT EXISTS stt_api_key TEXT,
  ADD COLUMN IF NOT EXISTS llm_api_key TEXT,
  ADD COLUMN IF NOT EXISTS tts_api_key TEXT,
  ADD COLUMN IF NOT EXISTS realtime_api_key TEXT,
  ADD COLUMN IF NOT EXISTS realtime_voice TEXT DEFAULT 'alloy',
  ADD COLUMN IF NOT EXISTS realtime_model TEXT DEFAULT 'gpt-4o-realtime-preview';

COMMENT ON COLUMN clients.voice_mode IS 'pipeline = STT+LLM+TTS, realtime = OpenAI Realtime API';
COMMENT ON COLUMN clients.stt_api_key IS 'NULL = usar key de la plataforma';
COMMENT ON COLUMN clients.llm_api_key IS 'NULL = usar key de la plataforma';
COMMENT ON COLUMN clients.tts_api_key IS 'NULL = usar key de la plataforma';
COMMENT ON COLUMN clients.realtime_api_key IS 'API key de OpenAI para modo realtime';
