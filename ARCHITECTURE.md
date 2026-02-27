# Voice AI Platform — Arquitectura Completa
## Plataforma Multi-Tenant de Agentes de Voz con IA

**Proyecto**: voice-ai-platform  
**Owner**: Sergio / Innotecnia  
**Fecha**: Febrero 2026  
**Mercado objetivo**: México / LATAM  
**Visión**: Construir un VAPI/Retell propio — plataforma SaaS donde cada cliente obtiene su agente de voz personalizado con número telefónico, knowledge base, y dashboard.

---

## Stack Definitivo

| Componente | Tecnología | Modelo/Versión |
|---|---|---|
| **Orquestación** | LiveKit Cloud (Plan Build) | Agents Framework (Python) |
| **STT** | Deepgram | Nova-3 + Flux (turn detection semántico) |
| **LLM** | Google Gemini | gemini-3-flash-preview |
| **RAG** | Gemini File Search | Storage gratis, indexing $0.15/1M tokens |
| **TTS** | Cartesia | Sonic 3 (snapshot: sonic-3-2026-01-12) |
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
├── Dockerfile               # Para deploy
├── livekit.toml             # Config LiveKit agent
│
├── agent/                   # === CORE: LiveKit Voice Agent ===
│   ├── main.py              # Entrypoint LiveKit agent worker
│   ├── agent_factory.py     # Crea agentes dinámicos por cliente
│   ├── session_handler.py   # Maneja lifecycle de cada llamada
│   ├── config_loader.py     # Carga config de cliente desde DB
│   └── tools/               # Herramientas que el agente puede usar
│       ├── __init__.py
│       ├── file_search.py   # Gemini File Search por cliente
│       ├── calendar.py      # Agendar citas (futuro)
│       ├── transfer.py      # Transferir a humano (futuro)
│       └── notify.py        # Enviar SMS/email (futuro)
│
├── admin/                   # === ADMIN: Scripts de gestión ===
│   ├── cli.py               # CLI principal con typer/click
│   ├── create_client.py     # Crear cliente + FileSearchStore
│   ├── upload_docs.py       # Subir docs al store del cliente
│   ├── assign_phone.py      # Asignar número Twilio + SIP trunk
│   ├── list_clients.py      # Listar clientes activos
│   ├── outbound.py          # Disparar llamadas salientes
│   └── test_call.py         # Test rápido de un agente
│
├── api/                     # === API: FastAPI endpoints ===
│   ├── main.py              # FastAPI app
│   ├── routes/
│   │   ├── clients.py       # CRUD clientes
│   │   ├── calls.py         # Historial de llamadas
│   │   ├── documents.py     # Upload/manage docs
│   │   └── webhooks.py      # Twilio/LiveKit webhooks
│   └── middleware/
│       └── auth.py          # Supabase JWT auth
│
├── db/                      # === DATABASE ===
│   ├── schema.sql           # Schema completo Supabase
│   ├── seed.sql             # Datos de prueba
│   └── migrations/
│
├── config/                  # === CONFIGURACIÓN ===
│   ├── voices.json          # Catálogo de voces Cartesia disponibles
│   └── prompts/             # Templates de system prompts
│       ├── dental.md        # Prompt para dentistas
│       ├── gym.md           # Prompt para gimnasios
│       ├── restaurant.md    # Prompt para restaurantes
│       └── generic.md       # Prompt genérico
│
├── dashboard/               # === FRONTEND (Fase 2) — servido por FastAPI ===
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   ├── components/
│   │   └── hooks/
│   ├── public/
│   └── dist/                # Build de producción, servido por FastAPI como static
│
└── tests/                   # === TESTS ===
    ├── test_agent_factory.py
    ├── test_config_loader.py
    ├── test_file_search.py
    └── test_admin_scripts.py
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

# === Twilio ===
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx

# === Supabase ===
SUPABASE_URL=https://xxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJxxxxxxxxxxxxxxxx
SUPABASE_ANON_KEY=eyJxxxxxxxxxxxxxxxx

# === App Config ===
APP_ENV=development
LOG_LEVEL=DEBUG
DEFAULT_LANGUAGE=es
DEFAULT_MAX_CALL_DURATION=300
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

### FASE 3 — Multi-tenant Completo (estimado: 2-4 días)

**Objetivo**: Producto SaaS funcional con billing.

**Entregables**:
1. Onboarding self-service para nuevos clientes
2. Billing automático (Stripe o similar)
3. Métricas avanzadas y analytics
4. Llamadas outbound (campañas)
5. Estructuras complejas (conmutador IVR)

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