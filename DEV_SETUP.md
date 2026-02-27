# Voice AI Platform — Setup de Desarrollo Local

## Requisitos Previos

- **Python 3.13** (3.14 NO compatible con livekit-agents)
- **Node.js 22+**
- **Git**

## 1. Clonar y configurar entorno

```bash
cd C:\Claude\VoiceAI

# Crear virtualenv (solo la primera vez)
python -m venv venv

# Activar virtualenv
venv\Scripts\activate        # Windows CMD
source venv/Scripts/activate  # Git Bash

# Instalar dependencias Python
pip install -r requirements.txt
```

## 2. Variables de entorno

Copiar `.env.example` a `.env` y llenar los valores:

```bash
cp .env.example .env
```

El frontend tiene su propio `.env` en `dashboard/.env`:

```
VITE_SUPABASE_URL=https://tfecomyseybwlvmoypqh.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...  (la anon key de Supabase)
```

## 3. Levantar servicios para desarrollo

Se necesitan **2 terminales** para desarrollo local:

### Terminal 1 — Backend API (FastAPI)

```bash
cd C:\Claude\VoiceAI
venv\Scripts\activate
uvicorn api.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/api/docs
- Health check: http://localhost:8000/api/health

### Terminal 2 — Frontend Dashboard (Vite + React)

```bash
cd C:\Claude\VoiceAI\dashboard
npm install   # solo la primera vez
npm run dev
```

- Dashboard: http://localhost:5173
- El proxy de Vite redirige `/api/*` → `http://localhost:8000`

### (Opcional) Terminal 3 — Agente de Voz (LiveKit)

Solo necesario si estás probando llamadas telefónicas:

```bash
cd C:\Claude\VoiceAI
venv\Scripts\activate
python -m agent.main dev
```

## 4. Credenciales del Admin

- **Email**: sergio.sanchez.valle@gmail.com
- **Password**: Innotecnia.2025*
- **Rol**: admin

## 5. Tests

```bash
cd C:\Claude\VoiceAI
venv\Scripts\activate
pytest tests/ -v
```

## 6. Build de producción

El dashboard se compila y FastAPI lo sirve como archivos estáticos:

```bash
cd C:\Claude\VoiceAI\dashboard
npm run build    # genera dashboard/dist/
```

Luego el backend sirve todo desde un solo puerto:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## 7. Deploy

| Servicio | Plataforma | Comando/Config |
|----------|-----------|----------------|
| **API + Dashboard** | Railway | `Dockerfile.railway` (multi-stage Node + Python) |
| **Agente de voz** | LiveKit Cloud | `lk agent deploy` (usa `Dockerfile` + `livekit.toml`) |

## Puertos

| Servicio | Puerto | URL |
|----------|--------|-----|
| FastAPI (backend) | 8000 | http://localhost:8000 |
| Vite (frontend dev) | 5173 | http://localhost:5173 |
| LiveKit Agent | — | Se conecta a LiveKit Cloud via WebSocket |
