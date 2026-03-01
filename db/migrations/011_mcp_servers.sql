-- Migración 011: MCP Servers
-- Servidores MCP configurables por cliente para conectar agentes a sistemas externos

-- ── Tabla principal ─────────────────────────────────
CREATE TABLE mcp_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    connection_type TEXT NOT NULL DEFAULT 'http'
        CHECK (connection_type IN ('http', 'stdio')),

    -- HTTP config
    url TEXT,
    transport_type TEXT DEFAULT 'sse'
        CHECK (transport_type IN ('sse', 'streamable_http')),
    headers JSONB DEFAULT '{}',

    -- Stdio config
    command TEXT,
    command_args JSONB DEFAULT '[]',

    -- Shared
    env_vars JSONB DEFAULT '{}',
    allowed_tools JSONB,          -- null = todos, array = whitelist
    agent_ids JSONB,              -- null = todos los agentes, array = específicos
    is_active BOOLEAN DEFAULT true,
    tools_cache JSONB,            -- cache de tool schemas para UI
    last_connected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(client_id, name)
);

CREATE INDEX idx_mcp_servers_active ON mcp_servers(client_id, is_active);

ALTER TABLE mcp_servers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_mcp" ON mcp_servers
    FOR ALL USING (auth.role() = 'service_role');

-- ── Templates de MCP servers populares ──────────────
CREATE TABLE mcp_server_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    icon TEXT,                     -- nombre de ícono Lucide
    category TEXT DEFAULT 'general',
    connection_type TEXT NOT NULL DEFAULT 'http',
    default_url TEXT,
    default_transport_type TEXT DEFAULT 'sse',
    default_command TEXT,
    default_command_args JSONB DEFAULT '[]',
    required_env_vars JSONB DEFAULT '[]',  -- ["API_KEY", "WORKSPACE_ID"]
    documentation_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE mcp_server_templates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_templates" ON mcp_server_templates
    FOR ALL USING (auth.role() = 'service_role');
-- Lectura pública de templates
CREATE POLICY "read_templates" ON mcp_server_templates
    FOR SELECT USING (true);

-- ── Seed: templates populares ───────────────────────
INSERT INTO mcp_server_templates (name, description, icon, category, connection_type, default_url, required_env_vars, documentation_url) VALUES
    ('Slack', 'Enviar mensajes y notificaciones a canales de Slack', 'MessageSquare', 'comunicacion', 'http', 'https://mcp.composio.dev/slack', '["COMPOSIO_API_KEY"]', 'https://docs.composio.dev/apps/slack'),
    ('HubSpot', 'CRM: contactos, deals, empresas y actividades', 'Users', 'crm', 'http', 'https://mcp.composio.dev/hubspot', '["COMPOSIO_API_KEY"]', 'https://docs.composio.dev/apps/hubspot'),
    ('Google Sheets', 'Leer y escribir hojas de cálculo de Google', 'Table2', 'productividad', 'http', 'https://mcp.composio.dev/googlesheets', '["COMPOSIO_API_KEY"]', 'https://docs.composio.dev/apps/google-sheets'),
    ('Google Drive', 'Buscar y gestionar archivos en Google Drive', 'HardDrive', 'productividad', 'http', 'https://mcp.composio.dev/googledrive', '["COMPOSIO_API_KEY"]', 'https://docs.composio.dev/apps/google-drive'),
    ('Stripe', 'Pagos, suscripciones y clientes de Stripe', 'CreditCard', 'pagos', 'http', 'https://mcp.composio.dev/stripe', '["COMPOSIO_API_KEY"]', 'https://docs.composio.dev/apps/stripe'),
    ('Notion', 'Bases de datos, páginas y bloques de Notion', 'BookOpen', 'productividad', 'http', 'https://mcp.composio.dev/notion', '["COMPOSIO_API_KEY"]', 'https://docs.composio.dev/apps/notion'),
    ('Gmail', 'Leer y enviar correos electrónicos', 'Mail', 'comunicacion', 'http', 'https://mcp.composio.dev/gmail', '["COMPOSIO_API_KEY"]', 'https://docs.composio.dev/apps/gmail'),
    ('Airtable', 'Bases de datos y registros de Airtable', 'Database', 'productividad', 'http', 'https://mcp.composio.dev/airtable', '["COMPOSIO_API_KEY"]', 'https://docs.composio.dev/apps/airtable'),
    ('Shopify', 'Productos, órdenes y clientes de Shopify', 'ShoppingBag', 'ecommerce', 'http', 'https://mcp.composio.dev/shopify', '["COMPOSIO_API_KEY"]', 'https://docs.composio.dev/apps/shopify'),
    ('Salesforce', 'CRM empresarial: leads, oportunidades, cuentas', 'Briefcase', 'crm', 'http', 'https://mcp.composio.dev/salesforce', '["COMPOSIO_API_KEY"]', 'https://docs.composio.dev/apps/salesforce');
