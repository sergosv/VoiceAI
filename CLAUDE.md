# Voice AI Platform — Instrucciones para Claude Code

## Contexto
Estás construyendo una plataforma multi-tenant de agentes de voz con IA para el mercado mexicano/LATAM.
**Lee ARCHITECTURE.md primero** — contiene el diseño completo: stack, schema DB, estructura, flujos, y fases.

## Stack
- **Runtime**: Python 3.12+
- **Agente de voz**: LiveKit Agents SDK (Python)
- **STT**: Deepgram Nova-3 con Flux
- **LLM**: Gemini 3 Flash Preview (`gemini-3-flash-preview`) vía google-genai SDK
- **RAG**: Gemini File Search (vector stores nativos)
- **TTS**: Cartesia Sonic 3 (`sonic-3-2026-01-12`)
- **Telefonía**: Twilio SIP → LiveKit SIP Server
- **Base de datos**: Supabase (PostgreSQL)
- **Hosting Agent**: LiveKit Cloud (`lk deploy`)
- **Hosting API + Dashboard**: Railway (un solo servicio FastAPI que sirve API + React static)
- **Base de datos**: Supabase (proyecto: `voice-ai-platform`)
- **Frontend**: React + Tailwind, build servido por FastAPI como StaticFiles (Fase 2)

## Reglas de Código

### Python
- Type hints estrictos en TODOS los parámetros y retornos
- `async/await` para todo I/O (DB, APIs, archivos)
- Pydantic v2 models para validación de datos y configs
- Logging estructurado con `structlog` o `logging` con formato JSON
- Manejo de errores robusto: try/except específicos, nunca bare except
- Docstrings en español, breves y directos
- Variables, funciones y clases en inglés
- Comentarios explicativos en español solo donde no sea obvio

### Estilo
- Black formatter, isort para imports
- Max line length: 100 chars
- Imports absolutos preferidos sobre relativos
- Un módulo, una responsabilidad

### Tests
- pytest para todo
- Mocks para servicios externos (Gemini, Deepgram, Cartesia, Twilio)
- Fixtures para configs de cliente de prueba
- Test cada módulo antes de avanzar al siguiente

## Estructura del Proyecto
Sigue EXACTAMENTE la estructura definida en ARCHITECTURE.md. No inventar carpetas o archivos extra sin justificación.

## Flujo de Desarrollo

### Fase 1 — El Motor (PRIORIDAD ACTUAL)
Construir en este orden:
1. `db/schema.sql` → Ejecutar en Supabase
2. `agent/config_loader.py` → Cargar config de cliente desde DB
3. `admin/create_client.py` → Crear cliente + FileSearchStore en Gemini
4. `admin/upload_docs.py` → Subir documentos al store
5. `agent/tools/file_search.py` → Integrar Gemini File Search como tool
6. `agent/agent_factory.py` → Crear agente dinámico con STT+LLM+TTS
7. `agent/main.py` → Entrypoint LiveKit con dispatch dinámico
8. `agent/session_handler.py` → Log de llamadas y cálculo de costos
9. `admin/assign_phone.py` → Configurar Twilio SIP + LiveKit trunk
10. Tests para cada módulo

### Fase 2 — Dashboard (DESPUÉS de Fase 1 completa)
No empezar dashboard hasta que una llamada end-to-end funcione.

## Decisiones Técnicas Clave

### Agente Dinámico
UN solo worker de LiveKit que se adapta por llamada:
```python
# NO crear N workers. UN worker que lee config de DB
async def entrypoint(ctx: JobContext):
    called_number = extract_phone_from_sip(ctx)
    client_config = await load_client_config(called_number)
    agent = build_agent(client_config)
    agent.start(ctx.room)
```

### File Search
Cada cliente tiene su propio vector store en Gemini. El store_id se guarda en la tabla clients y se pasa al agente en cada llamada.

### Costos
Calcular costos reales por llamada:
- Duración × rate de cada servicio
- Guardar desglose en tabla calls
- Acumular en usage_daily

## Verificaciones Importantes
Antes de implementar cada integración, verificar la API actual:
- LiveKit Agents SDK: `pip show livekit-agents` — puede haber breaking changes
- Gemini File Search: verificar endpoint actual en docs de google-genai
- Cartesia: verificar modelo y snapshot actual
- Deepgram: verificar que Nova-3 y Flux están disponibles

## Problemas Conocidos del Deploy

### SIP URI incorrecto
El subdomain del proyecto (`innotecnia-2lp4xy8z.sip.livekit.cloud`) **NO** es el SIP URI. El real es el project ID: `2r172cwux9u.sip.livekit.cloud`. Se encuentra en LiveKit Dashboard → Telephony → SIP trunks (esquina superior derecha).

### Supabase API keys
El SDK `supabase-py` **no soporta** el formato nuevo de keys (`sb_publishable_`, `sb_secret_`). Usar las **legacy JWT keys** (`eyJ...`) que están en Settings → API → pestaña "Legacy anon, service_role API keys".

### Twilio SIP transport
Twilio usa UDP por default, LiveKit necesita **TCP**. Usar `transport=tcp` en el Origination URI del Elastic SIP Trunk: `sip:2r172cwux9u.sip.livekit.cloud;transport=tcp`.

### LiveKit deploy — livekit.toml not found
El build remoto de `lk deploy` no incluye `livekit.toml` en el contexto de Docker. **NO** incluir `COPY livekit.toml .` en el Dockerfile. LiveKit lo maneja por separado.

### LiveKit deploy — agent ID requerido
El `livekit.toml` necesita el campo `id` bajo `[agent]` para que `lk agent deploy` funcione. Ejemplo: `id = "CA_cRCs5tbTho5A"`.

### LiveKit deploy — max agents
Plan Build permite solo 1 agente. Usar `lk agent deploy` para actualizar, **no** `lk agent create` para crear otro.

### Twilio trial
Solo permite llamadas a números verificados. Para pruebas, verificar el celular en Console → Verified Caller ID.

## NO hacer
- No sobre-engineerear. Mínimo viable primero.
- No agregar features no pedidos (auth, billing, analytics avanzados = Fase 3)
- No usar ORMs pesados. Raw SQL o supabase-py directo.
- No crear microservicios. Monolito modular.
- No hardcodear configs de clientes. Todo desde DB.
