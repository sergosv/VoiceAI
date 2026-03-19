# Guia Rapida del Desarrollador — VoiceAI Platform

> Cómo levantar todo el entorno local desde cero.
> Para Windows con Warp terminal.

---

## Requisitos previos

- Python 3.12+ instalado
- Node.js 18+ instalado
- Git configurado con acceso a `github.com/sergosv/VoiceAI`
- LiveKit CLI (`lk`) instalado: `winget install LiveKit.LiveKitCLI`
- Archivo `.env` en la raíz del proyecto (pedir a Sergio si no lo tienes)

---

## 1. Clonar y preparar

```bash
# Solo la primera vez
git clone https://github.com/sergosv/VoiceAI.git C:\Claude\VoiceAI
cd C:\Claude\VoiceAI

# Crear virtualenv (solo la primera vez)
python -m venv venv
```

---

## 2. Levantar el entorno — 3 terminales

### Terminal 1: API (FastAPI)

```bash
cd C:\Claude\VoiceAI

# Activar virtualenv
source venv/Scripts/activate    # bash/zsh en Warp
# o: .\venv\Scripts\activate   # PowerShell

# Instalar dependencias (solo si cambiaron)
pip install -r requirements.txt

# Cargar variables de entorno
source .env    # bash
# o: Get-Content .env | ForEach-Object { if ($_ -match '^([^#].+?)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }  # PowerShell

# Arrancar API
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

La API queda en: `http://localhost:8000`
Swagger docs: `http://localhost:8000/docs`
Health check: `http://localhost:8000/api/health`

### Terminal 2: Dashboard (React + Vite)

```bash
cd C:\Claude\VoiceAI\dashboard

# Instalar dependencias (solo si cambiaron)
npm install

# Arrancar dev server
npm run dev
```

El dashboard queda en: `http://localhost:5173`

> El dashboard apunta a la API local automáticamente (`.env` en dashboard/).
> Para apuntar a producción, editar `dashboard/.env` y cambiar `VITE_API_URL`.

### Terminal 3: Agente de voz (LiveKit — solo si necesitas probar llamadas)

```bash
cd C:\Claude\VoiceAI

source venv/Scripts/activate
source .env

# Correr agente localmente
python -m agent.main start
```

> El agente local se conecta a LiveKit Cloud. Para recibir llamadas reales
> necesitas que el SIP trunk apunte a tu agente (solo funciona con `lk agent deploy`).

---

## 3. Comandos frecuentes

### Correr tests
```bash
cd C:\Claude\VoiceAI
source venv/Scripts/activate

# Todos los tests
pytest

# Solo tests de regresión
pytest tests/test_evolution_lid.py tests/test_phone_normalization.py tests/test_whatsapp_regression.py tests/test_agent_save_regression.py

# Un test específico
pytest tests/test_phone_normalization.py -v

# Con output detallado
pytest -v --tb=short
```

### Deploy a producción

```bash
# API + Dashboard → Railway (automático con push)
git push origin master

# Agente de voz → LiveKit Cloud (manual)
cd C:\Claude\VoiceAI
lk agent deploy
```

### Migraciones de base de datos

```bash
# Opción 1: Supabase Dashboard → SQL Editor → pegar SQL
# Opción 2: psql directo
psql -U postgres.tfecomyseybwlvmoypqh \
  -h db.tfecomyseybwlvmoypqh.supabase.co \
  -d postgres \
  -f db/migrations/NNN_description.sql
```

### Build del dashboard para producción

```bash
cd C:\Claude\VoiceAI\dashboard
npm run build
# Output en dashboard/dist/ — servido por FastAPI como StaticFiles
```

---

## 4. Estructura de terminales en Warp

Recomendación: crear un layout con 3 paneles:

```
┌──────────────────────────────────────────┐
│  Terminal 1: API (uvicorn --reload)      │
├─────────────────────┬────────────────────┤
│  Terminal 2:        │  Terminal 3:       │
│  Dashboard (vite)   │  Agent / Tests     │
└─────────────────────┴────────────────────┘
```

---

## 5. Variables de entorno clave

El archivo `.env` en la raíz tiene TODAS las variables. Las más importantes:

| Variable | Para qué |
|----------|----------|
| `SUPABASE_URL` | Conexión a base de datos |
| `SUPABASE_SERVICE_KEY` | Auth de servicio (acceso total) |
| `GOOGLE_API_KEY` | Gemini (LLM + RAG) |
| `DEEPGRAM_API_KEY` | Speech-to-Text |
| `CARTESIA_API_KEY` | Text-to-Speech |
| `LIVEKIT_URL` | Servidor de audio/video |
| `LIVEKIT_API_KEY` / `SECRET` | Auth LiveKit |
| `TWILIO_ACCOUNT_SID` / `AUTH_TOKEN` | Telefonía SIP |
| `ENCRYPTION_KEY` | Encriptación de API keys de clientes |
| `STRIPE_SECRET_KEY` | Pagos (producción) |

> NUNCA commitear `.env` al repo. Ya está en `.gitignore`.

---

## 6. Archivos importantes que debes conocer

| Archivo | Qué es |
|---------|--------|
| `agent/main.py` | Entrypoint del agente de voz (LiveKit) |
| `api/main.py` | Entrypoint de la API (FastAPI) |
| `api/routes/*.py` | Endpoints de la API |
| `api/services/*.py` | Lógica de negocio |
| `agent/config_loader.py` | Carga config de agentes desde DB |
| `agent/phone_utils.py` | Normalización de teléfonos |
| `db/migrations/*.sql` | Migraciones de DB (001-042) |
| `dashboard/src/` | Frontend React |
| `Dockerfile` | Docker del agente (LiveKit Cloud) |
| `Dockerfile.railway` | Docker de API+Dashboard (Railway) |
| `livekit.toml` | Config de LiveKit agent |
| `CLAUDE.md` | Instrucciones para Claude Code |
| `ARCHITECTURE.md` | Diseño completo del sistema |
| `docs/OPERATIONS_MANUAL.md` | Manual de operaciones (admin) |

---

## 7. Troubleshooting local

### "Module not found" al correr API o agent
```bash
# Verificar que el virtualenv está activo
which python    # Debe mostrar .../venv/Scripts/python
pip install -r requirements.txt
```

### "CORS error" en el dashboard
- Verificar que la API corre en puerto 8000
- Verificar `VITE_API_URL` en `dashboard/.env`

### "Connection refused" en LiveKit
- Verificar `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` en `.env`

### Tests fallan por "No module named sentry_sdk"
- Normal en local — instalar: `pip install sentry-sdk`
- O ignorar: los tests que lo necesitan hacen mock automático

### uvicorn no arranca
- Verificar que puerto 8000 no está ocupado: `netstat -ano | findstr 8000`
- Matar proceso: `taskkill /PID <pid> /F`

### npm run dev falla
- `cd dashboard && rm -rf node_modules && npm install`

---

## 8. Flujo de trabajo diario

```
1. git pull origin master              ← traer cambios
2. Levantar 3 terminales (ver sección 2)
3. Hacer cambios
4. pytest                              ← verificar que no rompiste nada
5. git add + git commit + git push     ← deploy automático a Railway
6. lk agent deploy                     ← solo si tocaste código del agente
```
