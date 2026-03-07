"""Rutas de LoopTalk: test personas, ejecución de tests y suites de prueba."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.services.looptalk_service import generate_personas, run_test

logger = logging.getLogger("looptalk")
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────


class PersonaCreateRequest(BaseModel):
    """Crea una persona de prueba."""
    name: str
    personality: str
    objective: str
    success_criteria: list[str] | None = None
    curveballs: list[str] | None = None
    difficulty: str = "medium"
    language: str = "es"
    tags: list[str] | None = None


class PersonaUpdateRequest(BaseModel):
    """Actualiza una persona de prueba."""
    name: str | None = None
    personality: str | None = None
    objective: str | None = None
    success_criteria: list[str] | None = None
    curveballs: list[str] | None = None
    difficulty: str | None = None
    language: str | None = None
    tags: list[str] | None = None


class GeneratePersonasRequest(BaseModel):
    """Solicitud para generar personas con IA."""
    description: str
    count: int = Field(default=5, ge=1, le=20)
    language: str = "es"


class RunRequest(BaseModel):
    """Inicia un test run."""
    agent_id: str
    persona_id: str
    max_turns: int = Field(default=20, ge=2, le=100)


class BatchRunRequest(BaseModel):
    """Inicia múltiples test runs."""
    agent_id: str
    persona_ids: list[str]
    max_turns: int = Field(default=20, ge=2, le=100)


class SuiteCreateRequest(BaseModel):
    """Crea una suite de pruebas."""
    name: str
    description: str | None = None
    persona_ids: list[str] = Field(default_factory=list)
    max_turns: int = Field(default=20, ge=2, le=100)


class SuiteUpdateRequest(BaseModel):
    """Actualiza una suite de pruebas."""
    name: str | None = None
    description: str | None = None
    persona_ids: list[str] | None = None
    max_turns: int | None = None


class SuiteRunRequest(BaseModel):
    """Ejecuta una suite contra un agente."""
    agent_id: str


# ── Helpers ──────────────────────────────────────────────


def _resolve_client_id(user: CurrentUser, explicit_client_id: str | None = None) -> str | None:
    """Resuelve el client_id efectivo según el rol."""
    if user.role == "client":
        return user.client_id
    return explicit_client_id


def _check_own_persona(persona: dict, user: CurrentUser) -> None:
    """Verifica que la persona no sea template y pertenezca al usuario."""
    if persona.get("is_template"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No se pueden modificar personas template",
        )
    if user.role == "client" and persona.get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )


# ══════════════════════════════════════════════════════════
#  PERSONAS CRUD
# ══════════════════════════════════════════════════════════


@router.get("/personas")
async def list_personas(
    user: CurrentUser = Depends(get_current_user),
    tags: str | None = Query(None, description="Filtrar por tags (separados por coma)"),
    difficulty: str | None = Query(None, description="easy, medium, hard"),
) -> list[dict[str, Any]]:
    """Lista personas de prueba (templates + propias del cliente)."""
    sb = get_supabase()

    query = sb.table("test_personas").select("*").order("created_at", desc=True)

    if user.role == "client":
        # Templates + las del cliente
        query = query.or_(f"is_template.eq.true,client_id.eq.{user.client_id}")
    # Admin ve todas

    if difficulty:
        query = query.eq("difficulty", difficulty)

    result = query.execute()
    rows = result.data or []

    # Filtrar por tags en Python (JSONB contains no siempre es directo con supabase-py)
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
        rows = [
            r for r in rows
            if r.get("tags") and any(
                t.lower() in [x.lower() for x in (r["tags"] or [])]
                for t in tag_list
            )
        ]

    return rows


@router.post("/personas", status_code=201)
async def create_persona(
    req: PersonaCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Crea una nueva persona de prueba."""
    sb = get_supabase()

    client_id = _resolve_client_id(user)
    if not client_id and user.role == "client":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo determinar el client_id",
        )

    data: dict[str, Any] = {
        "name": req.name,
        "personality": req.personality,
        "objective": req.objective,
        "success_criteria": req.success_criteria,
        "curveballs": req.curveballs,
        "difficulty": req.difficulty,
        "language": req.language,
        "tags": req.tags,
        "is_template": False,
    }
    if client_id:
        data["client_id"] = client_id

    result = sb.table("test_personas").insert(data).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creando persona",
        )
    return result.data[0]


@router.get("/personas/{persona_id}")
async def get_persona(
    persona_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Obtiene una persona por ID."""
    sb = get_supabase()
    result = (
        sb.table("test_personas")
        .select("*")
        .eq("id", persona_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona no encontrada",
        )

    persona = result.data[0]
    # Verificar acceso: templates son públicas, propias filtradas por client_id
    if (
        not persona.get("is_template")
        and user.role == "client"
        and persona.get("client_id") != user.client_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )
    return persona


@router.patch("/personas/{persona_id}")
async def update_persona(
    persona_id: str,
    req: PersonaUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Actualiza una persona (solo propias, no templates)."""
    sb = get_supabase()

    # Verificar existencia y permisos
    existing = (
        sb.table("test_personas")
        .select("*")
        .eq("id", persona_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona no encontrada",
        )
    _check_own_persona(existing.data[0], user)

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sin cambios",
        )

    result = sb.table("test_personas").update(updates).eq("id", persona_id).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona no encontrada",
        )
    return result.data[0]


@router.delete("/personas/{persona_id}")
async def delete_persona(
    persona_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    """Elimina una persona (solo propias, no templates)."""
    sb = get_supabase()

    existing = (
        sb.table("test_personas")
        .select("*")
        .eq("id", persona_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona no encontrada",
        )
    _check_own_persona(existing.data[0], user)

    sb.table("test_personas").delete().eq("id", persona_id).execute()
    return {"message": "Persona eliminada"}


@router.post("/personas/generate")
async def generate_test_personas(
    req: GeneratePersonasRequest,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Genera personas de prueba con IA basándose en una descripción del negocio."""
    personas = await generate_personas(
        description=req.description,
        count=req.count,
        language=req.language,
    )
    return personas


# ══════════════════════════════════════════════════════════
#  TEST RUNS
# ══════════════════════════════════════════════════════════


@router.post("/run", status_code=201)
async def start_test_run(
    req: RunRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Inicia un test run en background. Retorna el ID inmediatamente."""
    sb = get_supabase()

    # Verificar acceso al agente
    agent = (
        sb.table("agents")
        .select("id, client_id, name")
        .eq("id", req.agent_id)
        .limit(1)
        .execute()
    )
    if not agent.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente no encontrado",
        )
    if user.role == "client" and agent.data[0].get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )

    client_id = agent.data[0]["client_id"]

    # Verificar que la persona existe
    persona = (
        sb.table("test_personas")
        .select("id")
        .eq("id", req.persona_id)
        .limit(1)
        .execute()
    )
    if not persona.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona no encontrada",
        )

    # Crear registro del run
    run_id = str(uuid.uuid4())
    run_data = {
        "id": run_id,
        "client_id": client_id,
        "agent_id": req.agent_id,
        "persona_id": req.persona_id,
        "status": "pending",
    }
    result = sb.table("test_runs").insert(run_data).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creando test run",
        )

    # Ejecutar en background
    background_tasks.add_task(
        run_test, run_id, req.agent_id, req.persona_id, client_id, req.max_turns
    )

    logger.info("Test run %s iniciado: agent=%s, persona=%s", run_id, req.agent_id, req.persona_id)
    return result.data[0]


@router.post("/run/batch", status_code=201)
async def start_batch_runs(
    req: BatchRunRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Inicia múltiples test runs en paralelo. Retorna array de IDs."""
    sb = get_supabase()

    # Verificar acceso al agente
    agent = (
        sb.table("agents")
        .select("id, client_id")
        .eq("id", req.agent_id)
        .limit(1)
        .execute()
    )
    if not agent.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente no encontrado",
        )
    if user.role == "client" and agent.data[0].get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )

    client_id = agent.data[0]["client_id"]
    runs: list[dict[str, Any]] = []

    for persona_id in req.persona_ids:
        run_id = str(uuid.uuid4())
        run_data = {
            "id": run_id,
            "client_id": client_id,
            "agent_id": req.agent_id,
            "persona_id": persona_id,
            "max_turns": req.max_turns,
            "status": "pending",
        }
        result = sb.table("test_runs").insert(run_data).execute()
        if result.data:
            runs.append(result.data[0])
            background_tasks.add_task(
                run_test, run_id, req.agent_id, persona_id, client_id, req.max_turns
            )

    logger.info(
        "Batch de %d test runs iniciado para agent=%s", len(runs), req.agent_id
    )
    return runs


@router.get("/runs")
async def list_runs(
    user: CurrentUser = Depends(get_current_user),
    agent_id: str | None = Query(None),
    persona_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Lista test runs con filtros. Incluye nombre de persona y agente."""
    sb = get_supabase()

    query = (
        sb.table("test_runs")
        .select(
            "*, "
            "test_personas(name, difficulty), "
            "agents(name)"
        )
        .order("created_at", desc=True)
    )

    # Multi-tenancy
    if user.role == "client":
        if not user.client_id:
            return []
        query = query.eq("client_id", user.client_id)

    if agent_id:
        query = query.eq("agent_id", agent_id)
    if persona_id:
        query = query.eq("persona_id", persona_id)
    if status_filter:
        query = query.eq("status", status_filter)

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)

    result = query.execute()
    rows = result.data or []

    # Aplanar los joins para facilitar consumo en frontend
    for row in rows:
        persona_data = row.pop("test_personas", None) or {}
        agent_data = row.pop("agents", None) or {}
        row["persona_name"] = persona_data.get("name")
        row["persona_difficulty"] = persona_data.get("difficulty")
        row["agent_name"] = agent_data.get("name")

    return rows


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Obtiene un test run completo con conversation_log y evaluación."""
    sb = get_supabase()
    result = (
        sb.table("test_runs")
        .select(
            "*, "
            "test_personas(name, personality, objective, difficulty), "
            "agents(name)"
        )
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run no encontrado",
        )

    row = result.data[0]

    # Multi-tenancy
    if user.role == "client" and row.get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )

    # Aplanar joins
    persona_data = row.pop("test_personas", None) or {}
    agent_data = row.pop("agents", None) or {}
    row["persona_name"] = persona_data.get("name")
    row["persona_personality"] = persona_data.get("personality")
    row["persona_objective"] = persona_data.get("objective")
    row["persona_difficulty"] = persona_data.get("difficulty")
    row["agent_name"] = agent_data.get("name")

    return row


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    """Elimina un test run."""
    sb = get_supabase()

    existing = (
        sb.table("test_runs")
        .select("id, client_id")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run no encontrado",
        )
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )

    sb.table("test_runs").delete().eq("id", run_id).execute()
    return {"message": "Test run eliminado"}


# ══════════════════════════════════════════════════════════
#  TEST SUITES
# ══════════════════════════════════════════════════════════


@router.get("/suites")
async def list_suites(
    user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Lista suites de pruebas."""
    sb = get_supabase()

    query = (
        sb.table("test_suites")
        .select("*")
        .order("created_at", desc=True)
    )

    if user.role == "client":
        if not user.client_id:
            return []
        query = query.eq("client_id", user.client_id)

    result = query.execute()
    return result.data or []


@router.post("/suites", status_code=201)
async def create_suite(
    req: SuiteCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Crea una suite de pruebas."""
    sb = get_supabase()

    client_id = _resolve_client_id(user)
    if not client_id and user.role == "client":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo determinar el client_id",
        )

    data: dict[str, Any] = {
        "name": req.name,
        "description": req.description,
        "persona_ids": req.persona_ids,
    }
    if client_id:
        data["client_id"] = client_id

    result = sb.table("test_suites").insert(data).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creando suite",
        )
    return result.data[0]


@router.patch("/suites/{suite_id}")
async def update_suite(
    suite_id: str,
    req: SuiteUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Actualiza una suite de pruebas."""
    sb = get_supabase()

    existing = (
        sb.table("test_suites")
        .select("id, client_id")
        .eq("id", suite_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suite no encontrada",
        )
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sin cambios",
        )

    result = (
        sb.table("test_suites")
        .update(updates)
        .eq("id", suite_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suite no encontrada",
        )
    return result.data[0]


@router.delete("/suites/{suite_id}")
async def delete_suite(
    suite_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    """Elimina una suite de pruebas."""
    sb = get_supabase()

    existing = (
        sb.table("test_suites")
        .select("id, client_id")
        .eq("id", suite_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suite no encontrada",
        )
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )

    sb.table("test_suites").delete().eq("id", suite_id).execute()
    return {"message": "Suite eliminada"}


@router.post("/suites/{suite_id}/run", status_code=201)
async def run_suite(
    suite_id: str,
    req: SuiteRunRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Ejecuta todas las personas de una suite contra un agente."""
    sb = get_supabase()

    # Cargar suite
    suite_result = (
        sb.table("test_suites")
        .select("*")
        .eq("id", suite_id)
        .limit(1)
        .execute()
    )
    if not suite_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suite no encontrada",
        )

    suite = suite_result.data[0]
    if user.role == "client" and suite.get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )

    persona_ids: list[str] = suite.get("persona_ids") or []
    if not persona_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La suite no tiene personas configuradas",
        )

    # Verificar acceso al agente
    agent = (
        sb.table("agents")
        .select("id, client_id")
        .eq("id", req.agent_id)
        .limit(1)
        .execute()
    )
    if not agent.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente no encontrado",
        )
    if user.role == "client" and agent.data[0].get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )

    client_id = agent.data[0]["client_id"]
    max_turns = suite.get("max_turns", 20)
    runs: list[dict[str, Any]] = []

    for persona_id in persona_ids:
        run_id = str(uuid.uuid4())
        run_data = {
            "id": run_id,
            "client_id": client_id,
            "agent_id": req.agent_id,
            "persona_id": persona_id,
            "status": "pending",
        }
        result = sb.table("test_runs").insert(run_data).execute()
        if result.data:
            runs.append(result.data[0])
            background_tasks.add_task(
                run_test, run_id, req.agent_id, persona_id, client_id, max_turns
            )

    logger.info(
        "Suite %s ejecutada: %d runs para agent=%s", suite_id, len(runs), req.agent_id
    )
    return runs


# ══════════════════════════════════════════════════════════
#  STATS
# ══════════════════════════════════════════════════════════


@router.get("/stats")
async def get_stats(
    user: CurrentUser = Depends(get_current_user),
    agent_id: str | None = Query(None),
) -> dict[str, Any]:
    """Estadísticas resumen: total runs, avg score, mejor/peor persona, runs por status."""
    sb = get_supabase()

    query = (
        sb.table("test_runs")
        .select("id, status, score, persona_id, test_personas(name)")
    )

    # Multi-tenancy
    if user.role == "client":
        if not user.client_id:
            return {
                "total_runs": 0,
                "avg_score": 0,
                "runs_by_status": {},
                "best_persona": None,
                "worst_persona": None,
            }
        query = query.eq("client_id", user.client_id)

    if agent_id:
        query = query.eq("agent_id", agent_id)

    result = query.execute()
    rows = result.data or []

    if not rows:
        return {
            "total_runs": 0,
            "avg_score": 0,
            "runs_by_status": {},
            "best_persona": None,
            "worst_persona": None,
        }

    total_runs = len(rows)

    # Runs por status
    runs_by_status: dict[str, int] = {}
    for r in rows:
        s = r.get("status", "unknown")
        runs_by_status[s] = runs_by_status.get(s, 0) + 1

    # Score promedio (solo completed)
    completed = [r for r in rows if r.get("status") == "completed" and r.get("score") is not None]
    avg_score = round(sum(r["score"] for r in completed) / len(completed), 1) if completed else 0

    # Mejor y peor persona (por score promedio)
    persona_scores: dict[str, list[int]] = {}
    persona_names: dict[str, str] = {}
    for r in completed:
        pid = r.get("persona_id", "")
        score = r.get("score", 0)
        persona_scores.setdefault(pid, []).append(score)
        persona_data = r.get("test_personas") or {}
        if pid not in persona_names and persona_data.get("name"):
            persona_names[pid] = persona_data["name"]

    best_persona: dict[str, Any] | None = None
    worst_persona: dict[str, Any] | None = None

    if persona_scores:
        persona_avgs = {
            pid: round(sum(scores) / len(scores), 1)
            for pid, scores in persona_scores.items()
        }
        best_pid = max(persona_avgs, key=lambda p: persona_avgs[p])
        worst_pid = min(persona_avgs, key=lambda p: persona_avgs[p])

        best_persona = {
            "persona_id": best_pid,
            "name": persona_names.get(best_pid, "Desconocida"),
            "avg_score": persona_avgs[best_pid],
            "runs": len(persona_scores[best_pid]),
        }
        worst_persona = {
            "persona_id": worst_pid,
            "name": persona_names.get(worst_pid, "Desconocida"),
            "avg_score": persona_avgs[worst_pid],
            "runs": len(persona_scores[worst_pid]),
        }

    return {
        "total_runs": total_runs,
        "avg_score": avg_score,
        "completed_runs": len(completed),
        "runs_by_status": runs_by_status,
        "best_persona": best_persona,
        "worst_persona": worst_persona,
    }
