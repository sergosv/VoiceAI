# Voz IA para Foodie — Guía de Instrucciones y Aprendizajes

> **Propósito.** Destilar todo lo aprendido construyendo la plataforma multi-tenant de
> agentes de voz (VoiceAI / Innotecnia) para **montar el módulo de voz dentro de Foodie**
> (plataforma de restaurantes). No migramos dos plataformas: **tomamos lo más útil del
> motor de voz y lo añadimos a Foodie** para hacer **atención, servicio y campañas de
> llamadas — Inbound y Outbound**.
>
> Este documento es el **camino**: qué tecnologías usar, cómo configurarlas (Twilio,
> LiveKit, Deepgram, Gemini, Cartesia), qué reutilizar tal cual, qué adaptar, los
> problemas que ya resolvimos y las fases de implementación.
>
> Fecha: 2026-06-27 · Fuente: repo `VoiceAI` (Fases 1–31, 104 bugs de auditoría, producción real).

---

## 0. TL;DR — La recomendación en una página

1. **El agente de voz es un worker Python LiveKit independiente.** No vive dentro del API
   de Foodie; corre en **LiveKit Cloud** y se comunica con Foodie por **DB compartida**
   (PostgreSQL) + webhooks. Foodie ya es Python/FastAPI async → el motor encaja casi directo.

2. **Stack ganador (probado en producción):**
   - **Telefonía:** Twilio Elastic SIP Trunk → LiveKit SIP (¡`transport=tcp` obligatorio!).
   - **Voz:** 3 modos. Para Foodie arranca con **`gemini_live`** (Gemini Live audio-to-audio,
     menor latencia, sin API key extra, ~$0.023/min). Ten **`pipeline`** (Deepgram + Gemini +
     Cartesia) como alternativa tuneable.
   - **DB:** Foodie se queda en su **PostgreSQL de Railway** — NO se migra a Supabase ni a
     ningún lado. La única "migración" es de *código de acceso a datos*: VoiceAI lee/escribe
     con `supabase-py` (porque hospedaba su Postgres en Supabase); Foodie lo hará con
     **SQLAlchemy async + asyncpg + Redis** sobre su Postgres de Railway. Se reescribe esa
     capa (ver §3.2), pero la lógica y las estructuras de datos se conservan.

3. **Reutiliza tal cual (lógica agnóstica al transporte):** `agent_factory`, `session_handler`
   (costos), `call_lifecycle`, `hook_engine`, `sentiment`/`intent`, `pipeline_builder`.

4. **El camino:** Telefonía (Inbound 1 número) → Agente mínimo → Inbound real → Costos →
   Outbound + campañas → Hardening. Detalle en §11.

5. **Multi-tenant:** en Foodie, **`restaurante` = `client`/tenant**. Cada restaurante = su
   config de agente, su número, su balance, sus campañas.

---

## 1. Qué construimos (arquitectura en un vistazo)

```
                          ┌─────────────────────────────────────────────┐
   Cliente final          │                 LiveKit Cloud                │
   (teléfono)             │   ┌──────────────────────────────────────┐  │
       │                  │   │   Worker de voz (Python, 1 solo)     │  │
       │  llama           │   │   agent/main.py  → entrypoint(ctx)   │  │
       ▼                  │   │   - dispatch inbound/outbound/widget │  │
   ┌────────┐   SIP/TCP   │   │   - build_agent(config dinámica)     │  │
   │ Twilio │────────────▶│   │   - STT/LLM/TTS según agent_mode     │  │
   │ Elastic│             │   └──────────────────────────────────────┘  │
   │  Trunk │◀────────────│            ▲                  │              │
   └────────┘   outbound  └────────────┼──────────────────┼─────────────┘
                                       │ lee config       │ escribe llamada/costos
                                       ▼                  ▼
                          ┌─────────────────────────────────────────────┐
                          │      PostgreSQL (en Foodie: compartido)      │
                          │  clients/restaurants · agents · calls ·      │
                          │  campaigns · campaign_calls · contacts ·     │
                          │  credit_balances · call_events ...           │
                          └─────────────────────────────────────────────┘
                                       ▲
                                       │ admin / dashboard / disparar campañas
                          ┌─────────────────────────────────────────────┐
                          │   API FastAPI de Foodie  (+ React/shadcn)    │
                          │  routes para: crear agente, asignar número,  │
                          │  lanzar/pausar campañas, ver llamadas, costos│
                          └─────────────────────────────────────────────┘
```

**Decisión de diseño central (la más importante):** **UN solo worker LiveKit** que se
**adapta por llamada** leyendo config de la DB. No N workers por cliente. El número marcado
(o el `agent_id` en metadata) determina qué agente "se materializa".

```python
# agent/main.py — el corazón del dispatch (simplificado)
async def entrypoint(ctx: JobContext):
    called_number = ctx...sip.trunkPhoneNumber      # a qué número llamaron
    caller_number = ctx...sip.phoneNumber           # quién llama
    config = await load_config_by_phone(called_number)   # inbound: busca por DID
    agent  = build_agent(config)                    # agente dinámico
    session = AgentSession(...)                      # arma STT/LLM/TTS según modo
    await session.start(room=ctx.room)
```

---

## 2. El stack ganador (tecnologías y por qué)

| Capa | Tecnología elegida | Por qué / Aprendizaje |
|---|---|---|
| **Runtime agente** | Python 3.11+ (Foodie usa 3.11.6) | LiveKit Agents SDK es Python. Foodie ya es Python async. |
| **Orquestación voz** | **LiveKit Agents SDK** (`livekit-agents 1.5.2 [codecs,mcp]`) | Maneja SIP, rooms, VAD, turn-taking, streaming. Deploy con `lk agent deploy`. |
| **Telefonía** | **Twilio Elastic SIP Trunking** → LiveKit SIP | Estándar, barato (~$0.013/min MX), soporta inbound y outbound. |
| **Voz — modo recomendado** | **Gemini Live** (`gemini-3.1-flash-live-preview`) | Audio-to-audio nativo, menor latencia, **sin API key extra**, ~$0.023/min. |
| **Voz — pipeline alterno** | Deepgram Nova-3 (STT) + Gemini 2.5 Flash (LLM) + Cartesia Sonic-3 (TTS) | Tuneable pieza por pieza. Mejor cuando quieres voz/idioma muy específicos. |
| **STT** | Deepgram Nova-3 (`$0.0043/min`) | Mejor latencia/precisión en español. |
| **LLM** | Gemini 2.5 Flash (`$0.15/$0.60` por 1M tok in/out) | Barato, rápido, function calling sólido. *(Ojo: Gemini 3 tiene bug con File Search → usar 2.5 para RAG.)* |
| **TTS** | Cartesia Sonic-3 (`$0.040/1K chars`) | Voz natural, soporta velocidad configurable (0.6–2.0). |
| **RAG** | Gemini File Search (vector store nativo) | 1 store por tenant; el `store_id` se guarda en `clients`. |
| **DB** | **PostgreSQL en Railway** (el de Foodie) | Se reutiliza el de Foodie tal cual. Acceso con SQLAlchemy async + Redis. Sin Supabase. |
| **Hosting agente** | LiveKit Cloud | `lk agent deploy`. Plan Build = 1 agente. |
| **Errores/APM** | Sentry | Ya integrado, sample 10–20%. |

**Regla de oro de los modos de voz (esto nos costó 4+ bugs):**
> **NUNCA mezcles stacks.** `gemini_live` y `realtime` (OpenAI) son stacks **completos**
> (STT+LLM+TTS en uno). No les pongas Cartesia/Deepgram encima. Solo `pipeline` es de piezas
> separadas y tuneable. Ver §6.3.

---

## 3. Cómo encaja en Foodie (mapa de integración)

### 3.1 Modelo mental: `restaurante = tenant`

Foodie ya es multi-restaurante. Mapea directo:

| VoiceAI | Foodie |
|---|---|
| `client` (tenant) | **`restaurant`** |
| `agent` (config de voz) | nuevo: **`voice_agent`** por restaurante (1+) |
| `contacts` | **clientes/comensales** de Foodie (ya existen) |
| `calls` / `call_events` | **nuevas tablas** de llamadas |
| `campaigns` / `campaign_calls` | **nuevas tablas** de campañas outbound |
| `credit_balances` | reusar el **billing de Foodie** o crear créditos de voz |
| `enabled_tools` | qué puede hacer el agente (reservar, pedir, transferir…) |

### 3.2 La diferencia técnica que SÍ importa: capa de acceso a datos

> **Aclaración clave:** Foodie **NO migra a Supabase**. Foodie ya tiene **PostgreSQL en
> Railway** y se queda ahí. Supabase solo era el *hosting* del Postgres de VoiceAI; por eso su
> código del agente usa `supabase-py`. Lo que "se migra" es **únicamente el código que
> lee/escribe en la DB**, para que use el Postgres de Railway de Foodie con su driver async.

VoiceAI accede a DB con **`supabase-py` (PostgREST sincrónico envuelto en `asyncio.to_thread`)**.
Foodie usará **SQLAlchemy async + asyncpg + Redis** sobre su **PostgreSQL de Railway**. Por tanto:

- **Reescribir** la capa de acceso del agente: `config_loader.py`, `session_handler.py`,
  `db.py` → usar el data layer de Foodie (SQLAlchemy async o un repositorio fino con asyncpg).
- **Conservar** las **firmas y dataclasses** (`AgentConfig`, `SlimClientConfig`,
  `UsageMetrics`): son agnósticas. Solo cambia el "cómo se lee/escribe".
- **Aprovechar Redis** (Foodie ya lo tiene) para lo que VoiceAI hacía con DB polling:
  - `active_calls` / límite de concurrencia → contador en Redis con TTL.
  - locks de campaña / dedup → Redis.
  - rate limiting → Redis.
  *(Esto es una mejora sobre VoiceAI, no una regresión.)*

> ⚠️ **Importante (conexión a la DB de Railway):** el worker de voz corre en **LiveKit
> Cloud**, separado del API de Foodie. Necesita **acceso de red al PostgreSQL de Railway**
> (la `DATABASE_URL` de Railway como secret en LiveKit Cloud). Railway expone una **URL
> pública de Postgres** que sirve para esto. Si prefieres no abrir la DB hacia afuera, expón
> un **API interno mínimo** en Foodie (leer config + escribir llamada) que el agente consuma
> por HTTP en vez de conexión directa.

### 3.3 Qué reutilizar — clasificado

**✅ Reutilizar casi intacto (lógica pura, agnóstica al transporte):**
- `agent/agent_factory.py` — `VoiceAgent`, construcción dinámica, filtrado de tools.
- `agent/pipeline_builder.py` — `build_stt/llm/tts/realtime_model/gemini_live_model`.
- `agent/call_lifecycle.py` — `CallLifecycleTracker` (disposition, ring/talk, timeline).
- `agent/session_handler.py` — cálculo de **costos reales** (las tarifas son oro, §8).
- `agent/hook_engine.py`, `agent/sentiment.py`, `agent/intent.py`, `agent/guardrails.py`.
- `agent/phone_utils.py` — normalización de teléfonos MX/E.164.

**🔧 Adaptar (cambiar capa de datos / transporte):**
- `agent/main.py` — el `entrypoint`: conservar el flujo, adaptar lectura de config y Redis.
- `agent/config_loader.py` — reescribir queries a SQLAlchemy/asyncpg.
- `api/services/phone_service.py` — la **config Twilio/LiveKit es reutilizable tal cual** (§5).
- `api/services/outbound_service.py` — runner de campañas; mover locks/concurrencia a Redis.

**🆕 Crear nuevo en Foodie:**
- Rutas FastAPI para administrar agentes/números/campañas/llamadas.
- Páginas React (shadcn) para dashboard de voz.
- Migraciones SQL de las tablas nuevas (adaptadas al estilo de Foodie).

**🚫 NO traer (al menos no en v1):**
- Multi-tenant billing complejo, Stripe/MercadoPago si Foodie ya cobra.
- Flow Builder visual, LoopTalk (test personas), Voice Cloning, Quality Firewall avanzado,
  Widget embeddable, orquestación multi-agente. Son features de Fase 3+; añaden mucha
  superficie. Empieza por prompt-driven simple.

---

## 4. Telefonía: Twilio + LiveKit paso a paso (lo más delicado)

> Esta sección es la que más dolor nos ahorró. Cópiala con cuidado.

### 4.1 Conceptos

- **Twilio Elastic SIP Trunk:** "tubo" SIP entre Twilio y LiveKit. Inbound y outbound.
- **LiveKit Inbound Trunk:** recibe las llamadas SIP de Twilio y las mete a un *room*.
- **LiveKit Dispatch Rule:** decide a qué *agente* y *room* va cada llamada.
- **SIP URI de LiveKit:** es el **project ID**, NO el subdominio. (Ver gotcha abajo.)

### 4.2 Setup Twilio → LiveKit (inbound)

```python
# api/services/phone_service.py — setup_twilio_elastic_sip_trunk()
trunk = client.trunking.v1.trunks.create(friendly_name="Foodie Voz")
trunk.origination_urls.create(
    friendly_name="LiveKit SIP",
    sip_url=f"sip:{SIP_URI};transport=tcp",   # ← TCP OBLIGATORIO
    priority=10, weight=10, enabled=True,
)
```

```python
# api/services/phone_service.py — setup_livekit_sip()
trunk = await lk.sip.create_sip_inbound_trunk(CreateSIPInboundTrunkRequest(
    trunk=SIPInboundTrunkInfo(
        name=f"twilio-{phone_number}",
        numbers=[phone_number],
        allowed_addresses=[              # IPs de Twilio (whitelist)
            "54.172.60.0/23", "54.244.51.0/24", "34.203.250.0/23",
        ],
    )))
rule = await lk.sip.create_sip_dispatch_rule(CreateSIPDispatchRuleRequest(
    name=f"route-{phone_number}",
    rule=SIPDispatchRule(dispatch_rule_individual=SIPDispatchRuleIndividual(
        room_prefix="call-")),
    trunk_ids=[trunk.sip_trunk_id],
    room_config=RoomConfiguration(agents=[
        RoomAgentDispatch(agent_name="foodie-voz")]),   # nombre del worker
))
```

### 4.3 ⚠️ Problemas conocidos de telefonía (los que ya pagamos)

| Problema | Solución |
|---|---|
| **SIP URI incorrecto** | El subdominio del proyecto NO es el SIP URI. El real es el **project ID** (`xxxxx.sip.livekit.cloud`). Está en LiveKit Dashboard → Telephony → SIP trunks (arriba a la derecha). |
| **Twilio usa UDP, LiveKit necesita TCP** | Poner `;transport=tcp` en el Origination URI. Sin esto, las llamadas no entran. |
| **`update_inbound_trunk` borra todo** | NO uses `update_inbound_trunk` con `SIPInboundTrunkInfo`: **reemplaza TODOS los campos** (números incluidos). **Recrea** el trunk. |
| **Twilio trial** | Solo llama a números verificados. Verifica tu celular en Console → Verified Caller ID para pruebas. |
| **Origination URL no se auto-configura** | Al comprar número, hay que apuntar su trunk a LiveKit manualmente (o automatizarlo). |
| **Geo permissions** | Activa MX/CO/etc. explícitamente (`enable_geo_permission`). No se asume. |

### 4.4 Caller ID outbound

En outbound, `CreateSIPParticipantRequest.sip_number` = el número **`from`** (Caller ID).
Debe ser un número que poseas en Twilio. Resolución de trunk/número: **agente primero,
cliente como fallback** (`_resolve_sip_trunk`).

### 4.5 Aislamiento por restaurante: BYOT vs Subaccounts

Tres formas de resolver credenciales Twilio (cascada **BYOT > Subaccount > Main**):

1. **Main account** (env `TWILIO_ACCOUNT_SID/AUTH_TOKEN`) — simple, todo en una cuenta.
2. **BYOT (Bring Your Own Twilio)** — el restaurante trae su cuenta; **él paga**. Bueno para
   cadenas grandes con contabilidad propia.
3. **Subaccounts** — subcuenta hija por restaurante; **Foodie paga** pero puede **suspender
   un restaurante sin tocar la cuenta principal**. Ideal para protegerte de abuso (spam).

> **Recomendación para Foodie v1:** arranca con **Main account** (1 cuenta, 1 número de
> pruebas). Cuando escales a muchos restaurantes con outbound, migra a **Subaccounts** para
> aislar riesgo. BYOT solo si un cliente enterprise lo pide. *(Twilio NO permite mover números
> entre cuentas fácilmente → planifícalo desde el inicio.)*

---

## 5. El agente de voz: arquitectura y flujo

### 5.1 Flujo end-to-end de una llamada Inbound

```
SIP (Twilio) → LiveKit → entrypoint(ctx)
 1. Detecta called_number (sip.trunkPhoneNumber) y caller_number (sip.phoneNumber)
 2. load_config_by_phone(called_number) → config del restaurante+agente
 3. Validaciones: límite de concurrencia, créditos/billing
 4. Registra "llamada activa" (Redis en Foodie)
 5. Carga en paralelo (asyncio.gather): RAG store, integraciones, hooks, memoria de contacto
 6. build_agent(config) → arma STT/LLM/TTS según agent_mode
 7. session.start(room) → conversación (loop de turnos)
 8. Al colgar → handler.finalize(): costos + transcript + análisis + webhook
```

### 5.2 Config del agente (lo que se guarda por restaurante)

`AgentConfig` (dataclass agnóstica — reusar):
- `system_prompt` (el cerebro), `greeting` (saludo)
- `agent_mode`: `pipeline` | `realtime` | `gemini_live`
- `voice_config` (JSONB): voz, velocidad, modelo, BYOK keys
- `transfer_number` (a dónde transferir a humano)
- `enabled_tools`: lista de capacidades habilitadas
- `business_hours` (con timezone, default `America/Mexico_City`)
- `max_concurrent_calls`
- `language` (`es`, `en`, `es-en`)

### 5.3 Los 3 modos de voz (elige por agente)

| Modo | Stack | Cuándo usarlo en Foodie | Costo aprox |
|---|---|---|---|
| **`gemini_live`** ⭐ | Gemini Live audio-to-audio | **Default.** Menor latencia, sin BYOK. Atención/servicio conversacional. | ~$0.023/min |
| **`pipeline`** | Deepgram + Gemini + Cartesia | Cuando quieras voz/idioma muy específico o tunear interrupciones. | ~$0.023/min |
| **`realtime`** | OpenAI Realtime | Solo si un cliente trae su key OpenAI (BYOK). | (key del cliente) |

**Restricciones críticas de Gemini Live (4+ bugs aprendidos):**
- El prompt se inyecta **UNA sola vez** al construir el modelo. Después de `session.start()`
  NADA puede modificar las instrucciones (`update_instructions` se ignora en silencio).
- ⇒ **Todo** (greeting, contexto, fecha/hora, script de campaña) debe ir **ANTES** de
  `build_gemini_live_model()`, en `config.agent.system_prompt`.
- NUNCA: `session.generate_reply()`, `session.say()`, mezclar TTS externo, modificar
  `_instructions` en runtime.
- Síntoma típico de violarlo: **"el agente no habla / silencio"**.

### 5.4 Turn detection / interrupciones (tuning)

Ajuste fino de cuándo el agente escucha vs habla. Valores que ya funcionan:

```python
# gemini_live (en build_gemini_live_model)
RealtimeInputConfig(automatic_activity_detection=AutomaticActivityDetection(
    start_of_speech_sensitivity=START_SENSITIVITY_LOW,   # ignora "ajá", "mm"
    end_of_speech_sensitivity=END_SENSITIVITY_HIGH,      # responde rápido
    prefix_padding_ms=200,
    silence_duration_ms=600,                             # espera 600ms de silencio
))
```

```python
# pipeline (en main.py)
silero.VAD.load(activation_threshold=0.5, min_speech_duration=0.1,
                min_silence_duration=0.4, sample_rate=8000)
AgentSession(min_endpointing_delay=0.5, max_endpointing_delay=3.0,
             min_interruption_duration=0.6, min_interruption_words=1)
```

- **Si el agente se corta con ruiditos:** sube `silence_duration_ms` (gemini) o
  `activation_threshold`/`min_interruption_words` (pipeline).
- **Si ignora interrupciones reales:** baja esos valores.
- **Prueba siempre con una llamada real**: subir VAD de más causó "el agente no responde nada".

### 5.5 Tools del agente (capacidades) — lo relevante para restaurantes

Reusables de VoiceAI + nuevas para Foodie:

| Tool | Reusable | Uso en Foodie |
|---|---|---|
| `transfer_to_human(reason)` | ✅ | Pasar a recepción/gerente. |
| `schedule_appointment(...)` | ✅ adaptar | **Reservaciones** de mesa. |
| `schedule_callback(...)` | ✅ | Devolver la llamada después. |
| `send_whatsapp(...)` | ✅ | Confirmación por WhatsApp (Foodie ya tiene WhatsApp). |
| `save_contact_info(...)` | ✅ | Capturar datos del comensal. |
| `recall_memory(query)` | ✅ | "La última vez pediste X". |
| `search_knowledge(query)` | ✅ | Menú, horarios, ubicación (RAG). |
| `create_order(...)` 🆕 | crear | **Tomar pedido** (pickup/delivery) → POS de Foodie. |
| `check_table_availability(...)` 🆕 | crear | Disponibilidad de mesas. |

> Para Gemini Live: las tools que tarden **>2.5s** son canceladas por el servidor. Usa
> timeouts agresivos y devuelve rápido (inserta en background si hace falta).

---

## 6. Inbound (atención y servicio)

**Casos de uso Foodie:**
- Responder horarios, ubicación, menú (RAG con `search_knowledge`).
- **Tomar reservaciones** (`schedule_appointment` → tu tabla de reservas).
- **Tomar pedidos** pickup/delivery (`create_order` → POS).
- Transferir a humano fuera de alcance (`transfer_to_human`).
- Capturar/identificar al comensal (`recall_memory`, `save_contact_info`).

**Setup mínimo:** 1 número Twilio → trunk LiveKit → dispatch rule → agente con
`system_prompt` del restaurante. El `called_number` resuelve qué restaurante atiende.

---

## 7. Outbound + campañas (lo que pediste para llamadas masivas)

### 7.1 Cómo se dispara una llamada outbound

```python
# api/services/outbound_service.py — _place_outbound_call()
await lk.room.create_room(CreateRoomRequest(
    name=f"campaign-{cid}-{eid}", metadata=room_metadata,
    empty_timeout=60,
    agents=[RoomAgentDispatch(agent_name="foodie-voz", metadata=room_metadata)],
))
await lk.sip.create_sip_participant(CreateSIPParticipantRequest(
    sip_trunk_id=trunk_id,          # trunk LiveKit→Twilio→destino
    sip_call_to=phone,              # destino (E.164)
    sip_number=from_number,         # Caller ID
    room_name=room_name,
    participant_identity=f"outbound-{eid}",
))
```

El `room.metadata` lleva `type:"outbound"`, `script`, `client_id`, `agent_id`,
`campaign_id`. El worker lee eso en el `entrypoint` y arma el agente con el **script de
campaña** inyectado en el prompt.

### 7.2 ⚠️ Bugs de outbound que YA resolvimos (no los repitas)

1. **Agente saluda antes de que contesten** → audio perdido. **Fix:** esperar el evento
   `_sip_connected` (hasta 60s) antes de hablar.
2. **Números NULL en outbound** → el participante SIP no estaba conectado al checar.
   **Fix:** actualizar números en el handler *después* de que conecta el SIP.
3. **`campaign_calls` atorado en "calling"** → `finalize()` no encontraba la llamada.
   **Fix:** búsqueda por `campaign_id + status` como fallback.
4. **Limpieza de stale matando llamadas activas** → timeout de 5 min mataba llamadas vivas.
   **Fix:** subir a **15 min**.
5. **Relanzar campaña "running"** → faltaba el botón. **Fix:** pausar antes de relanzar.

### 7.3 Safety controls (CRÍTICO para outbound — protege tu reputación y tu cuenta)

```python
DAILY_OUTBOUND_LIMIT      = 200      # llamadas/día/restaurante
MIN_ANSWER_RATE           = 0.20     # auto-pausa si <20% contestan
MIN_CALLS_FOR_RATE_CHECK  = 15       # mínimo de llamadas para evaluar
CALLING_TIMEOUT_MINUTES   = 15       # mata llamadas stuck
```

- **Auto-pausa** + alerta por email si la campaña va mal (>70% no contesta).
- **DNC (Do Not Call):** si el usuario dice "no me llamen", se agrega automáticamente.
  *(Para Foodie: imprescindible. Cumplimiento y reputación.)*
- **Concurrencia** controlada con semáforo (`max_concurrent`).
- **Reintentos:** 2 intentos, delay 30 min (`next_retry_at`).

### 7.4 Casos de uso outbound Foodie

- **Confirmación de reservación** ("su mesa para hoy 8pm, ¿confirma?").
- **Confirmación/seguimiento de pedido**.
- **Encuestas post-servicio** (NPS, "¿cómo estuvo su experiencia?").
- **Recuperación de clientes inactivos** ("hace tiempo no nos visita, le tenemos…").
- **Promociones / campañas** (con cuidado de DNC y horarios).
- **Recordatorios** de reservación.

### 7.5 Ciclo de vida de campaña

`draft → running → paused → completed`. El **runner** (`_campaign_runner`) hace loop:
health-check → limpia stale → calcula slots → lanza batch concurrente → repite.
> **Mejora para Foodie:** en VoiceAI el runner vive como `asyncio.Task` en el proceso API.
> En Foodie, considera moverlo a un **worker/scheduler dedicado** (o Celery/arq + Redis) para
> que reinicios del API no maten campañas en vuelo.

---

## 8. Costos y billing (las tarifas reales — esto es oro)

### 8.1 Tarifas verificadas en producción (USD)

```python
# Infra (por minuto)
RATE_LIVEKIT_PER_MIN   = 0.004
RATE_TELEPHONY_PER_MIN = 0.013          # Twilio MX

# STT (por minuto de audio)
deepgram = 0.0043   # Nova-3
google   = 0.006
openai   = 0.006

# LLM (por 1M tokens, input/output)
google    = 0.15 / 0.60     # Gemini 2.5 Flash
openai    = 0.15 / 0.60     # GPT-4o-mini
anthropic = 0.25 / 1.25     # Claude Haiku

# TTS (por 1K caracteres)
cartesia   = 0.040          # Sonic-3
elevenlabs = 0.120
openai     = 0.015

# Gemini Live (stack completo): ~$0.023/min total
```

### 8.2 Fórmula de costo por llamada (`session_handler.finalize`)

```
cost_livekit   = min × 0.004
cost_telephony = min × 0.013          (solo si hay número/SIP)
cost_stt       = min × stt_rate
cost_llm       = (in_tok/1M)×in_rate + (out_tok/1M)×out_rate   (tokens ≈ chars/4)
cost_tts       = (chars/1000) × tts_rate
cost_total     = suma de todo
```

Se guarda **desglosado** en `calls` (`cost_livekit`, `cost_stt`, `cost_llm`, `cost_tts`,
`cost_telephony`, `cost_total`) + `metadata` JSONB con uso (chars TTS, tokens estimados).

**Regla de negocio (de VoiceAI):** margen 75% sobre costo, conversión USD→MXN configurable.
Para Foodie, decide si cobras créditos de voz aparte o lo absorbes en el plan del restaurante.

### 8.3 Costo estimado de referencia

Una llamada de **3 minutos en `gemini_live` con telefonía** ≈
`(0.004 + 0.013)×3 + 0.023×3` ≈ **$0.12 USD** (~$2.4 MXN). Útil para presupuestar campañas.

---

## 9. Tracking profesional de llamadas (`call_lifecycle`) — reusar tal cual

`CallLifecycleTracker` da trazabilidad de nivel call-center. Eventos:
`call_initiated, sip_answered, agent_ready, first_speech_agent/user, user_hangup,
agent_hangup, transfer_*, sip_rejected/unavailable, no_answer, timeout, error, call_ended`.

Métricas calculadas: `ring_duration`, `talk_duration`, `disposition`
(`completed/short_call/abandoned/no_answer/transferred/voicemail/error`), `disconnect_reason`,
`disconnect_by`, latencia al primer "hola". Todo va a `calls` + tabla `call_events` (timeline).

> Para Foodie es **muy valioso** en outbound: saber por qué falló cada llamada (no contestó,
> rechazada, buzón, error SIP). LiveKit expone `disconnect_reason`: `USER_UNAVAILABLE`,
> `USER_REJECTED`, `SIP_TRUNK_FAILURE`.

---

## 10. Best practices y lecciones aprendidas (de la auditoría de 104 bugs)

**Estabilidad runtime (las que más duelen en voz):**
- **Todo I/O async.** Cualquier llamada sync a DB/API bloquea el event loop y **corta el
  audio**. En VoiceAI se envolvía en `asyncio.to_thread`; en Foodie usa drivers async nativos.
- **Previene garbage collection de tasks:** guarda referencias de `asyncio.create_task` en un
  `set` (`_bg_tasks`). Si no, el GC mata webhooks/análisis a medio vuelo.
- **Cierra conexiones LiveKitAPI** con `try/finally` (fugas de conexión).
- **`finalize()` a prueba de fallos:** envuelve el insert de la llamada en try/except. Si la DB
  parpadea, no pierdas billing + webhooks + contacto.
- **No fallback a IDs falsos** (`00000000…`) cuando no hay config → rechaza limpio.
- **Protege `session.start()`** con try/except para que un crash no se salte el cleanup/billing.

**Seguridad (multi-tenant):**
- **Aislamiento por tenant en TODAS las queries** (`WHERE restaurant_id = ...`). El bug más
  recurrente fue cross-tenant (ver datos de otro restaurante).
- **Auth en todas las rutas** (varias quedaron sin auth por olvido).
- **Valida URLs externas (SSRF)** en webhooks/integraciones.
- **Webhooks con HMAC + idempotencia** (evita duplicados y spoofing).
- **Cifra credenciales en reposo** (Fernet): keys de Twilio/BYOK nunca en claro.

**Datos:**
- **Costos por conteo incremental real**, no por fórmula a posteriori.
- **Timezones explícitos** (default `America/Mexico_City`).

**Deploy del agente (LiveKit Cloud):**
- **NO valides env vars a nivel de módulo** en `agent/main.py`: el build corre
  `python -m agent.main download-files` y truena. Valida dentro de funciones.
- `livekit.toml` necesita `id` bajo `[agent]`. **No** hagas `COPY livekit.toml` en el Dockerfile.
- `ENCRYPTION_KEY` debe estar en **LiveKit Cloud** (no solo en el API) para descifrar BYOK keys.
- Plan Build = 1 agente → usa `lk agent deploy` (actualizar), no `lk agent create`.

---

## 11. El camino: roadmap de implementación por fases

> Regla de VoiceAI que aplicamos: **no avanzar a la siguiente fase hasta que una llamada
> end-to-end funcione.** Mínimo viable primero, sin sobre-ingeniería.

### Fase 0 — Preparación (infra y cuentas)
- [ ] Cuenta **Twilio** (para Foodie) + 1 número MX de pruebas + Geo Permissions MX.
- [ ] Proyecto **LiveKit Cloud** + obtener el **SIP URI real (project ID)**.
- [ ] API keys: **Google (Gemini)**, Deepgram, Cartesia.
- [ ] Decidir acceso del worker a la DB de Foodie (conexión directa vs API interno).
- [ ] Definir tablas nuevas en PostgreSQL de Foodie (migraciones, estilo SQLAlchemy).

### Fase 1 — Telefonía Inbound (el "hola, ¿bueno?")
- [ ] `phone_service` adaptado: crear Twilio Elastic Trunk (`transport=tcp`) + LiveKit
      inbound trunk + dispatch rule.
- [ ] Worker `foodie-voz` mínimo en LiveKit Cloud: `entrypoint` que carga config por número.
- [ ] **Meta:** llamar al número y que el agente responda con un saludo (modo `gemini_live`).

### Fase 2 — Agente real Inbound (servicio)
- [ ] `config_loader` con SQLAlchemy: leer `voice_agent` por restaurante.
- [ ] `agent_factory` + tools básicas: `search_knowledge` (RAG menú/horarios),
      `transfer_to_human`, `save_contact_info`.
- [ ] RAG: 1 Gemini File Search store por restaurante (menú, FAQ, políticas).
- [ ] Tool `schedule_appointment` → reservaciones; `create_order` → POS (si aplica).

### Fase 3 — Costos + tracking
- [ ] `session_handler.finalize` con las tarifas de §8 → escribe `calls` desglosado.
- [ ] `call_lifecycle` → `call_events`. Concurrencia/active_calls en **Redis**.
- [ ] Dashboard React: lista de llamadas + detalle (transcript, costos, timeline).

### Fase 4 — Outbound + campañas
- [ ] `outbound_service`: disparar llamada (`create_sip_participant`), runner con concurrencia.
- [ ] **Safety controls** (§7.3): daily limit, answer-rate auto-pause, DNC, stale cleanup.
- [ ] Tablas `campaigns` / `campaign_calls`. UI para crear/lanzar/pausar/relanzar.
- [ ] Casos: confirmación de reserva, encuesta post-servicio, recuperación.

### Fase 5 — Hardening (antes de producción real)
- [ ] Aplicar checklist de §10 (async, GC tasks, finalize a prueba de fallos, aislamiento tenant).
- [ ] Sentry en API + agente. Alertas (créditos bajos, provider down, Twilio health).
- [ ] Subaccounts Twilio si escalas a muchos restaurantes con outbound.
- [ ] Tuning de turn detection con llamadas reales en español MX.

---

## 12. Checklist de variables de entorno

**En el worker (LiveKit Cloud):**
```
LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
GOOGLE_API_KEY            # Gemini (LLM + Gemini Live)
DEEPGRAM_API_KEY         # solo si usas modo pipeline
CARTESIA_API_KEY         # solo si usas modo pipeline
DATABASE_URL             # Postgres de Railway de Foodie (URL pública) o URL del API interno
ENCRYPTION_KEY           # Fernet, para descifrar BYOK keys  ← imprescindible
SENTRY_DSN
TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN   # outbound (caller ID / subaccounts)
```

**En el API de Foodie (lo que ya tendrá + nuevos):**
```
TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
GOOGLE_API_KEY, ENCRYPTION_KEY
OUTBOUND_DAILY_LIMIT=200, OUTBOUND_MIN_ANSWER_RATE=0.20,
OUTBOUND_CALLING_TIMEOUT_MINUTES=15
```

---

## 13. Resumen de qué tomar de VoiceAI (tabla final)

| Componente VoiceAI | Acción | Prioridad |
|---|---|---|
| `agent/agent_factory.py` | Reutilizar (adaptar tools a Foodie) | 🔴 Alta |
| `agent/pipeline_builder.py` | Reutilizar casi intacto | 🔴 Alta |
| `agent/session_handler.py` (costos) | Reutilizar lógica, reescribir capa DB | 🔴 Alta |
| `agent/call_lifecycle.py` | Reutilizar intacto | 🔴 Alta |
| `agent/main.py` (entrypoint/dispatch) | Adaptar (Redis, capa DB) | 🔴 Alta |
| `api/services/phone_service.py` (Twilio/LiveKit) | Reutilizar config, adaptar persistencia | 🔴 Alta |
| `api/services/outbound_service.py` | Adaptar (runner a worker dedicado + Redis) | 🟠 Media |
| `hook_engine`, `sentiment`, `intent`, `guardrails` | Reutilizar, activar gradual | 🟠 Media |
| `config_loader.py` | Reescribir a SQLAlchemy/asyncpg | 🟠 Media |
| Tarifas de costos (§8) | Copiar valores | 🔴 Alta |
| Gotchas de telefonía (§4.3) | Leer ANTES de configurar | 🔴 Alta |
| Flow Builder / LoopTalk / Voice Cloning / Widget / Multi-agente | **No traer en v1** | ⚪ Omitir |

---

### Cierre

El motor de voz de VoiceAI está **bien desacoplado**: el core (agente, tools, análisis,
costos, lifecycle) es **independiente del transporte SIP/LiveKit**, y eso es justo lo que
hace viable injertarlo en Foodie sin rehacerlo. Lo único que cambia de fondo es la **capa de
acceso a datos** (de `supabase-py` → SQLAlchemy async + Redis, **sobre el mismo Postgres de
Railway de Foodie** — sin Supabase) y el **dispatch** de entrada. Todo lo demás —
telefonía, modos de voz, costos, campañas, safety controls — son aprendizajes ya pagados que
puedes copiar con confianza.

**Empieza chico:** 1 número, 1 restaurante, modo `gemini_live`, que conteste y salude. A
partir de ahí, el resto del documento es el mapa.
