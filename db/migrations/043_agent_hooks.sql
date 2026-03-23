-- Lifecycle hooks para agentes — reglas determinísticas por evento y canal
-- Los hooks se evalúan en orden de priority (menor = primero)

CREATE TABLE IF NOT EXISTS agent_hooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    -- Evento del lifecycle
    hook_event TEXT NOT NULL CHECK (hook_event IN (
        'OnConversationStart', 'OnGreeting',
        'OnUserMessage', 'PreResponse', 'PostResponse',
        'PreToolCall', 'PostToolCall',
        'OnInactivity', 'OnSentimentShift', 'OnLanguageSwitch', 'OnGuardrailHit',
        'OnEscalation', 'OnConversationEnd', 'PostConversationEnd'
    )),
    -- Nombre descriptivo de la regla
    name TEXT NOT NULL DEFAULT '',
    -- Canal al que aplica (NULL = todos)
    channel TEXT CHECK (channel IS NULL OR channel IN ('voice', 'whatsapp', 'widget', 'ghl')),
    -- Tipo de hook
    hook_type TEXT NOT NULL CHECK (hook_type IN ('rule', 'validate', 'prompt', 'notify', 'transform')),
    -- Matcher: nombre de tool (para PreToolCall/PostToolCall) o '*' para todos
    matcher TEXT NOT NULL DEFAULT '*',
    -- Configuración completa del hook (conditions, action, message, etc.)
    config JSONB NOT NULL DEFAULT '{}',
    -- Orden de evaluación (menor = primero)
    priority INT NOT NULL DEFAULT 100,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Índice principal: buscar hooks activos de un agente por evento
CREATE INDEX IF NOT EXISTS idx_agent_hooks_agent_event
    ON agent_hooks(agent_id, hook_event) WHERE enabled = true;

-- Índice para listar por cliente
CREATE INDEX IF NOT EXISTS idx_agent_hooks_client
    ON agent_hooks(client_id);

-- RLS
ALTER TABLE agent_hooks ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_hooks_select ON agent_hooks
    FOR SELECT USING (
        auth.uid() IN (
            SELECT u.auth_user_id FROM users u
            WHERE u.role = 'admin'
               OR u.client_id = agent_hooks.client_id
        )
    );

CREATE POLICY agent_hooks_insert ON agent_hooks
    FOR INSERT WITH CHECK (
        auth.uid() IN (
            SELECT u.auth_user_id FROM users u
            WHERE u.role = 'admin'
               OR u.client_id = agent_hooks.client_id
        )
    );

CREATE POLICY agent_hooks_update ON agent_hooks
    FOR UPDATE USING (
        auth.uid() IN (
            SELECT u.auth_user_id FROM users u
            WHERE u.role = 'admin'
               OR u.client_id = agent_hooks.client_id
        )
    );

CREATE POLICY agent_hooks_delete ON agent_hooks
    FOR DELETE USING (
        auth.uid() IN (
            SELECT u.auth_user_id FROM users u
            WHERE u.role = 'admin'
               OR u.client_id = agent_hooks.client_id
        )
    );

COMMENT ON TABLE agent_hooks IS 'Lifecycle hooks: reglas determinísticas que se ejecutan en eventos específicos del agente';
COMMENT ON COLUMN agent_hooks.hook_event IS 'Evento del lifecycle: OnConversationStart, PreToolCall, PreResponse, etc.';
COMMENT ON COLUMN agent_hooks.channel IS 'Canal: voice, whatsapp, widget, ghl. NULL = aplica a todos';
COMMENT ON COLUMN agent_hooks.hook_type IS 'Tipo: rule (if/then), validate (datos), prompt (LLM check), notify (side-effect), transform (modifica)';
COMMENT ON COLUMN agent_hooks.matcher IS 'Para Pre/PostToolCall: nombre del tool. Para otros: * (todos)';
COMMENT ON COLUMN agent_hooks.config IS 'JSON con conditions, action, message, template, etc. según hook_type';
