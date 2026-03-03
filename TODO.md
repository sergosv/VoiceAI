# Voice AI Platform — Mejoras Pendientes

> Actualizado: 2026-03-02

## Prioridad Alta

- [ ] **Commit + Deploy** — Hay ~24 archivos sin commitear (billing, cost transparency, gift credits, MCP). Deploy a LiveKit Cloud + Railway.
- [ ] **Agregar env vars a `.env.example`** — Faltan `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `MERCADOPAGO_ACCESS_TOKEN`
- [ ] **Crear `railway.toml`** — Para que Railway use `Dockerfile.railway` explícitamente y no tome el Dockerfile del agente por error

## Prioridad Media

- [ ] **MercadoPago** — Implementar SDK real en `api/payments.py` y webhook en `api/routes/webhooks.py` (actualmente placeholder). Necesario para cobrar en MXN.
- [ ] **Tests para billing/costs** — Los módulos más críticos (dinero) no tienen tests: `billing.py`, `costs.py`, `webhooks.py`, `agent/billing.py`
- [ ] **Tests para rutas Fase 3+** — 11 de 16 rutas API sin tests: agents, campaigns, contacts, appointments, chat, mcp, voices, ai
- [ ] **Python version mismatch** — `Dockerfile` usa 3.12, `Dockerfile.railway` usa 3.13. Unificar a 3.13.

## Prioridad Baja

- [ ] **Email de alertas de créditos** — `api/tasks/credit_alerts.py` solo hace log, no envía email real. Integrar con SendGrid, SES o Resend.
- [ ] **Onboarding self-service** — Que nuevos clientes puedan registrarse solos desde una landing page, sin intervención de admin.
- [ ] **Analytics avanzados** — Sentiment analysis en tiempo real, conversion rates, métricas de calidad de llamada. Ya existe análisis post-llamada en campañas, pero falta dashboard de analytics dedicado.

## Ideas Futuras

- [ ] **Conmutador IVR** — Menú de opciones pre-agente ("Presione 1 para ventas..."). Baja prioridad porque el Modo Inteligente (orchestrator) ya hace routing automático por IA, que es mejor experiencia de usuario.
- [ ] **Grabación de llamadas** — Almacenar audio de llamadas para review/compliance
- [ ] **WhatsApp bot** — Agente IA por texto en WhatsApp (actualmente solo se envían mensajes salientes)
- [ ] **Web widget** — Botón de chat/voz embebible en sitios web de clientes
- [ ] **Multi-idioma dinámico** — Detectar idioma del caller y adaptar agente automáticamente
- [ ] **Dashboard analytics dedicado** — Gráficas de tendencias, top intents, satisfacción, comparativa entre agentes
