-- Phase 3A: Contacts, Appointments, y columnas de integración
-- Ejecutar en Supabase SQL Editor

-- ╔══════════════════════════════════════════════════════╗
-- ║  Contacts — capturados de llamadas o manuales       ║
-- ╚══════════════════════════════════════════════════════╝

CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT,
    phone TEXT NOT NULL,
    email TEXT,
    source TEXT DEFAULT 'inbound_call',
    notes TEXT,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_contacts_client ON contacts(client_id);
CREATE INDEX idx_contacts_phone ON contacts(client_id, phone);
CREATE UNIQUE INDEX idx_contacts_client_phone ON contacts(client_id, phone);

-- ╔══════════════════════════════════════════════════════╗
-- ║  Appointments — agendadas por el agente o manual    ║
-- ╚══════════════════════════════════════════════════════╝

CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    call_id UUID REFERENCES calls(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    status TEXT DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled', 'completed', 'no_show')),
    google_event_id TEXT,
    reminder_sent BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_appointments_client ON appointments(client_id);
CREATE INDEX idx_appointments_time ON appointments(client_id, start_time);
CREATE INDEX idx_appointments_contact ON appointments(contact_id);

-- ╔══════════════════════════════════════════════════════╗
-- ║  Nuevas columnas en clients para integraciones      ║
-- ╚══════════════════════════════════════════════════════╝

ALTER TABLE clients ADD COLUMN IF NOT EXISTS google_calendar_id TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS google_service_account_key JSONB;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS whatsapp_instance_id TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS whatsapp_api_url TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS whatsapp_api_key TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS enabled_tools TEXT[] DEFAULT '{"search_knowledge"}';

-- ╔══════════════════════════════════════════════════════╗
-- ║  updated_at triggers                                ║
-- ╚══════════════════════════════════════════════════════╝

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_contacts_updated_at
    BEFORE UPDATE ON contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_appointments_updated_at
    BEFORE UPDATE ON appointments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ╔══════════════════════════════════════════════════════╗
-- ║  RLS Policies                                       ║
-- ╚══════════════════════════════════════════════════════╝

ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

-- Service role tiene acceso total (el API usa service_role key)
CREATE POLICY "service_role_contacts" ON contacts
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_appointments" ON appointments
    FOR ALL USING (auth.role() = 'service_role');
