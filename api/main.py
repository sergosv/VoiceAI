"""FastAPI app principal — API + dashboard estático."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
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

# ── Validación de variables de entorno requeridas ──────────────────
_REQUIRED_ENV = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_ANON_KEY",
    "GOOGLE_API_KEY",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
]
_missing = [v for v in _REQUIRED_ENV if not os.environ.get(v)]
if _missing:
    raise RuntimeError(
        f"Variables de entorno requeridas no configuradas: {', '.join(_missing)}. "
        f"Configúralas en Railway o en .env antes de iniciar."
    )

# Sentry — error tracking & performance monitoring
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=os.environ.get("SENTRY_ENV", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.2")),
        profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_RATE", "0.1")),
        send_default_pii=False,
        release=f"voiceai-api@{os.environ.get('RAILWAY_GIT_COMMIT_SHA', 'dev')[:8]}",
    )

# Configurar logging estructurado (JSON en producción)
setup_logging(json_format=os.environ.get("LOG_FORMAT") == "json")

from api.routes import (
    admin, agents, ai, analytics, api_integrations, api_keys, auth, billing, calls, campaigns,
    chat, clients, contacts, conversation_results, appointments, costs, dashboard,
    documents, evaluations, evolution, flow_builder, ghl, looptalk, mcp, proactive,
    templates, v1, voices, webhook_management, webhooks, whatsapp, whatsapp_webhooks,
    widget,
)
from api.services.chat_store import start_cleanup_loop
from api.services.conversation_cleanup import start_conversation_cleanup
from api.services.proactive_worker import start_proactive_worker
from api.services.call_evaluator import start_evaluation_worker
from api.tasks.credit_alerts import start_credit_alert_worker

def _rate_limit_key(request: Request) -> str:
    """Key function: usa client_id del JWT si existe, sino IP."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            import jwt as _jwt
            payload = _jwt.decode(auth[7:], options={"verify_signature": False})
            sub = payload.get("sub", "")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass
    return get_remote_address(request)


# Rate limiter — per-client cuando hay JWT, per-IP cuando no
limiter = Limiter(key_func=_rate_limit_key, default_limits=["120/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown: inicia workers background."""
    start_cleanup_loop()
    start_proactive_worker()
    start_conversation_cleanup()
    start_evaluation_worker()
    start_credit_alert_worker()
    yield


app = FastAPI(
    title="Voice AI Platform",
    version="0.3.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
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
    rf"https://[a-f0-9]+\.{_cf_pages_domain.replace('.', r'\.')}"
    if _cf_pages_domain
    else r"https://[a-f0-9]+\.voiceai-69f\.pages\.dev"
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


# CORS abierto para endpoints del widget (públicos, protegidos por rate limit)
@app.middleware("http")
async def widget_cors_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Permite CORS abierto solo para /api/widget/* (embeddable en cualquier dominio)."""
    if request.url.path.startswith("/api/widget"):
        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Max-Age": "86400",
                },
            )
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response
    return await call_next(request)


# Inyectar versión en todas las respuestas
@app.middleware("http")
async def add_version_header(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers["X-API-Version"] = app.version
    return response


# Health check
@app.get("/api/health")
async def health_check() -> dict:
    try:
        from agent.circuit_breaker import get_all_circuits
        circuits = get_all_circuits()
    except Exception:
        circuits = {}
    return {
        "status": "ok",
        "service": "voice-ai-platform",
        "version": app.version,
        "circuits": circuits,
    }


@app.get("/api/admin/provider-health")
async def provider_health() -> dict:
    """Estado de salud de providers externos basado en llamadas recientes."""
    from api.deps import get_supabase as _get_sb

    sb = _get_sb()

    # Últimas 200 llamadas para analizar tasa de éxito por provider
    calls = (
        sb.table("calls")
        .select("status, metadata, started_at, duration_seconds")
        .order("started_at", desc=True)
        .limit(200)
        .execute()
    )

    # Agrupar por provider
    providers: dict[str, dict] = {}
    for row in calls.data or []:
        meta = row.get("metadata") or {}
        for key in ("stt_provider", "llm_provider", "tts_provider"):
            prov = meta.get(key)
            if not prov:
                continue
            component = key.replace("_provider", "").upper()
            label = f"{component}/{prov}"
            if label not in providers:
                providers[label] = {
                    "component": component,
                    "provider": prov,
                    "total_calls": 0,
                    "successful": 0,
                    "failed": 0,
                    "last_seen": None,
                }
            p = providers[label]
            p["total_calls"] += 1
            if row.get("status") == "completed":
                p["successful"] += 1
            else:
                p["failed"] += 1
            if not p["last_seen"] or (row.get("started_at") or "") > p["last_seen"]:
                p["last_seen"] = row.get("started_at")

    # Calcular health score y status
    for label, p in providers.items():
        total = p["total_calls"]
        if total == 0:
            p["health"] = "unknown"
            p["success_rate"] = 0
        else:
            rate = p["successful"] / total
            p["success_rate"] = round(rate * 100, 1)
            if rate >= 0.95:
                p["health"] = "healthy"
            elif rate >= 0.8:
                p["health"] = "degraded"
            else:
                p["health"] = "critical"

    # Circuit breaker state (si está disponible en este proceso)
    try:
        from agent.circuit_breaker import get_all_circuits
        circuits = get_all_circuits()
    except Exception:
        circuits = {}

    # Fallback chains
    try:
        from agent.circuit_breaker import FALLBACK_CHAINS
        fallbacks = {k: dict(v) for k, v in FALLBACK_CHAINS.items()}
    except Exception:
        fallbacks = {}

    return {
        "providers": list(providers.values()),
        "circuits": circuits,
        "fallback_chains": fallbacks,
        "total_calls_analyzed": len(calls.data or []),
    }


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


@app.get("/chat-widget.js")
async def serve_chat_widget_js() -> Response:
    widget_path = Path(__file__).parent.parent / "dashboard" / "dist" / "chat-widget.js"
    if not widget_path.exists():
        widget_path = Path(__file__).parent.parent / "dashboard" / "public" / "chat-widget.js"
    if not widget_path.exists():
        return Response(content="// chat widget not found", media_type="application/javascript")
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
app.include_router(whatsapp_webhooks.ghl_router, prefix="/api/webhooks/gohighlevel", tags=["ghl-webhooks"])
app.include_router(ghl.router, prefix="/api/clients", tags=["ghl"])
app.include_router(ghl.inbox_router, prefix="/api/ghl", tags=["ghl-inbox"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(widget.router, prefix="/api/widget", tags=["widget"])
app.include_router(looptalk.router, prefix="/api/looptalk", tags=["looptalk"])
app.include_router(proactive.router, prefix="/api/proactive", tags=["proactive"])
app.include_router(evaluations.router, prefix="/api/evaluations", tags=["evaluations"])
app.include_router(conversation_results.router, prefix="/api", tags=["conversation-results"])
app.include_router(api_keys.router, prefix="/api", tags=["api-keys"])
app.include_router(webhook_management.router, prefix="/api", tags=["webhook-management"])
app.include_router(flow_builder.router, prefix="/api/clients", tags=["flow-versions"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(v1.router, prefix="/api", tags=["public-api-v1"])

# Dashboard React (build estático) — solo si existe el directorio dist
dashboard_dir = Path(__file__).parent.parent / "dashboard" / "dist"
if dashboard_dir.exists():
    # Servir archivos estáticos (JS, CSS, assets)
    app.mount("/assets", StaticFiles(directory=str(dashboard_dir / "assets")), name="assets")

    # SPA catch-all: cualquier ruta no-API sirve index.html
    @app.get("/{path:path}")
    async def spa_fallback(request: Request, path: str) -> FileResponse:
        # Si el archivo existe en dist, servirlo directamente (con path containment check)
        file_path = (dashboard_dir / path).resolve()
        if file_path.is_file() and file_path.is_relative_to(dashboard_dir.resolve()):
            return FileResponse(str(file_path))
        # Cualquier otra ruta → index.html (React Router maneja el routing)
        return FileResponse(str(dashboard_dir / "index.html"))
