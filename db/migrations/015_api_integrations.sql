-- Migration 015: API Integrations
-- Endpoints HTTP configurables como tools del agente (sin necesidad de MCP server)

CREATE TABLE api_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    url TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'POST' CHECK (method IN ('GET','POST','PUT','PATCH','DELETE')),
    headers JSONB DEFAULT '{}',
    body_template JSONB,
    query_params JSONB DEFAULT '{}',
    auth_type TEXT DEFAULT 'none' CHECK (auth_type IN ('none','bearer','api_key','basic','custom_header')),
    auth_config JSONB DEFAULT '{}',
    response_type TEXT DEFAULT 'json' CHECK (response_type IN ('json','text')),
    response_path TEXT DEFAULT '',
    agent_ids JSONB,
    is_active BOOLEAN DEFAULT true,
    input_schema JSONB DEFAULT '{"parameters":[]}',
    last_tested_at TIMESTAMPTZ,
    last_test_status TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(client_id, name)
);

CREATE INDEX idx_api_integrations_active ON api_integrations(client_id, is_active);

ALTER TABLE api_integrations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_api_integrations" ON api_integrations
    FOR ALL USING (auth.role() = 'service_role');
