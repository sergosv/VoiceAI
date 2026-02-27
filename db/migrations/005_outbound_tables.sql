-- Phase 3C: Outbound Calling Engine — Campaigns
-- Ejecutar en Supabase SQL Editor

-- ╔══════════════════════════════════════════════════════╗
-- ║  Campaigns — campañas de llamadas outbound           ║
-- ╚══════════════════════════════════════════════════════╝

CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    script TEXT NOT NULL,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'running', 'paused', 'completed')),
    scheduled_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    max_concurrent INT DEFAULT 1,
    retry_attempts INT DEFAULT 2,
    retry_delay_minutes INT DEFAULT 30,
    total_contacts INT DEFAULT 0,
    completed_contacts INT DEFAULT 0,
    successful_contacts INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ╔══════════════════════════════════════════════════════╗
-- ║  Campaign Calls — llamadas individuales por campaña  ║
-- ╚══════════════════════════════════════════════════════╝

CREATE TABLE campaign_calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    call_id UUID REFERENCES calls(id) ON DELETE SET NULL,
    phone TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'calling', 'completed', 'failed', 'no_answer', 'busy', 'retry')),
    attempt INT DEFAULT 0,
    next_retry_at TIMESTAMPTZ,
    result_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_campaigns_client ON campaigns(client_id);
CREATE INDEX idx_campaign_calls_campaign ON campaign_calls(campaign_id);
CREATE INDEX idx_campaign_calls_status ON campaign_calls(campaign_id, status);

-- Triggers
CREATE TRIGGER set_campaigns_updated_at
    BEFORE UPDATE ON campaigns
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_campaign_calls_updated_at
    BEFORE UPDATE ON campaign_calls
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_calls ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_campaigns" ON campaigns
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_campaign_calls" ON campaign_calls
    FOR ALL USING (auth.role() = 'service_role');
