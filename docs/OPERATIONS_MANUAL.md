# Manual de Operaciones — VoiceAI Platform

> Documento para el dueño/administrador de la agencia.
> Ultima actualizacion: 2026-03-16

---

## 1. Servicios que debes pagar (no olvidar)

### Infraestructura (pagos mensuales fijos)

| Servicio | Para que sirve | Costo aprox. | Donde pagar | Frecuencia |
|----------|---------------|--------------|-------------|------------|
| **Railway** | API + Dashboard backend | $5-20/mo (por uso) | railway.app | Mensual auto |
| **Supabase** | Base de datos PostgreSQL | $25/mo (Pro plan) | supabase.com | Mensual auto |
| **Sentry** | Monitoreo de errores | $29/mo (Team plan) | sentry.io | Mensual auto |
| **Cloudflare Pages** | Hosting del dashboard | GRATIS | cloudflare.com | — |
| **Cloudflare R2** | Almacenamiento de grabaciones | ~$0.015/GB/mes | cloudflare.com | Mensual auto |
| **Resend** | Envio de emails (alertas, clientes) | $0-20/mo | resend.com | Mensual auto |

### Servicios de voz e IA (pagos por consumo)

| Servicio | Para que sirve | Costo por minuto | Donde pagar |
|----------|---------------|-----------------|-------------|
| **LiveKit Cloud** | Infraestructura de audio en tiempo real | $0.004/min | livekit.io |
| **Twilio** | Telefonia SIP (llamadas reales) | $0.013/min (MX) | twilio.com |
| **Deepgram** | Speech-to-Text (STT) | $0.0043/min | deepgram.com |
| **Google AI (Gemini)** | LLM + RAG (cerebro del agente) | ~$0.003/min | aistudio.google.com |
| **Cartesia** | Text-to-Speech (TTS, la voz) | ~$0.006/min | cartesia.ai |

### Pagos y facturacion

| Servicio | Estado | Para que sirve |
|----------|--------|---------------|
| **Stripe** | ACTIVO (produccion) | Cobros con tarjeta a tus clientes |
| **MercadoPago** | PENDIENTE | OXXO/SPEI para mercado mexicano |

### Costo total por minuto de llamada

```
LiveKit:     $0.004
Twilio:      $0.013   (solo llamadas telefonicas, widget no usa Twilio)
Deepgram:    $0.004
Gemini:      $0.003
Cartesia:    $0.006
─────────────────────
TOTAL:      ~$0.030 USD/min  ($1.80 USD/hora)
```

Con margen de 75% → le cobras al cliente ~$0.12 USD/credito (1 credito = 1 minuto).

---

## 2. Dashboards que debes conocer

| Dashboard | URL | Para que |
|-----------|-----|---------|
| **Tu plataforma** | https://agentes.innotecnia.app | Gestionar clientes, agentes, ver llamadas |
| **Sentry** | https://sentry.io | Errores en tiempo real, performance |
| **LiveKit Console** | https://console.livekit.cloud | SIP trunks, agentes desplegados, rooms activas |
| **Twilio Console** | https://console.twilio.com | Numeros, trunks SIP, logs de llamadas |
| **Stripe Dashboard** | https://dashboard.stripe.com | Pagos recibidos, disputas, webhook logs |
| **Supabase** | https://supabase.com/dashboard | Base de datos, usuarios, logs |
| **Railway** | https://railway.app | API deployment, logs del servidor, env vars |
| **Cloudflare** | https://dash.cloudflare.com | DNS, R2 (grabaciones), Pages (dashboard) |
| **Resend** | https://resend.com | Emails enviados, deliverability |
| **Evolution API** | Tu instancia Railway | Instancias WhatsApp conectadas |

---

## 3. Que monitorear diariamente

### Critico (revisar cada dia)

- [ ] **Sentry** — Revisar errores nuevos. Si hay un spike de errores, algo se rompio.
- [ ] **Balance de Stripe** — Verificar que no haya disputas/chargebacks pendientes.
- [ ] **Railway logs** — Un vistazo rapido a que no haya errores 500 repetitivos.

### Semanal

- [ ] **Llamadas fallidas** — En tu dashboard, filtrar llamadas con status `error`. Si hay muchas, investigar.
- [ ] **Provider health** — `GET /api/admin/provider-health` — Verificar que todos los circuitos estan cerrados (healthy).
- [ ] **Costos acumulados** — Revisar en Twilio, Deepgram, Google AI, Cartesia que el consumo este acorde al numero de clientes.
- [ ] **Grabaciones en R2** — Verificar que no este creciendo descontroladamente (no hay limpieza automatica aun).
- [ ] **Creditos de clientes** — Revisar que ningun cliente activo tenga saldo en cero sin saberlo.

### Mensual

- [ ] **Facturas de todos los servicios** — Bajar y guardar facturas de Railway, Supabase, Sentry, Twilio, etc.
- [ ] **Margen de ganancia real** — Comparar lo cobrado a clientes vs lo gastado en proveedores.
- [ ] **Uso de base de datos** — En Supabase, verificar tamano de tablas. `calls` y `whatsapp_messages` crecen rapido.
- [ ] **Rotar credenciales** — Evaluar si alguna API key necesita rotarse por seguridad.
- [ ] **Actualizar tipo de cambio** — En pricing_config, actualizar `usd_to_mxn_rate` si el peso se movio mucho.

---

## 4. Alertas automaticas que ya tienes

| Alerta | Cuando se dispara | Donde llega |
|--------|--------------------|-------------|
| **Sentry errors** | Cualquier error en API o agente | Email (Sentry) |
| **Provider caido** | Circuit breaker se abre (3+ fallas seguidas) | Email a ADMIN_ALERT_EMAIL |
| **Creditos bajos (warning)** | Cliente baja de 20% de saldo | Email al cliente |
| **Creditos bajos (critico)** | Cliente baja de 5% de saldo | Email al cliente |
| **Campana pausada** | Answer rate < 20% en outbound | Email al admin |
| **Webhook DLQ** | Webhook de cliente falla 3+ veces | Log (revisar en dashboard admin) |

### Alertas que NO tienes y deberas agregar

- **Saldo bajo en Twilio** — Twilio no avisa automaticamente si se te acaba el saldo. Pon una alerta manual en Twilio Console → Billing → Alerts.
- **Saldo bajo en Deepgram/Cartesia** — Misma situacion. Configura alertas en cada panel.
- **Disco de Supabase lleno** — Supabase avisa por email si llegas al limite, pero monitorea tu plan.
- **R2 storage > X GB** — No hay alerta, revisar manualmente.

---

## 5. Estructura de precios para tus clientes

### Como funciona el modelo de creditos

```
1 credito ≈ 1 minuto de llamada

Costo real por credito:  ~$0.030 USD
Precio venta (75% margen): ~$0.12 USD por credito
```

### Paquetes actuales

| Paquete | Creditos | Precio USD | Precio MXN (aprox) | Descuento |
|---------|----------|-----------|---------------------|-----------|
| Starter | 100 | $14 | $280 | 0% |
| Business | 500 | $63 | $1,260 | 10% |
| Pro | 2,000 | $224 | $4,480 | 20% |
| Enterprise | 5,000 | $525 | $10,500 | 35% |

### Ajustar precios

1. Ir a tu dashboard → Admin → Precios
2. Modificar `profit_margin` (actualmente 0.75 = 75%)
3. Los paquetes se recalculan automaticamente
4. Actualizar `usd_to_mxn_rate` si cambio el tipo de cambio

---

## 6. Dar de alta un cliente nuevo

### Checklist

1. [ ] Crear cuenta de usuario en tu dashboard (Admin → Usuarios)
2. [ ] Crear el registro del cliente (Admin → Clientes)
3. [ ] Crear al menos un agente para el cliente
4. [ ] Configurar el system prompt del agente (instrucciones de que hace y como habla)
5. [ ] Si usa telefono: asignar numero Twilio + crear SIP trunk
6. [ ] Si usa WhatsApp: crear instancia en Evolution API + configurar webhook
7. [ ] Si usa widget web: generar el embed code desde el dashboard
8. [ ] Subir documentos de conocimiento (RAG) si el agente necesita consultar info
9. [ ] Regalar creditos iniciales (10 por defecto) o que compre un paquete
10. [ ] Hacer llamada de prueba para verificar que todo funciona

### Canales disponibles por agente

| Canal | Requisito | Costo adicional |
|-------|-----------|-----------------|
| **Telefono** | Numero Twilio + SIP trunk | $0.013/min (Twilio) |
| **Widget web** | Embed code en su sitio | $0 adicional |
| **WhatsApp** | Instancia Evolution API | $0 (tu pagas Evolution) |
| **GoHighLevel** | Cuenta GHL del cliente | $0 adicional |

---

## 7. Cuando algo falla — Guia rapida

### "Un cliente dice que su agente no contesta llamadas"

1. Verificar en Sentry si hay errores recientes del agente
2. En LiveKit Console → Rooms: ver si hay rooms activas
3. En Twilio Console → SIP trunks: verificar que el trunk esta activo
4. Verificar que el agente esta desplegado: `lk agent deploy` si es necesario
5. Revisar que el numero del cliente este mapeado correctamente en la DB

### "El agente contesta pero no habla / se queda mudo"

1. Verificar Cartesia (TTS) — puede estar caido. El circuit breaker debio hacer fallback.
2. Verificar que el agente tenga system prompt configurado
3. Revisar en Sentry errores de tipo `TTS` o `LLM`
4. Probar con una llamada de prueba desde tu numero verificado en Twilio

### "WhatsApp no responde"

1. Verificar estado de la instancia Evolution: debe decir `open`
2. Revisar logs de Railway buscando `Evolution webhook`
3. Si el numero aparece raro (muchos digitos), puede ser un LID — ya esta corregido
4. Verificar que `auto_reply: true` y `is_paused: false` en la config

### "Un cliente no puede comprar creditos"

1. Verificar Stripe Dashboard → Payments: buscar el intento de pago
2. Si fallo, revisar el motivo (tarjeta rechazada, fondos insuficientes, etc.)
3. Verificar que el webhook de Stripe este configurado y respondiendo 200
4. Puedes regalar creditos manualmente desde Admin → Clientes → Ajustar saldo

### "Se cayo todo"

1. Railway → Verificar que el servicio este corriendo (no en deploy/crash loop)
2. Supabase → Verificar que la base de datos este accesible
3. Si Railway se cayo: reiniciar el servicio desde el dashboard de Railway
4. Si Supabase se cayo: esperar (es manejado por ellos) y verificar status.supabase.com

---

## 8. Mantenimiento periodico

### Cada mes

| Tarea | Como hacerlo |
|-------|-------------|
| Revisar y pagar facturas | Cada servicio tiene su panel de billing |
| Verificar margen de ganancia | Dashboard Admin → ver costos vs ingresos |
| Backup de base de datos | Supabase lo hace automatico, pero descarga uno manual |
| Revisar errores en Sentry | Resolver los mas frecuentes |
| Limpiar grabaciones viejas | R2 → borrar grabaciones de > 90 dias (manual por ahora) |

### Cada trimestre

| Tarea | Como hacerlo |
|-------|-------------|
| Rotar API keys sensibles | Generar nuevas en cada proveedor, actualizar en Railway env vars |
| Revisar limites de plan | LiveKit (1 agente concurrente), Supabase (conexiones), etc. |
| Actualizar dependencias | `pip install --upgrade` + probar en staging |
| Revisar seguridad | Sentry security alerts, dependabot en GitHub |

### Cuando escales a 10+ clientes

- [ ] Subir plan de LiveKit (Build → Scale) para mas agentes concurrentes
- [ ] Subir plan de Supabase si las conexiones se saturan
- [ ] Considerar Twilio Subaccounts para aislar clientes
- [ ] Implementar MercadoPago para clientes que no usan tarjeta
- [ ] Automatizar limpieza de grabaciones con lifecycle policy en R2

---

## 9. Datos importantes de tu infraestructura

### Identificadores clave

| Dato | Valor |
|------|-------|
| **LiveKit Project ID** | `2r172cwux9u` |
| **LiveKit SIP URI** | `sip:2r172cwux9u.sip.livekit.cloud;transport=tcp` |
| **LiveKit Agent ID** | `CA_cRCs5tbTho5A` |
| **Twilio SIP Trunk** | `ST_7rZEwfz7zMQ8` |
| **Supabase Project** | `tfecomyseybwlvmoypqh` (us-west-2) |
| **Railway Service** | `voiceai-production-f4e4.up.railway.app` |
| **Dashboard** | `agentes.innotecnia.app` (Cloudflare Pages) |
| **R2 Bucket** | `voiceai-recordings` |
| **Telefono Twilio** | +529994890531 |
| **Admin email** | sergio.sanchez.valle@gmail.com |

### Dominios y DNS (Cloudflare)

| Dominio | Apunta a | Proposito |
|---------|----------|-----------|
| `agentes.innotecnia.app` | Cloudflare Pages | Dashboard |
| API calls desde dashboard | `voiceai-production-f4e4.up.railway.app` | Backend |

---

## 10. Seguridad — Lo que debes saber

### Encriptacion

- Las API keys de clientes (BYOK) se encriptan con Fernet antes de guardar en DB
- La `ENCRYPTION_KEY` esta en Railway y LiveKit Cloud — **nunca la pierdas o no podras desencriptar**
- Los JWT de Supabase expiran en 1 hora

### Accesos criticos

- **Railway env vars**: Aqui estan TODAS las API keys. Protege tu cuenta de Railway con 2FA.
- **Supabase service key**: Acceso total a la base de datos. Solo esta en Railway env vars.
- **Stripe live keys**: Pueden hacer cobros reales. Solo en Railway.

### Que hacer si se compromete una API key

1. Revocar la key comprometida en el panel del proveedor
2. Generar una nueva
3. Actualizar en Railway → Environment Variables
4. Redesplegar: Railway lo hace automatico al cambiar env vars
5. Si es del agente (LiveKit), tambien actualizar con `lk agent deploy`

---

## 11. Limites y restricciones actuales

| Limite | Valor | Donde cambiarlo |
|--------|-------|-----------------|
| Llamadas outbound por cliente/dia | 200 | Env var `OUTBOUND_DAILY_LIMIT` |
| Rate limit API | 120 req/min por cliente | Codigo (`api/middleware.py`) |
| Duracion maxima de llamada | 300 seg (5 min) | Env var `DEFAULT_MAX_CALL_DURATION` |
| Timeout sesion WhatsApp | 30 min | Campo `session_timeout_minutes` en DB |
| Agentes concurrentes (LiveKit) | 1 (plan Build) | Upgrade a plan Scale |
| Archivo de voz clonada max | 30 MB | Codigo (`api/routes/voice_cloning.py`) |
| MCP servers por agente | Sin limite hard | Depende de latencia |

---

## 12. Proximos pasos recomendados

### Corto plazo (este mes)

1. **Estabilizar primer cliente** — Monitorear de cerca al doctor en Merida
2. **Configurar alertas de saldo** en Twilio, Deepgram, Cartesia
3. **Probar flujo completo de pago** — Comprar creditos con tarjeta real via Stripe

### Mediano plazo (1-3 meses)

4. **MercadoPago** — Para clientes que quieran pagar con OXXO/SPEI
5. **Segundo/tercer cliente** — Validar que el multi-tenant funciona bien
6. **Simli Avatar** — Diferenciador visual para widgets ($10/mo por 1,000 min)

### Largo plazo (3-6 meses)

7. **BYOT (Bring Your Own Twilio)** — Clientes conectan su propia cuenta
8. **Twilio Subaccounts** — Aislar clientes para proteger tu cuenta principal
9. **Multi-region** — Si consigues clientes fuera de Mexico
