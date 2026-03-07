# Voice AI Platform — Roadmap de Features Futuras

> Documento vivo con ideas discutidas, features planeadas y prioridades.
> Ultima actualizacion: 2026-03-06

---

## Estado Actual — Fases Completadas

| Fase | Descripcion | Status |
|------|-------------|--------|
| 1 | Motor de voz (agent, SIP, LiveKit, Gemini) | Completada |
| 2 | API FastAPI + Dashboard React | Completada |
| 3 | Tools (calendar, whatsapp, crm), outbound, BYOK, multi-agent | Completada |
| 4 | MCP Integration (servers HTTP/stdio nativos en LiveKit) | Completada |
| 5 | Billing (creditos, Stripe, MercadoPago) | Completada |
| 6 | Flow Builder + API Integrations | Completada |
| 7 | UX/UI Overhaul (sidebar, command palette, filtros) | Completada |
| 8 | Template Store + Agent Wizard | Completada |
| 9 | Hardening (seguridad, tests, CI, logging) | Completada |
| 10 | Analytics + Web Widget embeddable | Completada |

---

## Features Futuras — Agentes

### 1. Agentes Proactivos (Prioridad Alta)

Sistema de acciones programadas que permite al agente tomar la iniciativa de contactar usuarios.

#### Dos tipos de proactividad

**Tipo 1: Reglas de negocio (configuradas por el dueno del agente en el dashboard)**

Reglas automaticas que aplican a todos los contactos:

| Regla | Trigger | Canal | Ejemplo |
|-------|---------|-------|---------|
| `callback_missed_call` | Llamada perdida | call | Devolver llamada en 15 min |
| `followup_no_conversion` | Llamada sin cita/venta | whatsapp/call | Seguimiento al dia siguiente |
| `reminder_appointment` | Cita agendada | whatsapp/sms | Recordar 1 hora antes |
| `reengagement` | Lead frio (X dias sin contacto) | call/whatsapp | Reactivar despues de 7 dias |
| `post_sale` | Conversion exitosa | whatsapp | Encuesta de satisfaccion |
| `custom_schedule` | Periodico (cron-like) | call/whatsapp | Seguimiento semanal |

Se configuran una vez en el dashboard y corren automaticamente.

**Tipo 2: Instrucciones conversacionales (el usuario le pide al agente durante la llamada)**

El usuario final le dice al agente cosas como:
- "Recuerdame manana a las 2 de mi cita con el doctor"
- "Mandame un WhatsApp el viernes con el resumen"
- "Llamame la proxima semana para darme seguimiento"

El agente entiende, programa la accion, y la ejecuta en la fecha indicada.
Esto convierte al agente en un **asistente personal con memoria y acciones futuras**.

#### Arquitectura propuesta

**Campo en `agents`:**
```sql
ALTER TABLE agents ADD COLUMN proactive_config jsonb DEFAULT NULL;
-- NULL = agente NO proactivo, con contenido = activo
```

**Estructura del `proactive_config`:**
```json
{
  "enabled": true,
  "rules": [
    {
      "type": "callback_missed_call",
      "delay_minutes": 15,
      "channel": "call",
      "message": "Hola, vi que intentaste comunicarte. En que puedo ayudarte?",
      "max_attempts": 2,
      "schedule": { "days": ["mon","tue","wed","thu","fri"], "hours": "09:00-19:00" }
    },
    {
      "type": "followup_no_conversion",
      "delay_minutes": 1440,
      "channel": "whatsapp",
      "message": "Hola {{name}}, ayer platicamos sobre {{topic}}. Tienes alguna duda?",
      "condition": { "status": "completed", "no_appointment": true }
    },
    {
      "type": "reminder_appointment",
      "delay_minutes": -60,
      "channel": "whatsapp",
      "message": "Recordatorio: tienes cita en 1 hora. Confirmas asistencia?"
    }
  ]
}
```

**Tabla `scheduled_actions`:**
```sql
CREATE TABLE scheduled_actions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id uuid REFERENCES agents(id),
  client_id uuid REFERENCES clients(id),
  rule_type text NOT NULL,
  channel text NOT NULL,            -- 'call' | 'whatsapp' | 'sms'
  target_number text NOT NULL,
  target_contact_id uuid REFERENCES contacts(id),
  message text,
  metadata jsonb DEFAULT '{}',      -- contexto: call_id original, topic, etc.
  scheduled_at timestamptz NOT NULL,
  status text DEFAULT 'pending',    -- pending | executing | completed | failed | cancelled
  attempts int DEFAULT 0,
  max_attempts int DEFAULT 2,
  last_attempt_at timestamptz,
  created_at timestamptz DEFAULT now()
);
```

**Function tool para Tipo 2 (instrucciones conversacionales):**
```python
@function_tool()
async def schedule_reminder(
    description: str,    # "Cita con el doctor"
    datetime_str: str,   # "2026-03-07T14:00:00"
    channel: str = "call"
) -> str:
    """Programa un recordatorio para el contacto en la fecha indicada."""
    # INSERT en scheduled_actions
    return f"Listo, te recordare '{description}' el {fecha}"
```

**Flujo:**
```
Fuente 1: Reglas de negocio (dashboard)      --+
                                                +--> scheduled_actions --> worker --> accion
Fuente 2: Instrucciones del usuario (tool)   --+

Background worker (cada 60s):
  SELECT * FROM scheduled_actions WHERE status='pending' AND scheduled_at <= now()
  Para cada accion:
    channel='call'     --> outbound_service.make_call()
    channel='whatsapp' --> whatsapp_service.send_message()
    UPDATE status
```

**Impacto en servidor:** Minimo. Worker es un `asyncio.create_task` con query cada 60s. El costo real es la accion saliente, no el scheduling. Concurrencia controlada por `Semaphore` existente en outbound_service.

**UI en Dashboard:**
- Toggle proactividad on/off por agente
- Lista de reglas con editor visual
- Cada regla: tipo, delay, canal, mensaje (con variables {{name}}, {{topic}}), horario, max intentos
- Tab dedicada en Settings del agente o seccion en tab Avanzado

#### Implementacion requerida
1. Migracion: `proactive_config` en agents + tabla `scheduled_actions`
2. Background worker: `api/services/proactive_worker.py`
3. Trigger post-llamada en `session_handler.py`
4. Function tool `schedule_reminder` en agent
5. API endpoints CRUD para reglas
6. UI en Settings del agente

---

### 2. Memoria Persistente del Agente

El agente recuerda conversaciones pasadas con el mismo contacto.

- Resumen automatico post-llamada guardado en `contacts.context_notes` o tabla dedicada
- Al recibir llamada, cargar historial del contacto y pasarlo como contexto al LLM
- "Hola Juan, la ultima vez hablamos sobre tu poliza de auto. Como te fue?"
- Requiere: matching de caller_number con contacto existente

---

### 3. Sentimiento y Escalacion Inteligente

- Analisis de sentimiento en tiempo real durante la llamada
- Si detecta frustracion/enojo sostenido, el agente cambia de tono o escala
- Configuracion de umbrales por agente: "Si sentimiento negativo > 3 turnos, transferir a humano"
- Metricas de sentimiento guardadas por llamada para analytics

---

### 4. Multi-idioma Dinamico

- Deteccion automatica del idioma del caller en los primeros segundos
- Switch de STT/TTS/prompt al idioma detectado (es-MX, en-US, pt-BR)
- Configuracion por agente: idiomas habilitados y prompt por idioma
- Util para negocios con clientes en Mexico, USA y Brasil

---

### 5. Modos de Conversacion Avanzados

Mas alla del modo actual (conversacional libre):

- **Modo encuesta**: preguntas predefinidas en orden, respuestas guardadas
- **Modo quiz/evaluacion**: preguntas con respuestas correctas, scoring
- **Modo negociacion**: el agente tiene rangos de precios/descuentos autorizados
- **Modo entrevista**: filtra candidatos con preguntas situacionales, genera reporte

---

### 6. Voz Clonada del Cliente

- Integrar clonacion de voz (Cartesia custom voices o ElevenLabs)
- El dueno del negocio graba 30s de su voz
- El agente habla con SU voz
- Diferenciador enorme para negocios personales (doctores, abogados, coaches)

---

## Features Futuras — Plataforma

### 7. Onboarding Self-Service

- Registro publico sin necesidad de admin
- Wizard de setup: crear cuenta > configurar agente > subir docs > probar
- Free tier con X minutos/mes
- Upgrade a plan pagado desde el dashboard

---

### 8. API Publica para Developers

- Documentacion OpenAPI completa con ejemplos
- API keys por cliente (no solo JWT)
- Rate limits por plan
- SDKs: Python, Node.js, curl examples
- Webhooks configurables (call.completed, lead.qualified, appointment.created)

---

### 9. Marketplace de Templates

- Templates compartidos por la comunidad
- Rating y reviews
- Categorias por industria y objetivo
- Import/export de configuraciones completas (prompt + flow + tools)

---

### 10. Analytics Avanzados

- Funnel de conversion: llamada > contacto > cita > venta
- ROI calculator: costo de llamadas vs valor de conversiones
- Comparativo temporal: esta semana vs anterior
- Alertas: "Las llamadas fallidas subieron 30% hoy"
- Export a CSV/PDF para reportes

---

### 11. Integraciones Nativas

- **CRM**: HubSpot, Salesforce, Pipedrive (sync bidireccional)
- **Calendario**: Google Calendar, Outlook (ya existe basico, expandir)
- **Pagos**: cobro durante la llamada via link de pago
- **Email**: enviar resumen post-llamada al contacto
- **Slack/Teams**: notificaciones de llamadas importantes

---

## Pendientes Operativos (Config/Deploy, no codigo)

1. Configurar Stripe con llaves reales y probar pago
2. Probar WhatsApp en vivo (webhook Railway > Evolution API)
3. Deploy completo: push a LiveKit Cloud + Railway
4. MercadoPago SDK: completar OXXO/SPEI
5. Sentry: crear cuenta + DSN
6. Dominio innotecnia.app: SSL + DNS final

---

## Prioridades Sugeridas

**Corto plazo (siguiente sprint):**
- Agentes Proactivos (Tipo 1 + Tipo 2) — mayor diferenciador
- Memoria Persistente — mejora dramatica en UX

**Mediano plazo:**
- Onboarding Self-Service — desbloquea crecimiento
- Analytics Avanzados — valor para clientes existentes
- Sentimiento + Escalacion — profesionaliza el servicio

**Largo plazo:**
- Multi-idioma Dinamico
- Voz Clonada
- Marketplace de Templates
- API Publica + SDKs
- Integraciones nativas con CRMs
