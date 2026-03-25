-- BYOT (Bring Your Own Twilio): permite a clientes usar su propia cuenta Twilio
ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS twilio_account_sid TEXT,
  ADD COLUMN IF NOT EXISTS twilio_auth_token TEXT;  -- almacenado encriptado con Fernet

COMMENT ON COLUMN clients.twilio_account_sid IS 'BYOT: client Twilio Account SID';
COMMENT ON COLUMN clients.twilio_auth_token IS 'BYOT: client Twilio Auth Token (encrypted with Fernet)';
