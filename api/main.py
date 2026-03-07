"""FastAPI app principal — API + dashboard estático."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.logging_config import RequestIdMiddleware, setup_logging

load_dotenv()

# Configurar logging estructurado (JSON en producción)
setup_logging(json_format=os.environ.get("LOG_FORMAT") == "json")

from api.routes import (
    agents, ai, analytics, api_integrations, auth, billing, calls, campaigns, chat,
    clients, contacts, appointments, costs, dashboard, documents, evolution,
    looptalk, mcp, proactive, templates, voices, webhooks, whatsapp, whatsapp_webhooks, widget,
)
from api.services.chat_store import start_cleanup_loop
from api.services.proactive_worker import start_proactive_worker

# Rate limiter global
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(
    title="Voice AI Platform",
    version="0.3.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiadas solicitudes. Intenta de nuevo en un momento."},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

# CORS — localhost para dev, ALLOWED_ORIGINS para producción
_origins = [
    "http://localhost:5173",
    "http://localhost:8000",
]
_extra = os.environ.get("ALLOWED_ORIGINS", "")
if _extra:
    _origins.extend(o.strip() for o in _extra.split(",") if o.strip())

# Cloudflare Pages: aceptar deployment-specific URLs (hash.project.pages.dev)
_cf_pages_domain = os.environ.get("CF_PAGES_DOMAIN", "")

_cf_regex = (
    rf"https://.*\.{_cf_pages_domain.replace('.', r'\.')}"
    if _cf_pages_domain
    else r"https://.*\.voiceai-69f\.pages\.dev"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=_cf_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "X-Request-ID"],
)

# Correlation ID middleware (genera request_id por petición)
app.add_middleware(RequestIdMiddleware)


# Inyectar versión en todas las respuestas
@app.middleware("http")
async def add_version_header(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers["X-API-Version"] = app.version
    return response


# Health check
@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "voice-ai-platform", "version": app.version}


# Widget JS — servido con CORS abierto para embeber en sitios externos
@app.get("/widget.js")
async def serve_widget_js() -> Response:
    widget_path = Path(__file__).parent.parent / "dashboard" / "dist" / "widget.js"
    if not widget_path.exists():
        widget_path = Path(__file__).parent.parent / "dashboard" / "public" / "widget.js"
    if not widget_path.exists():
        return Response(content="// widget not found", media_type="application/javascript")
    content = widget_path.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="application/javascript",
        headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=3600"},
    )


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
app.include_router(evolution.router, prefix="/api/clients", tags=["evolution"])
app.include_router(whatsapp.inbox_router, prefix="/api/whatsapp", tags=["whatsapp-inbox"])
app.include_router(whatsapp_webhooks.router, prefix="/api/webhooks/whatsapp", tags=["whatsapp-webhooks"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(widget.router, prefix="/api/widget", tags=["widget"])
app.include_router(looptalk.router, prefix="/api/looptalk", tags=["looptalk"])
app.include_router(proactive.router, prefix="/api/proactive", tags=["proactive"])

@app.on_event("startup")
async def startup_background_tasks() -> None:
    """Inicia workers background: chat cleanup + proactive scheduler."""
    start_cleanup_loop()
    start_proactive_worker()


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
