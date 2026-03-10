-- Migration 036: Flow versioning for agent conversation flows

CREATE TABLE IF NOT EXISTS flow_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    version INT NOT NULL DEFAULT 1,
    label TEXT,
    flow_data JSONB NOT NULL,
    is_published BOOLEAN DEFAULT FALSE,
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(agent_id, version)
);

CREATE INDEX idx_flow_versions_agent ON flow_versions(agent_id);
CREATE INDEX idx_flow_versions_published ON flow_versions(agent_id, is_published) WHERE is_published = TRUE;

COMMENT ON TABLE flow_versions IS 'Version history for agent conversation flows';
