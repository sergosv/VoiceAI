-- ============================================
-- MIGRATION 002: Tabla users
-- Puente entre Supabase Auth y clients
-- Ejecutar en Supabase SQL Editor
-- ============================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auth_user_id UUID UNIQUE NOT NULL,  -- uid de Supabase Auth
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'client' CHECK (role IN ('admin', 'client')),
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    display_name TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_auth_user ON users(auth_user_id);
CREATE INDEX idx_users_client ON users(client_id);
CREATE INDEX idx_users_email ON users(email);

-- Trigger updated_at
CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Política temporal: service_role tiene acceso total
CREATE POLICY "Service role full access" ON users FOR ALL USING (true) WITH CHECK (true);
