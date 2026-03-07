# Voice AI Platform — Arquitectura Completa
## Plataforma Multi-Tenant de Agentes de Voz con IA

**Proyecto**: voice-ai-platform  
**Owner**: Sergio / Innotecnia  
**Fecha**: Marzo 2026
**Mercado objetivo**: México / LATAM  
**Visión**: Construir un VAPI/Retell propio — plataforma SaaS donde cada cliente obtiene su agente de voz personalizado con número telefónico, knowledge base, y dashboard.

---

## Stack Definitivo

| Componente | Tecnología | Modelo/Versión |
|---|---|---|
| **Orquestación** | LiveKit Cloud (Plan Build) | Agents Framework (Python) |
| **STT** | Deepgram (default) | Nova-3 + Flux — BYOK: Google, OpenAI |
| **LLM** | Google Gemini (default) | gemini-2.5-flash — BYOK: OpenAI, Anthropic |
| **RAG** | Gemini File Search | Vector stores nativos por cliente |
| **TTS** | Cartesia (default) | Sonic 3 — BYOK: ElevenLabs, OpenAI |
| **Telefonía** | Twilio | SIP Trunking → LiveKit SIP |
| **Base de Datos** | Supabase | PostgreSQL + Auth + Realtime |
| **Backend API** | Python FastAPI | Para admin endpoints |
| **Frontend Dashboard** | React + Tailwind | SaaS Dashboard (Fase 2) |
| **Hosting Agent** | LiveKit Cloud | `lk deploy` — LiveKit hostea el agente |
| **Hosting API + Dashboard** | Railway | FastAPI sirve API + React static build |
| **Hosting DB** | Supabase Cloud | Proyecto: `voice-ai-platform` |

### Costo estimado por llamada de 3 minutos
```
LiveKit infra:     $0.03
Deepgram Nova-3:   $0.015  
Gemini 3 Flash:    $0.03
Cartesia Sonic 3:  $0.03
Twilio SIP:        $0.03
────────────────────────
TOTAL:             ~$0.135 USD (~2.70 MXN)
```

---

## Hosting — Arquitectura de Deploy

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARQUITECTURA DE HOSTING                       │
│                                                                  │
│  ┌─── LiveKit Cloud ──────────────┐                             │
│  │  Voice Agent (Python)          │  ← lk deploy               │
│  │  Procesa llamadas en tiempo    │  ← Plan Build ($0 base)    │
│  │  real. Proceso persistente     │  ← 1,000 min incluidos     │
│  │  con WebSocket connections.    │                             │
│  └────────────────────────────────┘                             │
│           │                                                      │
│           │ (queries DB, logs llamadas)                          │
│           ▼                                                      │
│  ┌─── Supabase Cloud ────────────┐                              │
│  │  PostgreSQL (voice-ai-platform)│  ← Free tier / Pro $25     │
│  │  Auth, Realtime, RLS          │                              │
│  │  Tablas: clients, calls,      │                              │
│  │  documents, usage_daily       │                              │
│  └────────────────────────────────┘                             │
│           ▲                                                      │
│           │ (CRUD, auth, realtime)                               │
│           │                                                      │
│  ┌─── Railway ────────────────────┐                             │
│  │  FastAPI + React Dashboard     │  ← Un solo servicio        │
│  │  /api/* → FastAPI endpoints    │  ← railway.app domain      │
│  │  /*     → React static build   │  ← ~$5-10/mes              │
│  │                                │                             │
│  │  FastAPI sirve:                │                             │
│  │  - API admin (CRUD clientes)   │                             │
│  │  - Webhooks (Twilio/LiveKit)   │                             │
│  │  - Dashboard React (static)    │                             │
│  └────────────────────────────────┘                             │
│                                                                  │
│  Servicios externos:                                             │
│  • Twilio (SIP/telefonía) → LiveKit Cloud                       │
│  • Deepgram (STT) → LiveKit Agent                               │
│  • Gemini (LLM + File Search) → LiveKit Agent                   │
│  • Cartesia (TTS) → LiveKit Agent                               │
└─────────────────────────────────────────────────────────────────┘
```

### FastAPI sirve el Dashboard (un solo deploy)
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# API endpoints
app.include_router(api_router, prefix="/api")

# Dashboard React (build estático)
app.mount("/", StaticFiles(directory="dashboard/dist", html=True), name="dashboard")
```

### Railway Deploy
```bash
# Dockerfile único que:
# 1. Instala dependencias Python
# 2. Hace build de React (npm run build)
# 3. Corre FastAPI con uvicorn
# Un solo servicio, un solo dominio
```

### Costo mensual estimado de hosting
```
LiveKit Cloud (Build):  $0 base + $0.01/min overage
Railway (API+Dashboard): ~$5-10/mes
Supabase (Free/Pro):     $0-25/mes
────────────────────────
TOTAL hosting:          ~$5-35/mes
```

```
voice-ai-platform/
├── ARCHITECTURE.md          # Este archivo
├── CLAUDE.md                # Instrucciones para Claude Code
├── .env.example             # Template de variables de entorno
├── .env                     # Variables reales (gitignored)
├── requirements.txt         # Dependencias Python
├── Dockerfile               # Para deploy del agente en LiveKit Cloud
├── Dockerfile.railway       # Para deploy de API+Dashboard en Railway
├── livekit.toml             # Config LiveKit agent
│
├── agent/                   # === CORE: LiveKit Voice Agent ===
│   ├── main.py              # Entrypoint LiveKit agent (AgentServer + rtc_session)
│   ├── agent_factory.py     # Crea agentes dinámicos por cliente (VoiceAgent + voice rules)
│   ├── pipeline_builder.py  # Factory BYOK: build_stt(), build_llm(), build_tts(), build_realtime_model()
│   ├── session_handler.py   # Maneja lifecycle de cada llamada (transcript, costs, DB)
│   ├── config_loader.py     # Carga config de agente+cliente desde DB (by phone/agent_id/client_id)
│   ├── billing.py           # CallBilling — créditos por llamada (1 crédito = 1 min)
│   ├── memory.py            # AgentMemory — memoria de largo plazo por contacto
│   ├── orchestrator.py      # Multi-agente: OrchestratorAgent con routing por turno (Gemini ADK)
│   ├── mcp_builder.py       # Construye MCPServerHTTP/Stdio desde config DB
│   ├── db.py                # Supabase client singleton para el proceso agente
│   ├── call_analyzer.py     # Análisis post-llamada con Gemini (outbound campaigns)
│   ├── phone_utils.py       # Utilidades de números telefónicos
│   ├── voice_quality.py     # Filler phrases, backchannels, timing
│   └── tools/               # Herramientas que el agente puede usar (@function_tool)
│       ├── __init__.py
│       ├── file_search.py   # Gemini File Search por cliente
│       ├── calendar_tool.py # Google Calendar — agendar citas
│       ├── whatsapp_tool.py # Evolution API — enviar WhatsApp
│       └── crm_tool.py      # CRM — guardar/actualizar contactos
│
├── admin/                   # === ADMIN: Scripts de gestión ===
│   ├── cli.py               # CLI principal con typer
│   ├── create_client.py     # Crear cliente + FileSearchStore
│   ├── upload_docs.py       # Subir docs al store del cliente
│   ├── assign_phone.py      # Asignar número Twilio + SIP trunk
│   ├── list_clients.py      # Listar clientes activos
│   ├── outbound.py          # Disparar llamadas salientes
│   └── test_call.py         # Test rápido de un agente
│
├── api/                     # === API: FastAPI endpoints ===
│   ├── main.py              # FastAPI app (API + static dashboard + rate limiter)
│   ├── deps.py              # Dependencias comunes (Supabase singleton)
│   ├── schemas.py           # Pydantic v2 models + field validators
│   ├── logging_config.py    # Structured logging + correlation IDs (RequestIdMiddleware)
│   ├── middleware/
│   │   └── auth.py          # Supabase JWT auth (ES256 via JWKS)
│   ├── routes/
│   │   ├── auth.py          # Login, signup, me, forgot-password
│   │   ├── clients.py       # CRUD clientes
│   │   ├── agents.py        # CRUD agentes + assign/purchase phone
│   │   ├── calls.py         # Historial de llamadas
│   │   ├── documents.py     # Upload/manage docs (File Search, 50MB limit)
│   │   ├── contacts.py      # CRM contactos
│   │   ├── appointments.py  # CRM citas
│   │   ├── campaigns.py     # Campañas outbound
│   │   ├── voices.py        # Catálogo de voces (Cartesia, ElevenLabs, OpenAI)
│   │   ├── dashboard.py     # Stats para dashboard principal
│   │   ├── chat.py          # Chat tester (probar agentes via texto)
│   │   ├── ai.py            # Generación/mejora de prompts con IA
│   │   ├── billing.py       # Balance, packages, transactions, purchase, gift
│   │   ├── webhooks.py      # Stripe (firma verificada) + MercadoPago webhooks
│   │   ├── mcp.py           # MCP server CRUD + templates
│   │   ├── api_integrations.py  # API integrations CRUD
│   │   ├── whatsapp.py      # WhatsApp config + inbox
│   │   ├── whatsapp_webhooks.py # WhatsApp inbound webhooks
│   │   ├── evolution.py     # Evolution API QR connect
│   │   ├── templates.py     # Template store: objectives, verticals, search, generate
│   │   └── costs.py         # Pricing config (admin)
│   ├── generator/
│   │   ├── system_prompt.py # AI prompt generator
│   │   └── builder_flow.py  # Flow builder generator
│   └── services/
│       ├── client_service.py    # Lógica de negocio clientes
│       ├── document_service.py  # Lógica de negocio documentos
│       ├── outbound_service.py  # Motor de llamadas salientes
│       ├── phone_service.py     # Twilio: search/purchase numbers
│       ├── chat_store.py        # In-memory store de conversaciones chat
│       └── chat_service.py      # Chat tester: Gemini multi-turn + tool simulation
│
├── db/                      # === DATABASE ===
│   ├── schema.sql           # Schema base (clients, calls, documents, usage_daily)
│   ├── seed.sql             # Datos de prueba
│   └── migrations/
│       ├── 002_users_table.sql
│       ├── 003_rls_policies.sql
│       ├── 004_phase3_tables.sql      # contacts, appointments
│       ├── 005_outbound_tables.sql    # campaigns, campaign_calls
│       ├── 006_byok_columns.sql       # stt/llm/tts provider + api_key per agent
│       ├── 007_campaign_analysis.sql  # AI analysis fields on campaign_calls
│       ├── 008_conversational_quality.sql  # contact dedup, timeline
│       ├── 009_agents_table.sql       # Multi-agent: agents table
│       ├── 010_flow_builder.sql       # Flow builder JSON + agent mode
│       ├── 011_mcp_servers.sql        # MCP server configs
│       ├── 012_api_integrations.sql   # External API integrations
│       ├── 013_memory_tables.sql      # Long-term memory (contact_memories)
│       ├── 014_orchestration.sql      # Multi-agent orchestration fields
│       ├── 015_billing.sql            # credit_balances, credit_transactions, credit_packages
│       ├── 016_whatsapp_configs.sql   # WhatsApp per-agent config
│       ├── 017_whatsapp_messages.sql  # WhatsApp message log
│       └── 018_template_store.sql     # Frameworks, verticals, objectives, templates
│
├── config/                  # === CONFIGURACIÓN ===
│   ├── voices.json          # Catálogo de voces por provider
│   └── prompts/             # Templates de system prompts por industria
│
├── dashboard/               # === FRONTEND — servido por FastAPI ===
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── App.jsx          # Router principal
│   │   ├── lib/api.js       # HTTP client con auth
│   │   ├── pages/
│   │   │   ├── Login.jsx, ForgotPassword.jsx
│   │   │   ├── Dashboard.jsx         # Overview con stats + gráficas
│   │   │   ├── Calls.jsx             # Lista de llamadas
│   │   │   ├── CallDetail.jsx        # Detalle + transcripción
│   │   │   ├── Documents.jsx         # Gestión de knowledge base
│   │   │   ├── Settings.jsx          # Config unificada (5 tabs: General, Voz, Llamadas, WhatsApp, Avanzado)
│   │   │   ├── AgentWizard.jsx       # Wizard 6 pasos para crear agentes desde templates
│   │   │   ├── Contacts.jsx          # CRM contactos
│   │   │   ├── ContactDetail.jsx     # Detalle contacto + timeline
│   │   │   ├── Appointments.jsx      # Citas agendadas
│   │   │   ├── Campaigns.jsx         # Campañas outbound
│   │   │   ├── CampaignDetail.jsx    # Detalle campaña + análisis AI
│   │   │   ├── Integrations.jsx      # Google Calendar, WhatsApp, tools
│   │   │   ├── McpServers.jsx        # MCP server management
│   │   │   ├── ApiIntegrations.jsx   # External API integrations
│   │   │   ├── FlowBuilder.jsx       # Visual flow builder (React Flow)
│   │   │   ├── WhatsAppInbox.jsx     # WhatsApp inbox/conversations
│   │   │   ├── Billing.jsx           # Credits, packages, transactions
│   │   │   └── admin/                # Solo admin: ClientsList, ClientDetail, ClientCreate, PricingConfig
│   │   └── components/
│   │       ├── Sidebar.jsx           # Nav lateral colapsable (6 grupos)
│   │       ├── Breadcrumbs.jsx       # Breadcrumbs automáticos por ruta
│   │       ├── CommandPalette.jsx    # Ctrl+K búsqueda global
│   │       ├── FilterBar.jsx         # Filtros chip + date range + SortableHeader
│   │       ├── OnboardingChecklist.jsx # Checklist 4 pasos
│   │       ├── EmptyState.jsx        # Estado vacío reutilizable
│   │       ├── ChatTester.jsx        # Modal para probar agentes via texto
│   │       ├── PromptAssistant.jsx   # Asistente AI para generar prompts
│   │       ├── TranscriptViewer.jsx  # Visualizador de transcripciones
│   │       ├── CallsTable.jsx        # Tabla reutilizable de llamadas
│   │       ├── ContactTimeline.jsx   # Timeline de interacciones
│   │       ├── WhatsAppConfig.jsx    # Config WhatsApp per-agent
│   │       ├── StatsCard.jsx, UsageChart.jsx, ClientSelector.jsx, AdminRoute.jsx
│   │       ├── flow/                 # Flow builder nodes + panels
│   │       └── ui/                   # Componentes base (Button, Input, Modal, Badge, etc.)
│   └── dist/                # Build de producción
│
├── .github/workflows/
│   └── ci.yml               # CI: lint (black, isort, flake8, mypy) + tests + dashboard build
│
└── tests/                   # === TESTS (199 tests, 46%+ coverage) ===
    ├── test_agent_factory.py
    ├── test_config_loader.py
    ├── test_file_search.py
    ├── test_admin_scripts.py
    ├── test_session_handler.py
    ├── test_billing.py
    ├── test_logging_config.py
    ├── test_api_agents.py
    ├── test_api_contacts.py
    ├── test_api_appointments.py
    ├── test_api_campaigns.py
    ├── test_api_voices.py
    └── ... (more test files)
```

---

## Database Schema (Supabase PostgreSQL)

```sql
-- ============================================
-- SCHEMA: Voice AI Platform
-- ============================================

-- Extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TABLA: clients
-- Un registro por cada cliente/negocio
-- ============================================
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Identidad del negocio
    name TEXT NOT NULL,                          -- "Consultorio Dr. García"
    slug TEXT UNIQUE NOT NULL,                   -- "dr-garcia" (para URLs y stores)
    business_type TEXT DEFAULT 'generic',        -- dental, gym, restaurant, realestate, generic
    
    -- Configuración del agente de voz
    agent_name TEXT NOT NULL,                    -- "María" (nombre del agente)
    language TEXT DEFAULT 'es',                  -- es, en, es-en (bilingual)
    voice_id TEXT NOT NULL,                      -- ID de voz Cartesia
    greeting TEXT NOT NULL,                      -- "Hola, consultorio del Dr. García, ¿en qué puedo ayudarle?"
    system_prompt TEXT NOT NULL,                 -- Instrucciones completas del agente
    
    -- Gemini File Search
    file_search_store_id TEXT,                   -- ID del FileSearchStore en Gemini
    file_search_store_name TEXT,                 -- Nombre legible del store
    
    -- Telefonía Twilio
    phone_number TEXT,                           -- "+5219991234567" número asignado
    twilio_phone_sid TEXT,                       -- SID del número en Twilio
    sip_trunk_id TEXT,                           -- ID del SIP trunk en LiveKit
    
    -- Configuración avanzada
    max_call_duration_seconds INT DEFAULT 300,   -- 5 min max por default
    tools_enabled TEXT[] DEFAULT '{"search_knowledge"}', -- Tools habilitados
    transfer_number TEXT,                        -- Número para transferir a humano
    business_hours JSONB,                        -- {"mon": {"open": "09:00", "close": "18:00"}, ...}
    after_hours_message TEXT,                    -- Mensaje fuera de horario
    
    -- Metadata
    is_active BOOLEAN DEFAULT true,
    owner_email TEXT,                            -- Email del dueño del negocio
    monthly_minutes_limit INT DEFAULT 500,       -- Límite mensual de minutos
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TABLA: calls
-- Log de cada llamada procesada
-- ============================================
CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    
    -- Info de la llamada
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    caller_number TEXT,                          -- Quién llamó
    callee_number TEXT,                          -- A quién se llamó (outbound)
    
    -- LiveKit
    livekit_room_id TEXT,                        -- Room ID de LiveKit
    livekit_room_name TEXT,                      -- Room name
    
    -- Duración y costos
    duration_seconds INT DEFAULT 0,
    cost_livekit DECIMAL(10,6) DEFAULT 0,
    cost_stt DECIMAL(10,6) DEFAULT 0,
    cost_llm DECIMAL(10,6) DEFAULT 0,
    cost_tts DECIMAL(10,6) DEFAULT 0,
    cost_telephony DECIMAL(10,6) DEFAULT 0,
    cost_total DECIMAL(10,6) DEFAULT 0,
    
    -- Resultado
    status TEXT DEFAULT 'completed' CHECK (status IN ('completed', 'failed', 'transferred', 'no_answer', 'busy')),
    summary TEXT,                                -- Resumen generado por IA de la conversación
    transcript JSONB,                            -- Transcripción completa [{role, text, timestamp}]
    
    -- Metadata
    metadata JSONB DEFAULT '{}',                 -- Info extra (appointement_scheduled, lead_qualified, etc.)
    
    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TABLA: documents
-- Documentos subidos al File Search de cada cliente
-- ============================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    
    filename TEXT NOT NULL,                      -- "menu.pdf", "servicios.txt"
    file_type TEXT,                              -- pdf, txt, md, csv
    file_size_bytes INT,
    
    -- Gemini File Search
    gemini_file_id TEXT,                         -- ID del archivo en Gemini
    gemini_file_uri TEXT,                        -- URI del archivo
    indexing_status TEXT DEFAULT 'pending',      -- pending, indexed, failed
    
    -- Metadata
    description TEXT,                            -- Descripción del contenido
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TABLA: usage_daily
-- Tracking diario de uso por cliente (para billing)
-- ============================================
CREATE TABLE usage_daily (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    
    date DATE NOT NULL,
    total_calls INT DEFAULT 0,
    total_minutes DECIMAL(10,2) DEFAULT 0,
    total_cost DECIMAL(10,4) DEFAULT 0,
    
    inbound_calls INT DEFAULT 0,
    outbound_calls INT DEFAULT 0,
    
    UNIQUE(client_id, date)
);

-- ============================================
-- TABLA: agents (migration 009)
-- Múltiples agentes por cliente
-- ============================================
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    agent_type TEXT DEFAULT 'inbound',         -- inbound, outbound, both
    phone_number TEXT,
    phone_sid TEXT,
    livekit_sip_trunk_id TEXT,
    system_prompt TEXT NOT NULL,
    greeting TEXT NOT NULL,
    examples TEXT,                              -- Ejemplos de conversación
    voice_id TEXT DEFAULT 'default',
    transfer_number TEXT,
    -- BYOK pipeline config
    agent_mode TEXT DEFAULT 'pipeline',         -- pipeline, realtime
    stt_provider TEXT DEFAULT 'deepgram',
    llm_provider TEXT DEFAULT 'google',
    tts_provider TEXT DEFAULT 'cartesia',
    stt_api_key TEXT, llm_api_key TEXT, tts_api_key TEXT,
    realtime_model TEXT DEFAULT 'gpt-4o-realtime-preview',
    realtime_voice TEXT DEFAULT 'alloy',
    realtime_api_key TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, slug)
);

-- ============================================
-- TABLA: contacts (migration 004)
-- ============================================
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    name TEXT,
    email TEXT,
    notes TEXT,
    call_count INT DEFAULT 0,
    last_call_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, phone)
);

-- ============================================
-- TABLA: appointments (migration 004)
-- ============================================
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    contact_phone TEXT,
    patient_name TEXT NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    duration_minutes INT DEFAULT 60,
    description TEXT,
    status TEXT DEFAULT 'scheduled',
    google_event_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TABLA: campaigns (migration 005)
-- ============================================
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id),
    name TEXT NOT NULL,
    script TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    phone_numbers JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TABLA: campaign_calls (migration 005)
-- ============================================
CREATE TABLE campaign_calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    call_id UUID REFERENCES calls(id),
    phone_number TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    -- AI analysis fields (migration 007)
    analysis_sentiment TEXT,
    analysis_outcome TEXT,
    analysis_summary TEXT,
    analysis_interest_level INT,
    analysis_next_steps TEXT,
    analysis_full JSONB,
    analyzed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================
CREATE INDEX idx_clients_phone ON clients(phone_number);
CREATE INDEX idx_clients_slug ON clients(slug);
CREATE INDEX idx_clients_active ON clients(is_active);
CREATE INDEX idx_calls_client ON calls(client_id);
CREATE INDEX idx_calls_started ON calls(started_at);
CREATE INDEX idx_calls_client_date ON calls(client_id, started_at);
CREATE INDEX idx_documents_client ON documents(client_id);
CREATE INDEX idx_usage_client_date ON usage_daily(client_id, date);
CREATE INDEX idx_agents_client ON agents(client_id);
CREATE INDEX idx_contacts_client ON contacts(client_id);
CREATE INDEX idx_contacts_phone ON contacts(client_id, phone);
CREATE INDEX idx_appointments_client ON appointments(client_id);
CREATE INDEX idx_campaigns_client ON campaigns(client_id);
CREATE INDEX idx_campaign_calls_campaign ON campaign_calls(campaign_id);

-- ============================================
-- RLS (Row Level Security) — para Fase 2
-- ============================================
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_daily ENABLE ROW LEVEL SECURITY;

-- ============================================
-- FUNCTIONS
-- ============================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Función para obtener config de cliente por número de teléfono
CREATE OR REPLACE FUNCTION get_client_by_phone(phone TEXT)
RETURNS TABLE (
    id UUID,
    name TEXT,
    slug TEXT,
    agent_name TEXT,
    language TEXT,
    voice_id TEXT,
    greeting TEXT,
    system_prompt TEXT,
    file_search_store_id TEXT,
    tools_enabled TEXT[],
    max_call_duration_seconds INT,
    transfer_number TEXT,
    business_hours JSONB,
    after_hours_message TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id, c.name, c.slug, c.agent_name, c.language,
        c.voice_id, c.greeting, c.system_prompt,
        c.file_search_store_id, c.tools_enabled,
        c.max_call_duration_seconds, c.transfer_number,
        c.business_hours, c.after_hours_message
    FROM clients c
    WHERE c.phone_number = phone AND c.is_active = true;
END;
$$ LANGUAGE plpgsql;
```

---

## Variables de Entorno (.env)

```bash
# === LiveKit Cloud ===
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

# === Google Gemini ===
GOOGLE_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxx

# === Deepgram ===
DEEPGRAM_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx

# === Cartesia ===
CARTESIA_API_KEY=sk-cart-xxxxxxxxxxxxxxxx

# === ElevenLabs (opcional, BYOK) ===
ELEVENLABS_API_KEY=sk_xxxxxxxxxxxxxxxx

# === Twilio ===
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx

# === Supabase ===
SUPABASE_URL=https://xxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJxxxxxxxxxxxxxxxx
SUPABASE_ANON_KEY=eyJxxxxxxxxxxxxxxxx

# === Stripe (billing) ===
STRIPE_SECRET_KEY=sk_xxxxxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxx

# === MercadoPago (billing) ===
MERCADOPAGO_ACCESS_TOKEN=APP_USR-xxxxxxxx
MERCADOPAGO_WEBHOOK_SECRET=xxxxxxxxxxxxxxxx

# === App Config ===
APP_ENV=development
LOG_FORMAT=json          # json para producción, omitir para texto
DEFAULT_LANGUAGE=es
DEFAULT_MAX_CALL_DURATION=300

# === CORS (producción) ===
ALLOWED_ORIGINS=https://your-domain.railway.app
CF_PAGES_DOMAIN=voiceai-69f.pages.dev
```

---

## Flujo de una Llamada Entrante

```
┌──────────────────────────────────────────────────────────────────────┐
│  FLUJO: Llamada Entrante                                             │
│                                                                      │
│  1. Cliente marca +52 999 111 2233                                   │
│     │                                                                │
│  2. Twilio recibe → SIP INVITE → LiveKit SIP Server                 │
│     │                                                                │
│  3. LiveKit crea Room "call-{uuid}" → Dispatch a Agent Worker       │
│     │                                                                │
│  4. agent/main.py recibe el evento:                                  │
│     │  - Extrae caller_number y called_number del SIP headers       │
│     │  - Busca en DB: get_client_by_phone(called_number)            │
│     │  - Obtiene: voice_id, greeting, system_prompt, store_id       │
│     │                                                                │
│  5. agent_factory.py construye el agente dinámicamente:             │
│     │  - STT: Deepgram Nova-3 (language del cliente)                │
│     │  - LLM: Gemini 3 Flash (system_prompt del cliente)            │
│     │  - TTS: Cartesia Sonic 3 (voice_id del cliente)               │
│     │  - Tools: file_search con store_id del cliente                │
│     │                                                                │
│  6. Agente saluda con greeting del cliente                          │
│     │                                                                │
│  7. Conversación fluye:                                              │
│     │  Usuario habla → Deepgram STT → texto                        │
│     │  → Gemini procesa (+ File Search si necesita)                 │
│     │  → respuesta texto → Cartesia TTS → audio                    │
│     │  + Filler phrases si LLM tarda >1.2s ("Déjeme ver...")       │
│     │  + Backchannels cada ~5.5s si usuario habla largo ("Ajá")    │
│     │                                                                │
│  8. Llamada termina:                                                 │
│     │  - Genera summary con Gemini                                  │
│     │  - Calcula costos (duration × rates)                          │
│     │  - Guarda call log en DB                                      │
│     │  - Actualiza usage_daily                                      │
│     │                                                                │
│  9. Room se destruye automáticamente                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Concurrencia

NO hay límite práctico. Cada llamada crea un Room separado con su propia instancia del agente. 10 personas pueden llamar al mismo número simultáneamente. No hay cola de espera, no hay "ocupado". Todas las instancias comparten: mismo FileSearchStore, mismo prompt, misma voz. Solo pagas más minutos.

Dispatch Rule:
```json
{
    "rule": {
        "dispatchRuleIndividual": {
            "roomPrefix": "call-"
        }
    }
}
```

---

## Configuración del Agente LiveKit

### livekit.toml
```toml
[agent]
name = "voice-ai-platform"
version = "0.1.0"

[sip]
# SIP trunks se configuran via API o dashboard de LiveKit
```

### Dependencias principales (requirements.txt)
```
# LiveKit
livekit==1.x
livekit-agents==1.x
livekit-plugins-deepgram==1.x
livekit-plugins-cartesia==1.x
livekit-plugins-google==1.x

# Google Gemini
google-genai>=1.0

# Database
supabase>=2.0
asyncpg>=0.29

# Admin API
fastapi>=0.115
uvicorn>=0.32

# Twilio
twilio>=9.0

# Utilities
python-dotenv>=1.0
typer>=0.12
rich>=13.0
pydantic>=2.0
```

---

## Gemini File Search — Integración

Cada cliente tiene su propio FileSearchStore en Gemini. Cuando un usuario pregunta algo, el agente busca automáticamente en el store de ese cliente.

### Crear Store + Subir Documentos
```python
from google import genai

client = genai.Client(api_key=GOOGLE_API_KEY)

# 1. Crear store para un cliente
store = client.vector_stores.create(
    name=f"store-{client_slug}",  # "store-dr-garcia"
    config={"embedding_model": "models/text-embedding-005"}
)

# 2. Subir archivo
with open("menu.pdf", "rb") as f:
    uploaded = client.files.upload(file=f)

# 3. Agregar al store
client.vector_stores.files.create(
    vector_store_id=store.id,
    file_id=uploaded.id
)

# 4. Usar en conversación como tool
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="¿Cuáles son los servicios disponibles?",
    config={
        "tools": [{
            "file_search": {
                "vector_store_ids": [store.id]
            }
        }],
        "system_instruction": system_prompt
    }
)
```

### File Search como Tool en LiveKit Agent
```python
# El agente usa Gemini con File Search integrado
# NO es un tool separado — es nativo de Gemini
# Se pasa el vector_store_id del cliente en cada request
```

---

## Twilio → LiveKit SIP Setup

### 1. Crear SIP Trunk en LiveKit
```python
from livekit.api import LiveKitAPI

lk = LiveKitAPI(
    url=LIVEKIT_URL,
    api_key=LIVEKIT_API_KEY, 
    api_secret=LIVEKIT_API_SECRET
)

# Crear trunk
trunk = await lk.sip.create_sip_trunk({
    "name": "twilio-inbound",
    "numbers": ["+5219991112233"],
    "inbound": {
        "allowed_addresses": ["54.172.60.0/23"],  # Twilio IPs
    }
})

# Crear dispatch rule
rule = await lk.sip.create_sip_dispatch_rule({
    "name": "route-to-agent",
    "rule": {
        "dispatchRuleIndividual": {
            "roomPrefix": "call-"
        }
    },
    "trunk_ids": [trunk.sip_trunk_id]
})
```

### 2. Configurar Twilio
En Twilio Console:
- Elastic SIP Trunking → Create Trunk
- Origination URI: `sip:{your-project}.livekit.cloud`
- Asignar número telefónico al trunk

---

## Fases de Desarrollo

### FASE 1 — El Motor (estimado: 4-8 horas con Claude Code)

**Objetivo**: Un agente funcional que recibe llamadas, se adapta por cliente, usa knowledge base, y loguea todo.

**Entregables**:
1. ✅ Schema de DB ejecutado en Supabase
2. ✅ `admin/create_client.py` — crea cliente + FileSearchStore  
3. ✅ `admin/upload_docs.py` — sube docs al store
4. ✅ `admin/assign_phone.py` — asigna número Twilio + SIP
5. ✅ `agent/main.py` — agente LiveKit con carga dinámica
6. ✅ `agent/agent_factory.py` — construye agente por config
7. ✅ `agent/tools/file_search.py` — File Search por cliente
8. ✅ `agent/session_handler.py` — log de llamadas + costos
9. ✅ Tests básicos
10. ✅ Deploy: agente con `lk deploy`, API con `railway up`

**Criterio de éxito**: Puedo llamar al +52 999 XXX, me contesta "María" del Dr. García, le pregunto horarios, busca en su PDF, y me responde. La llamada queda logueada con costos.

### FASE 2 — Dashboard Web (estimado: 8-16 horas)

**Objetivo**: Panel web donde cada cliente puede ver sus llamadas, subir docs, y configurar su agente.

**Entregables**:
1. Dashboard React con autenticación Supabase
2. Página de overview: llamadas hoy, minutos usados, costo
3. Historial de llamadas con transcripciones
4. Upload de documentos a File Search
5. Configuración de prompts, voz, greeting
6. Panel admin para Sergio (ver todos los clientes)

**Diseño**: SaaS moderno, dark theme, tech aesthetic. Ver sección de diseño abajo.
**Deploy**: React build servido por FastAPI en Railway (mismo servicio que la API).

### FASE 3 — Multi-tenant Completo ✅

**Objetivo**: Plataforma SaaS funcional con herramientas de negocio.

**Entregables**:
1. ✅ Tool calling: calendar, whatsapp, CRM (contacts, appointments)
2. ✅ CRM dashboard: Contacts, ContactDetail, Appointments pages
3. ✅ Outbound engine: campaigns, campaign_calls, outbound_service
4. ✅ Integrations page: Google Calendar, WhatsApp, tool toggles
5. ✅ BYOK voice pipeline: STT/LLM/TTS provider + API key por agente
6. ✅ Call analyzer AI: Gemini post-call analysis para campañas
7. ✅ Multi-agent: agents table, CRUD, cada cliente múltiples agentes
8. ✅ Phone management: search/purchase Twilio numbers desde dashboard

### Mejoras Post-Fase 3 ✅

**Chat Tester** — Probar agentes de voz via texto sin gastar en audio/telefonía:
- Mismo pipeline (prompt, knowledge base, tools) pero en texto
- Tools simulados (excepto search_knowledge que es real/read-only)
- Soporte outbound con campaign_script
- Integrado en AgentDetail, CampaignDetail, Settings

**Voice Quality** — Mejoras de calidad de voz humana:
- Filler phrases: "Déjeme ver..." cuando LLM tarda >1.2s
- Backchanneling: "Ajá", "Mjm" mientras usuario habla largo
- VAD + turn detection optimizados
- Deepgram: filler_words, smart_format, punctuate, no_delay
- Voice rules: precios naturales, fechas conversacionales, tono empático

**AI Prompt Generation** — Asistente para crear/mejorar prompts:
- Genera prompts por industria y configuración del negocio
- Mejora prompts existentes con sugerencias

### FASE 4 — MCP Integration ✅

1. ✅ MCP builder (MCPServerHTTP, MCPServerStdio) desde config DB
2. ✅ MCP server CRUD API + templates (Brave Search, etc.)
3. ✅ LiveKit native `Agent(mcp_servers=[])` integration
4. ✅ MCP tools en chat tester y WhatsApp (no solo voz)

### FASE 5 — Billing ✅

1. ✅ Modelo 1 crédito = 1 minuto, billing incremental >5min
2. ✅ `agent/billing.py` — CallBilling class (check, start, finish)
3. ✅ Credit packages, transactions, balance API
4. ✅ Stripe webhook con verificación de firma
5. ✅ MercadoPago webhook (preparado, pendiente SDK)
6. ✅ Gift credits (admin), pricing config

### FASE 6 — Flow Builder + API Integrations ✅

1. ✅ Visual flow builder (React Flow) con 8 tipos de nodos
2. ✅ Flow engine runtime en el agente de voz
3. ✅ API integrations CRUD y ejecución en tools

### FASE 7 — UX/UI Overhaul ✅

1. ✅ Sidebar colapsable con 6 grupos
2. ✅ Breadcrumbs automáticos, CommandPalette (Ctrl+K)
3. ✅ FilterBar, SortableHeader, EmptyState, OnboardingChecklist
4. ✅ Settings unificado (5 tabs: General, Voz, Llamadas, WhatsApp, Avanzado)
5. ✅ Agent selector pills + multi-agent orchestration UI

### FASE 8 — Template Store + Agent Wizard ✅

1. ✅ Qualification frameworks (BANT, CHAMP, SPIN, Simple)
2. ✅ Industry verticals (7) + objectives (7) + templates
3. ✅ Dual generator: system_prompt + builder_flow
4. ✅ Agent wizard 6 pasos

### FASE 9 — Hardening ✅

1. ✅ Security: rate limiting, input validation, CORS hardening, webhook signatures
2. ✅ Robustness: DB singleton, timeouts on all external calls, error recovery
3. ✅ Tests: 199 tests, 46%+ coverage, CI pipeline (lint + test + build)
4. ✅ Observability: structured logging, correlation IDs, X-Request-ID
5. ✅ Frontend: toast error handling, cancelled pattern, Modal accessibility
6. ✅ Dockerfiles unified to Python 3.13, API versioning header

### Pendiente

1. Probar WhatsApp en vivo (webhook Railway → Evolution API)
2. Analytics de llamadas — dashboard de métricas
3. Web widget embeddable para sitios web de clientes
4. Sentry integration (error tracking en producción)
5. Onboarding self-service para nuevos clientes

---

## Estrategia de Agentes para Claude Code CLI

### CLAUDE.md (instrucciones para Claude Code)

```markdown
# Voice AI Platform — Instrucciones para Claude Code

## Contexto
Estás construyendo una plataforma multi-tenant de agentes de voz con IA.
Lee ARCHITECTURE.md para el diseño completo.

## Stack
- Python 3.12+, LiveKit Agents SDK, Gemini 3 Flash, Deepgram Nova-3, Cartesia Sonic 3
- Supabase (PostgreSQL), FastAPI, Twilio SIP
- React + Tailwind (dashboard, Fase 2)

## Reglas de código
- Tipado estricto con type hints en todo Python
- Async/await para todo I/O
- Pydantic models para validación
- Manejo de errores robusto con logging estructurado
- Docstrings en español
- Variables y código en inglés, comentarios en español
- Tests con pytest para cada módulo

## Estructura
Sigue exactamente la estructura definida en ARCHITECTURE.md.

## Prioridad
Fase 1 primero. No construir dashboard hasta que el motor funcione end-to-end.
```

### Estrategia Multi-Agente (recomendada)

Para Fase 1, **un solo agente de Claude Code es suficiente**. El proyecto no es tan grande como para necesitar Agent Teams. Usa:

```bash
# Modo recomendado: interactivo con auto-accept
claude --dangerously-skip-permissions

# Darle el contexto
> Lee ARCHITECTURE.md y empecemos con la Fase 1.
> Primero ejecuta el schema.sql en Supabase, luego construye 
> create_client.py y upload_docs.py. Test cada módulo.
```

Para Fase 2 (Dashboard), ahí SÍ considera Agent Teams o sesiones paralelas:
- **Sesión 1**: Backend API (FastAPI routes)
- **Sesión 2**: Frontend Dashboard (React)
- Ambas comparten el mismo repo con git worktrees

---

## Diseño del Dashboard (Fase 2)

### Dirección Estética: "Command Center" / Dark Tech SaaS

**Concepto**: Un dashboard que se siente como un centro de control de misión. Dark theme dominante, acentos de color vibrantes (cyan/electric blue), datos en tiempo real, visualizaciones de llamadas activas.

**Referencias de diseño**:
- Vercel Dashboard (minimalismo dark)
- Linear App (clean, funcional, tech)  
- Retell.ai Dashboard (competidor directo — superarlo)
- Datadog (data-dense pero legible)

**Principios**:
- Dark background (#0a0a0f o similar), NO pure black
- Accent color: Electric cyan (#00f0ff) o Neon green (#00ff88)
- Font: JetBrains Mono para datos, Geist/Satoshi para UI
- Cards con glassmorphism sutil (backdrop-blur)
- Animaciones de entrada suaves (framer-motion)
- Gráficas con Recharts, estilo "terminal"
- Llamadas activas con indicador pulsante en tiempo real
- Sidebar minimal con iconos (lucide-react)

**Skill recomendado para Claude Code**:
Crear un archivo `.claude/skills/dashboard-design/SKILL.md` con las instrucciones de diseño del frontend-design skill de Anthropic más estas especificaciones del proyecto.

---

## Catálogo de Voces Cartesia (config/voices.json)

```json
{
    "voices": {
        "es_female_warm": {
            "id": "PENDING_CARTESIA_VOICE_ID",
            "name": "María",
            "language": "es",
            "gender": "female",
            "description": "Voz femenina cálida, profesional, mexicana"
        },
        "es_male_professional": {
            "id": "PENDING_CARTESIA_VOICE_ID", 
            "name": "Carlos",
            "language": "es",
            "gender": "male",
            "description": "Voz masculina profesional, seria"
        },
        "en_female_friendly": {
            "id": "PENDING_CARTESIA_VOICE_ID",
            "name": "Katie",
            "language": "en",
            "gender": "female",
            "description": "English friendly female voice"
        },
        "bilingual_female": {
            "id": "PENDING_CARTESIA_VOICE_ID",
            "name": "Sofia",
            "language": "es-en",
            "gender": "female",
            "description": "Bilingual Spanish/English, natural switching"
        }
    },
    "note": "Actualizar IDs después de explorar el catálogo de Cartesia Sonic 3"
}
```

---

## Checklist Pre-Desarrollo

### Cuentas y API Keys
- [x] LiveKit Cloud — cuenta creada, plan Build activado
- [x] Google AI Studio — API key para Gemini 3 Flash
- [x] Deepgram — cuenta con créditos
- [x] Cartesia — cuenta con créditos
- [x] Twilio — cuenta creada
- [x] Supabase — proyecto: `voice-ai-platform`
- [x] Railway — cuenta activa

### Herramientas
- [ ] Claude Code CLI instalado y autenticado
- [ ] Python 3.12+ instalado
- [ ] Node.js 20+ (para dashboard en Fase 2)
- [ ] Git configurado
- [ ] Editor (VS Code recomendado con extensión Claude Code)

### Validaciones iniciales
- [ ] Confirmar que Gemini 3 Flash soporta File Search (API de Google GenAI)
- [ ] Confirmar versión actual de LiveKit Agents SDK para Python
- [ ] Explorar catálogo de voces Cartesia Sonic 3 y elegir IDs
- [ ] Probar que Twilio puede enviar SIP a LiveKit Cloud
- [ ] Verificar precios actuales de cada servicio

---

## Comandos Útiles

```bash
# Crear entorno virtual
python -m venv venv && source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Correr agente local
python -m livekit.agents dev agent/main.py

# Deploy agente a LiveKit Cloud
lk deploy

# Correr API + Dashboard local
uvicorn api.main:app --reload --port 8000

# Build del dashboard
cd dashboard && npm run build && cd ..

# Deploy a Railway (desde root del proyecto)
railway up

# Correr tests
pytest tests/ -v

# Admin scripts
python admin/create_client.py --name "Dr. García" --slug "dr-garcia" --voice es_female_warm
python admin/upload_docs.py --client dr-garcia --file ./docs/servicios.pdf
python admin/assign_phone.py --client dr-garcia --number "+5219991112233"
python admin/test_call.py --client dr-garcia
```

---

## Notas Importantes

1. **Gemini File Search** es relativamente nuevo. Verificar la API actual antes de implementar. La documentación oficial es: https://ai.google.dev/gemini-api/docs/file-search
2. **LiveKit Agents SDK** evoluciona rápido. Verificar versión actual y breaking changes.
3. **Cartesia Sonic 3** snapshot actual: `sonic-3-2026-01-12`. Verificar en docs de Cartesia.
4. **Twilio SIP → LiveKit** requiere configurar IPs de Twilio en el trunk. Consultar docs de LiveKit SIP.
5. **Concurrencia**: Plan Build de LiveKit tiene quotas para desarrollo. Monitorear si se necesita Scale.