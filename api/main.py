"""FastAPI app principal — API + dashboard estático."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from api.routes import (
    agents, ai, api_integrations, auth, billing, calls, campaigns, chat,
    clients, contacts, appointments, costs, dashboard, documents, mcp,
    voices, webhooks, whatsapp, whatsapp_webhooks,
)
from api.services.chat_store import start_cleanup_loop

app = FastAPI(
    title="Voice AI Platform",
    version="0.2.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# CORS — localhost para dev, ALLOWED_ORIGINS para producción
_origins = [
    "http://localhost:5173",
    "http://localhost:8000",
]
_extra = os.environ.get("ALLOWED_ORIGINS", "")
if _extra:
    _origins.extend(o.strip() for o in _extra.split(",") if o.strip())
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "voice-ai-platform"}


# Rutas API
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(voices.router, prefix="/api/voices", tags=["voices"])
app.include_router(clients.router, prefix="/api/clients", tags=["clients"])
app.include_router(agents.router, prefix="/api/clients", tags=["agents"])
app.include_router(calls.router, prefix="/api/calls", tags=["calls"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["contacts"])
app.include_router(appointments.router, prefix="/api/appointments", tags=["appointments"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(costs.router, prefix="/api/costs", tags=["costs"])
app.include_router(billing.router, prefix="/api/billing", tags=["billing"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(mcp.router, prefix="/api/clients", tags=["mcp"])
app.include_router(mcp.templates_router, prefix="/api", tags=["mcp-templates"])
app.include_router(api_integrations.router, prefix="/api/clients", tags=["api-integrations"])
app.include_router(whatsapp.router, prefix="/api/clients", tags=["whatsapp"])
app.include_router(whatsapp.inbox_router, prefix="/api/whatsapp", tags=["whatsapp-inbox"])
app.include_router(whatsapp_webhooks.router, prefix="/api/webhooks/whatsapp", tags=["whatsapp-webhooks"])

@app.on_event("startup")
async def startup_chat_cleanup() -> None:
    """Inicia el loop de limpieza de conversaciones de chat."""
    start_cleanup_loop()


# Dashboard React (build estático) — solo si existe el directorio dist
dashboard_dir = Path(__file__).parent.parent / "dashboard" / "dist"
if dashboard_dir.exists():
    # Servir archivos estáticos (JS, CSS, assets)
    app.mount("/assets", StaticFiles(directory=str(dashboard_dir / "assets")), name="assets")

    # SPA catch-all: cualquier ruta no-API sirve index.html
    @app.get("/{path:path}")
    async def spa_fallback(request: Request, path: str) -> FileResponse:
        # Si el archivo existe en dist, servirlo directamente
        file_path = dashboard_dir / path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # Cualquier otra ruta → index.html (React Router maneja el routing)
        return FileResponse(str(dashboard_dir / "index.html"))
