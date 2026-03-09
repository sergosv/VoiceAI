-- Migration 030: Call evaluations, failure detection, quality alerts, tool traces
-- Fase 14: Quality Firewall — silent failure detection system

-- Evaluaciones de llamadas
CREATE TABLE IF NOT EXISTS call_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    client_id UUID NOT NULL,
    agent_id UUID,
    overall_score INT CHECK (overall_score >= -1 AND overall_score <= 100),
    failures_found INT DEFAULT 0,
    critical_failures INT DEFAULT 0,
    evaluation_data JSONB DEFAULT '{}',
    status TEXT DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed')),
    evaluated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Fallos individuales detectados
CREATE TABLE IF NOT EXISTS evaluation_failures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES call_evaluations(id) ON DELETE CASCADE,
    call_id UUID NOT NULL,
    client_id UUID NOT NULL,
    failure_type TEXT NOT NULL CHECK (failure_type IN (
        'unauthorized_commitment', 'hallucination', 'rag_miss',
        'tool_error', 'prompt_leak', 'context_drift',
        'guardrail_bypass', 'wrong_escalation'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description TEXT NOT NULL,
    evidence TEXT,
    turn_index INT,
    recommendation TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Alertas de calidad
CREATE TABLE IF NOT EXISTS quality_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    agent_id UUID,
    call_id UUID,
    evaluation_id UUID REFERENCES call_evaluations(id) ON DELETE SET NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    acknowledged BOOLEAN DEFAULT false,
    acknowledged_by UUID,
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Trazas de tool calls por llamada
CREATE TABLE IF NOT EXISTS call_tool_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    tool_params JSONB DEFAULT '{}',
    tool_result JSONB DEFAULT '{}',
    duration_ms INT,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    turn_index INT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_call_evaluations_client ON call_evaluations(client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_call_evaluations_call ON call_evaluations(call_id);
CREATE INDEX IF NOT EXISTS idx_call_evaluations_score ON call_evaluations(overall_score);
CREATE INDEX IF NOT EXISTS idx_evaluation_failures_type ON evaluation_failures(failure_type);
CREATE INDEX IF NOT EXISTS idx_evaluation_failures_severity ON evaluation_failures(severity);
CREATE INDEX IF NOT EXISTS idx_evaluation_failures_client ON evaluation_failures(client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quality_alerts_client ON quality_alerts(client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quality_alerts_unack ON quality_alerts(client_id, acknowledged) WHERE NOT acknowledged;
CREATE INDEX IF NOT EXISTS idx_call_tool_traces_call ON call_tool_traces(call_id);
