"""
Production call evaluator — samples and evaluates calls for silent failures.

Runs as a background task, sampling recent calls and running them through
the failure detector to identify quality issues.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("api.call_evaluator")


async def evaluate_call(call_id: str, sb=None) -> dict | None:
    """Evaluate a single call for silent failures."""
    from api.deps import get_supabase

    sb = sb or get_supabase()

    # 1. Fetch call data
    call_result = sb.table("calls").select("*").eq("id", call_id).limit(1).execute()
    if not call_result.data:
        return None
    call = call_result.data[0]

    # 2. Get agent config (system_prompt)
    agent = None
    if call.get("agent_id"):
        agent_result = (
            sb.table("agents")
            .select("name, system_prompt, agent_type")
            .eq("id", call["agent_id"])
            .limit(1)
            .execute()
        )
        agent = agent_result.data[0] if agent_result.data else None

    # 3. Build transcript from metadata or summary
    transcript = ""
    if call.get("metadata") and isinstance(call["metadata"], dict):
        transcript = call["metadata"].get("transcript", "")
    if not transcript:
        transcript = call.get("resumen_ia") or call.get("summary") or ""

    if not transcript or len(transcript) < 50:
        logger.debug("Call %s has insufficient transcript, skipping", call_id)
        return None

    # 4. Get tool traces if available
    tool_calls: list[dict] = []
    try:
        traces = (
            sb.table("call_tool_traces")
            .select("*")
            .eq("call_id", call_id)
            .order("created_at")
            .execute()
            .data
            or []
        )
        tool_calls = [
            {
                "name": t["tool_name"],
                "params": t.get("tool_params", {}),
                "result": t.get("tool_result", {}),
            }
            for t in traces
        ]
    except Exception:
        pass  # Tabla puede no existir aún

    # 5. Run failure detection
    from agent.failure_detector import detect_failures

    analysis = await detect_failures(
        transcript=transcript,
        system_prompt=agent["system_prompt"] if agent else "",
        tool_calls=tool_calls if tool_calls else None,
        agent_name=agent["name"] if agent else "",
        agent_type=agent.get("agent_type", "inbound") if agent else "inbound",
    )

    # 6. Store evaluation
    eval_data = {
        "call_id": call_id,
        "client_id": call["client_id"],
        "agent_id": call.get("agent_id"),
        "overall_score": analysis.overall_score,
        "failures_found": len(analysis.failures),
        "critical_failures": analysis.critical_count,
        "evaluation_data": analysis.to_dict(),
        "status": "completed" if analysis.overall_score >= 0 else "failed",
    }
    result = sb.table("call_evaluations").insert(eval_data).execute()
    evaluation_id = result.data[0]["id"] if result.data else None

    # 7. Store individual failures
    if evaluation_id and analysis.failures:
        failure_rows = []
        for f in analysis.failures:
            failure_rows.append(
                {
                    "evaluation_id": evaluation_id,
                    "call_id": call_id,
                    "client_id": call["client_id"],
                    "failure_type": f.failure_type.value,
                    "severity": f.severity.value,
                    "description": f.description,
                    "evidence": f.evidence,
                    "turn_index": f.turn_index,
                    "recommendation": f.recommendation,
                }
            )
        sb.table("evaluation_failures").insert(failure_rows).execute()

    # 8. Generate alerts for critical/high failures
    if evaluation_id and (analysis.critical_count > 0 or analysis.high_count > 0):
        alert = {
            "client_id": call["client_id"],
            "agent_id": call.get("agent_id"),
            "call_id": call_id,
            "evaluation_id": evaluation_id,
            "alert_type": (
                "critical_failure" if analysis.critical_count > 0 else "high_failure"
            ),
            "severity": "critical" if analysis.critical_count > 0 else "high",
            "title": (
                "Fallo critico detectado"
                if analysis.critical_count > 0
                else "Fallo importante detectado"
            ),
            "description": analysis.summary,
            "metadata": {
                "score": analysis.overall_score,
                "critical": analysis.critical_count,
                "high": analysis.high_count,
                "failure_types": list(
                    set(f.failure_type.value for f in analysis.failures)
                ),
            },
        }
        sb.table("quality_alerts").insert(alert).execute()

    logger.info(
        "Evaluated call %s: score=%d failures=%d critical=%d",
        call_id,
        analysis.overall_score,
        len(analysis.failures),
        analysis.critical_count,
    )
    return eval_data


async def run_evaluation_sweep(sample_size: int = 10) -> dict:
    """Sample recent unevaluated calls and evaluate them."""
    from api.deps import get_supabase

    sb = get_supabase()

    # Llamadas completadas en las últimas 24h
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    calls = (
        sb.table("calls")
        .select("id")
        .eq("status", "completed")
        .gte("started_at", cutoff)
        .order("started_at", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )

    if not calls:
        return {"evaluated": 0, "skipped": 0, "errors": 0}

    # Filtrar las que ya fueron evaluadas
    call_ids = [c["id"] for c in calls]
    existing = (
        sb.table("call_evaluations")
        .select("call_id")
        .in_("call_id", call_ids)
        .execute()
        .data
        or []
    )
    evaluated_ids = {e["call_id"] for e in existing}

    unevaluated = [cid for cid in call_ids if cid not in evaluated_ids][:sample_size]

    results = {"evaluated": 0, "skipped": 0, "errors": 0}
    for call_id in unevaluated:
        try:
            result = await evaluate_call(call_id, sb)
            if result:
                results["evaluated"] += 1
            else:
                results["skipped"] += 1
        except Exception as e:
            logger.error("Error evaluating call %s: %s", call_id, e)
            results["errors"] += 1

    logger.info("Evaluation sweep: %s", results)
    return results


_worker_task: asyncio.Task | None = None


def start_evaluation_worker(interval_minutes: int = 30) -> None:
    """Inicia el worker de evaluación como task async."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        logger.warning("Evaluation worker ya está corriendo")
        return
    _worker_task = asyncio.create_task(_evaluation_loop(interval_minutes))
    logger.info("Evaluation worker started (interval=%dm)", interval_minutes)


def stop_evaluation_worker() -> None:
    """Detiene el worker de evaluación."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None
        logger.info("Evaluation worker stopped")


async def _evaluation_loop(interval_minutes: int = 30) -> None:
    """Background loop that periodically evaluates calls."""
    # Esperar a que la app arranque
    await asyncio.sleep(60)
    while True:
        try:
            await run_evaluation_sweep(sample_size=10)
        except asyncio.CancelledError:
            logger.info("Evaluation worker cancelado")
            return
        except Exception:
            logger.exception("Evaluation worker error")
        await asyncio.sleep(interval_minutes * 60)
