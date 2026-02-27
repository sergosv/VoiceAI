-- ============================================
-- MIGRATION 003: RLS Policies para multi-tenancy
-- Ejecutar en Supabase SQL Editor
-- ============================================

-- Función helper: obtiene client_id del usuario autenticado
CREATE OR REPLACE FUNCTION get_user_client_id()
RETURNS UUID AS $$
DECLARE
    _client_id UUID;
BEGIN
    SELECT client_id INTO _client_id
    FROM users
    WHERE auth_user_id = auth.uid();
    RETURN _client_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Función helper: verifica si el usuario es admin
CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
DECLARE
    _role TEXT;
BEGIN
    SELECT role INTO _role
    FROM users
    WHERE auth_user_id = auth.uid();
    RETURN _role = 'admin';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- USERS: puede ver/editar su propio perfil, admin ve todos
-- ============================================
DROP POLICY IF EXISTS "Service role full access" ON users;

CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (
        auth_user_id = auth.uid() OR is_admin()
    );

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (
        auth_user_id = auth.uid() OR is_admin()
    );

CREATE POLICY "Admin can insert users" ON users
    FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Admin can delete users" ON users
    FOR DELETE USING (is_admin());

-- service_role bypass (para API con service key)
CREATE POLICY "Service role bypass users" ON users
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================
-- CLIENTS: client ve solo el suyo, admin ve todos
-- ============================================
DROP POLICY IF EXISTS "Service role full access" ON clients;

CREATE POLICY "Client can view own" ON clients
    FOR SELECT USING (
        id = get_user_client_id() OR is_admin()
    );

CREATE POLICY "Client can update own" ON clients
    FOR UPDATE USING (
        id = get_user_client_id() OR is_admin()
    );

CREATE POLICY "Admin can insert clients" ON clients
    FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Admin can delete clients" ON clients
    FOR DELETE USING (is_admin());

CREATE POLICY "Service role bypass clients" ON clients
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================
-- CALLS: client ve solo las suyas, admin ve todas
-- ============================================
DROP POLICY IF EXISTS "Service role full access" ON calls;

CREATE POLICY "Client can view own calls" ON calls
    FOR SELECT USING (
        client_id = get_user_client_id() OR is_admin()
    );

CREATE POLICY "Service role bypass calls" ON calls
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================
-- DOCUMENTS: client ve solo los suyos, admin ve todos
-- ============================================
DROP POLICY IF EXISTS "Service role full access" ON documents;

CREATE POLICY "Client can view own docs" ON documents
    FOR SELECT USING (
        client_id = get_user_client_id() OR is_admin()
    );

CREATE POLICY "Client can insert own docs" ON documents
    FOR INSERT WITH CHECK (
        client_id = get_user_client_id() OR is_admin()
    );

CREATE POLICY "Client can delete own docs" ON documents
    FOR DELETE USING (
        client_id = get_user_client_id() OR is_admin()
    );

CREATE POLICY "Service role bypass documents" ON documents
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================
-- USAGE_DAILY: client ve solo el suyo, admin ve todo
-- ============================================
DROP POLICY IF EXISTS "Service role full access" ON usage_daily;

CREATE POLICY "Client can view own usage" ON usage_daily
    FOR SELECT USING (
        client_id = get_user_client_id() OR is_admin()
    );

CREATE POLICY "Service role bypass usage" ON usage_daily
    FOR ALL TO service_role USING (true) WITH CHECK (true);
