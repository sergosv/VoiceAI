-- 059: Twilio Subaccounts — aislar cada cliente en su propia subcuenta Twilio
--
-- Modelo: la cuenta parent (env TWILIO_ACCOUNT_SID) crea subaccounts por cliente.
-- Cada subaccount tiene su propio Elastic SIP Trunk apuntando a LiveKit.
-- Los números se compran directamente en la subaccount (clientes nuevos)
-- o se transfieren desde main vía API (clientes grandfathered, Paso 5).
--
-- Resolución de credenciales (phone_service.resolve_twilio_creds):
--   BYOT (twilio_account_sid) > Subaccount (twilio_subaccount_sid) > Main (env)

ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS twilio_subaccount_sid TEXT,
    ADD COLUMN IF NOT EXISTS twilio_subaccount_auth_token TEXT,
    ADD COLUMN IF NOT EXISTS twilio_subaccount_status TEXT,
    ADD COLUMN IF NOT EXISTS twilio_subaccount_trunk_sid TEXT,
    ADD COLUMN IF NOT EXISTS twilio_subaccount_created_at TIMESTAMPTZ;

COMMENT ON COLUMN clients.twilio_subaccount_sid IS
    'Twilio Subaccount SID (AC...). NULL = cliente grandfathered que usa main account.';
COMMENT ON COLUMN clients.twilio_subaccount_auth_token IS
    'Auth token de la subaccount, encriptado con Fernet (prefijo enc:)';
COMMENT ON COLUMN clients.twilio_subaccount_status IS
    'provisioning | active | suspended | closed. provisioning = subaccount creada pero trunk aun no; active = subaccount+trunk listos; suspended/closed = gestionado desde admin UI.';
COMMENT ON COLUMN clients.twilio_subaccount_trunk_sid IS
    'Elastic SIP Trunk SID creado DENTRO de la subaccount (apunta a LiveKit).';
COMMENT ON COLUMN clients.twilio_subaccount_created_at IS
    'Fecha de creación de la subaccount en Twilio.';

-- Validar que status tenga valores esperados
ALTER TABLE clients
    DROP CONSTRAINT IF EXISTS chk_twilio_subaccount_status;

ALTER TABLE clients
    ADD CONSTRAINT chk_twilio_subaccount_status
    CHECK (twilio_subaccount_status IS NULL OR twilio_subaccount_status IN ('provisioning', 'active', 'suspended', 'closed'));

-- Índice para admin UI (listar subaccounts por status)
CREATE INDEX IF NOT EXISTS idx_clients_subaccount_status
    ON clients (twilio_subaccount_status)
    WHERE twilio_subaccount_sid IS NOT NULL;
