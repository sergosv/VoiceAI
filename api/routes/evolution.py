"""Rutas para conectar/desconectar Evolution API desde el dashboard.

Flujo: crear instancia -> obtener QR -> escanear -> auto-configurar webhook.
Credenciales de Evolution API vienen de env vars (EVO_API_URL, EVO_API_KEY).
"""

from __future__ import annotations

import logging
import os
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client

from api.middleware.auth import CurrentUser, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _check_client(user: CurrentUser, client_id: str) -> None:
    if user.role != "admin" and user.client_id != client_id:
        raise HTTPException(403, "No autorizado para este cliente")


def _get_evo_credentials() -> tuple[str, str]:
    """Obtiene credenciales de Evolution API de env vars."""
    api_url = os.environ.get("EVO_API_URL", "")
    api_key = os.environ.get("EVO_API_KEY", "")
    if not api_url or not api_key:
        raise HTTPException(500, "Evolution API no configurada en el servidor (EVO_API_URL, EVO_API_KEY)")
    return api_url.rstrip("/"), api_key


# ── Schemas ─────────────────────────────────────────────


class ConnectRequest(BaseModel):
    """Datos opcionales para crear instancia."""
    instance_name: str | None = None


class ConnectResponse(BaseModel):
    qr_code: str | None = None
    instance_name: str = ""
    status: str = ""


class StatusResponse(BaseModel):
    connected: bool = False
    instance_name: str = ""
    phone_number: str | None = None
    profile_name: str | None = None
    profile_pic_url: str | None = None
    status: str = ""


class DisconnectResponse(BaseModel):
    message: str = ""


# ── Helper — HTTP client para Evolution ─────────────────


async def _evo_request(
    method: str,
    api_url: str,
    api_key: str,
    path: str,
    json: dict | None = None,
    timeout: float = 20,
) -> dict:
    """Hace request a Evolution API con manejo de errores."""
    url = f"{api_url}{path}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "POST":
                resp = await client.post(url, json=json or {}, headers=headers)
            elif method == "PUT":
                resp = await client.put(url, json=json or {}, headers=headers)
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Method no soportado: {method}")

            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:500] if e.response else str(e)
            logger.error("Evolution %s %s -> %s: %s", method, path, e.response.status_code, detail)
            raise HTTPException(e.response.status_code, f"Evolution API: {detail}")
        except httpx.TimeoutException:
            raise HTTPException(504, "Evolution API timeout")
        except httpx.ConnectError:
            raise HTTPException(502, "No se pudo conectar a Evolution API")


def _get_webhook_url() -> str:
    """Construye la webhook URL del servidor."""
    base = os.environ.get("API_BASE_URL", "")
    if not base:
        railway = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
        base = f"https://{railway}" if railway else "http://localhost:8000"
    return f"{base}/api/webhooks/whatsapp/evolution"


# ── Endpoints ───────────────────────────────────────────


@router.post(
    "/{client_id}/agents/{agent_id}/whatsapp/evolution/connect",
    response_model=ConnectResponse,
)
async def connect_evolution(
    client_id: str,
    agent_id: str,
    body: ConnectRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ConnectResponse:
    """Crea instancia en Evolution API y retorna QR code base64."""
    _check_client(user, client_id)
    api_url, api_key = _get_evo_credentials()
    sb = _sb()

    # Generar nombre legible: nombre del agente o fallback a ID
    instance_name = body.instance_name
    if not instance_name:
        agent_row = sb.table("agents").select("name").eq("id", agent_id).limit(1).execute()
        if agent_row.data and agent_row.data[0].get("name"):
            # Sanitizar: lowercase, sin espacios, sin caracteres especiales
            import re
            raw = agent_row.data[0]["name"].lower().strip()
            instance_name = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")[:30]
        else:
            instance_name = f"voiceai-{agent_id[:8]}"

    # 1. Crear instancia (si ya existe, obtener QR)
    try:
        create_data = await _evo_request("POST", api_url, api_key, "/instance/create", {
            "instanceName": instance_name,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
        })
    except HTTPException as e:
        if e.status_code == 409:
            logger.info("Instancia %s ya existe, obteniendo QR...", instance_name)
            create_data = {}
        else:
            raise

    # 2. Extraer QR
    qr_code = None
    if create_data.get("qrcode", {}).get("base64"):
        qr_code = create_data["qrcode"]["base64"]
    else:
        try:
            qr_data = await _evo_request("GET", api_url, api_key, f"/instance/connect/{instance_name}")
            qr_code = qr_data.get("base64") or qr_data.get("qrcode", {}).get("base64")
        except HTTPException:
            logger.warning("No se pudo obtener QR para %s", instance_name)

    # 3. Auto-configurar webhook
    webhook_url = _get_webhook_url()
    try:
        await _evo_request("POST", api_url, api_key, f"/webhook/set/{instance_name}", {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "webhookByEvents": False,
                "webhookBase64": True,
                "events": ["MESSAGES_UPSERT"],
            }
        })
        logger.info("Webhook configurado: %s", webhook_url)
    except HTTPException as e:
        logger.warning("No se pudo configurar webhook: %s", e.detail)

    # 4. Settings de instancia
    try:
        await _evo_request("POST", api_url, api_key, f"/settings/set/{instance_name}", {
            "rejectCall": False,
            "groupsIgnore": True,
            "alwaysOnline": False,
            "readMessages": False,
            "readStatus": False,
            "syncFullHistory": False,
        })
    except HTTPException:
        pass

    # 5. Guardar/actualizar config en DB (credenciales del server, no del cliente)
    existing = (
        sb.table("whatsapp_configs")
        .select("id")
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )

    config_data = {
        "provider": "evolution",
        "evo_instance_id": instance_name,
        "evo_api_url": api_url,
        "evo_api_key": api_key,
        "is_active": True,
    }

    if existing.data:
        sb.table("whatsapp_configs").update(config_data).eq("agent_id", agent_id).execute()
    else:
        config_data.update({
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "agent_id": agent_id,
        })
        sb.table("whatsapp_configs").insert(config_data).execute()

    return ConnectResponse(
        qr_code=qr_code,
        instance_name=instance_name,
        status="qr_ready" if qr_code else "pending",
    )


@router.get(
    "/{client_id}/agents/{agent_id}/whatsapp/evolution/status",
    response_model=StatusResponse,
)
async def get_evolution_status(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> StatusResponse:
    """Verifica el estado de conexión de la instancia."""
    _check_client(user, client_id)
    sb = _sb()

    result = (
        sb.table("whatsapp_configs")
        .select("*")
        .eq("agent_id", agent_id)
        .eq("provider", "evolution")
        .limit(1)
        .execute()
    )
    if not result.data:
        return StatusResponse(status="not_configured")

    cfg = result.data[0]
    api_url = cfg.get("evo_api_url", "")
    api_key = cfg.get("evo_api_key", "")
    instance_name = cfg.get("evo_instance_id", "")

    if not all([api_url, api_key, instance_name]):
        return StatusResponse(status="not_configured")

    try:
        data = await _evo_request(
            "GET", api_url, api_key, f"/instance/connectionState/{instance_name}"
        )
    except HTTPException:
        return StatusResponse(status="error", instance_name=instance_name)

    # connectionState puede devolver {instance: {state: "open"}} o {state: "open"}
    state = (
        data.get("state")
        or data.get("instance", {}).get("state", "")
    )
    connected = state == "open"

    phone_number = None
    profile_name = None
    profile_pic_url = None

    if connected:
        try:
            info = await _evo_request(
                "GET", api_url, api_key, "/instance/fetchInstances"
            )
            # Evolution v2: lista de objetos con campos en raíz (name, connectionStatus, ownerJid, etc.)
            for inst in (info if isinstance(info, list) else [info]):
                inst_name = inst.get("name") or inst.get("instance", {}).get("instanceName", "")
                if inst_name == instance_name:
                    owner_jid = inst.get("ownerJid") or inst.get("instance", {}).get("owner", "")
                    if owner_jid:
                        phone_number = owner_jid.split("@")[0] if "@" in owner_jid else owner_jid
                    profile_name = inst.get("profileName") or inst.get("instance", {}).get("profileName")
                    profile_pic_url = inst.get("profilePicUrl") or inst.get("instance", {}).get("profilePicUrl")
                    break
        except HTTPException:
            pass

        # Auto-guardar número en DB
        if phone_number and not cfg.get("phone_number"):
            sb.table("whatsapp_configs").update({
                "phone_number": f"+{phone_number}",
            }).eq("id", cfg["id"]).execute()

    return StatusResponse(
        connected=connected,
        instance_name=instance_name,
        phone_number=phone_number,
        profile_name=profile_name,
        profile_pic_url=profile_pic_url,
        status=state,
    )


@router.get(
    "/{client_id}/agents/{agent_id}/whatsapp/evolution/qr",
    response_model=ConnectResponse,
)
async def get_evolution_qr(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ConnectResponse:
    """Obtiene un nuevo QR para instancia existente."""
    _check_client(user, client_id)
    sb = _sb()

    result = (
        sb.table("whatsapp_configs")
        .select("*")
        .eq("agent_id", agent_id)
        .eq("provider", "evolution")
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Config no encontrada")

    cfg = result.data[0]
    api_url = cfg["evo_api_url"]
    api_key = cfg["evo_api_key"]
    instance_name = cfg["evo_instance_id"]

    qr_data = await _evo_request(
        "GET", api_url, api_key, f"/instance/connect/{instance_name}"
    )
    qr_code = qr_data.get("base64") or qr_data.get("qrcode", {}).get("base64")

    return ConnectResponse(
        qr_code=qr_code,
        instance_name=instance_name,
        status="qr_ready" if qr_code else "already_connected",
    )


@router.post(
    "/{client_id}/agents/{agent_id}/whatsapp/evolution/disconnect",
    response_model=DisconnectResponse,
)
async def disconnect_evolution(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> DisconnectResponse:
    """Desconecta y elimina instancia de Evolution API."""
    _check_client(user, client_id)
    api_url, api_key = _get_evo_credentials()
    sb = _sb()

    result = (
        sb.table("whatsapp_configs")
        .select("*")
        .eq("agent_id", agent_id)
        .eq("provider", "evolution")
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Config no encontrada")

    cfg = result.data[0]
    instance_name = cfg["evo_instance_id"]

    # Logout + eliminar instancia en Evolution
    try:
        await _evo_request("DELETE", api_url, api_key, f"/instance/logout/{instance_name}")
    except HTTPException:
        pass
    try:
        await _evo_request("DELETE", api_url, api_key, f"/instance/delete/{instance_name}")
    except HTTPException:
        pass

    # Limpiar DB
    sb.table("whatsapp_configs").delete().eq("id", cfg["id"]).execute()

    return DisconnectResponse(message="WhatsApp desconectado")


@router.post(
    "/{client_id}/agents/{agent_id}/whatsapp/evolution/restart",
    response_model=StatusResponse,
)
async def restart_evolution(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> StatusResponse:
    """Reinicia la instancia (útil si se desconectó)."""
    _check_client(user, client_id)
    sb = _sb()

    result = (
        sb.table("whatsapp_configs")
        .select("*")
        .eq("agent_id", agent_id)
        .eq("provider", "evolution")
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Config no encontrada")

    cfg = result.data[0]
    try:
        await _evo_request(
            "PUT", cfg["evo_api_url"], cfg["evo_api_key"],
            f"/instance/restart/{cfg['evo_instance_id']}"
        )
    except HTTPException:
        pass

    return await get_evolution_status(client_id, agent_id, user)
