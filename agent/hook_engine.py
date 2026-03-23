"""Motor de lifecycle hooks para agentes de voz y texto.

Evalúa reglas determinísticas en eventos del lifecycle:
- OnConversationStart, OnGreeting
- OnUserMessage, PreResponse, PostResponse
- PreToolCall, PostToolCall
- OnInactivity, OnSentimentShift, OnLanguageSwitch, OnGuardrailHit
- OnEscalation, OnConversationEnd, PostConversationEnd

Cada hook produce un HookResult que puede: block, transform, inject_context,
speak, notify, close_session, o simplemente pasar (allow).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Tipos ──────────────────────────────────────────────


class HookAction(str, Enum):
    """Acciones que un hook puede producir."""

    ALLOW = "allow"
    BLOCK = "block"
    TRANSFORM = "transform"
    INJECT_CONTEXT = "inject_context"
    SPEAK = "speak"
    NOTIFY = "notify"
    CLOSE_SESSION = "close_session"
    REPLACE_TOOL = "replace_tool"
    REGENERATE = "regenerate"  # Evaluator-optimizer: pedir al agente que regenere


@dataclass
class HookResult:
    """Resultado de evaluar un hook."""

    action: HookAction = HookAction.ALLOW
    message: str | None = None
    context: str | None = None
    transformed_data: dict | None = None
    notify_config: dict | None = None
    hook_name: str = ""
    hook_id: str = ""


@dataclass
class HookContext:
    """Contexto pasado a los hooks para evaluación."""

    event: str
    channel: str  # "voice", "whatsapp", "widget", "ghl"
    agent_id: str
    client_id: str
    # Datos específicos del evento
    user_text: str | None = None
    response_text: str | None = None
    tool_name: str | None = None
    tool_input: dict = field(default_factory=dict)
    tool_result: dict | None = None
    silence_seconds: float = 0
    inactive_minutes: float = 0
    sentiment: str | None = None
    sentiment_score: float | None = None
    previous_sentiment: str | None = None
    language: str | None = None
    previous_language: str | None = None
    caller_phone: str | None = None
    contact_name: str | None = None
    transcript: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class HookDefinition:
    """Definición de un hook cargado desde DB."""

    id: str
    name: str
    hook_event: str
    channel: str | None  # None = todos los canales
    hook_type: str  # rule, validate, prompt, notify, transform
    matcher: str  # nombre de tool o "*"
    config: dict
    priority: int = 100


# ── Engine ─────────────────────────────────────────────


class HookEngine:
    """Motor de evaluación de hooks para un agente.

    Uso:
        engine = HookEngine(hooks)
        results = await engine.evaluate("PreToolCall", context)
        for result in results:
            if result.action == HookAction.BLOCK:
                # No ejecutar la tool, devolver result.message al agente
    """

    def __init__(self, hooks: list[HookDefinition]) -> None:
        self._hooks = hooks
        # Índice por evento para búsqueda rápida
        self._by_event: dict[str, list[HookDefinition]] = {}
        for hook in sorted(hooks, key=lambda h: h.priority):
            self._by_event.setdefault(hook.hook_event, []).append(hook)

    @property
    def hooks(self) -> list[HookDefinition]:
        return self._hooks

    def has_hooks_for(self, event: str) -> bool:
        """Verifica si hay hooks registrados para un evento."""
        return bool(self._by_event.get(event))

    async def evaluate(
        self, event: str, ctx: HookContext
    ) -> list[HookResult]:
        """Evalúa todos los hooks de un evento y retorna resultados.

        Los hooks se evalúan en orden de prioridad. Si un hook produce BLOCK,
        se detiene la evaluación y retorna inmediatamente.

        Args:
            event: Nombre del evento (debe coincidir con hook_event).
            ctx: Contexto con datos del evento.

        Returns:
            Lista de HookResult. Vacía si no hay hooks o todos son ALLOW.
        """
        hooks = self._by_event.get(event, [])
        if not hooks:
            return []

        results: list[HookResult] = []

        for hook in hooks:
            # Filtrar por canal
            if hook.channel and hook.channel != ctx.channel:
                continue

            # Filtrar por matcher (para PreToolCall/PostToolCall)
            if hook.matcher != "*" and ctx.tool_name:
                if not re.match(hook.matcher, ctx.tool_name):
                    continue

            try:
                result = await self._evaluate_hook(hook, ctx)
                if result.action != HookAction.ALLOW:
                    results.append(result)
                    logger.info(
                        "Hook [%s] %s → %s: %s",
                        hook.hook_event,
                        hook.name,
                        result.action.value,
                        result.message or "",
                    )
                    # BLOCK detiene la cadena
                    if result.action == HookAction.BLOCK:
                        break
            except Exception:
                logger.exception("Error evaluando hook %s (%s)", hook.name, hook.id)

        return results

    async def evaluate_first_block(
        self, event: str, ctx: HookContext
    ) -> HookResult | None:
        """Evalúa hooks y retorna el primer BLOCK, o None si todos pasan."""
        results = await self.evaluate(event, ctx)
        for r in results:
            if r.action == HookAction.BLOCK:
                return r
        return None

    def collect_transforms(self, results: list[HookResult]) -> dict:
        """Combina todas las transformaciones de una lista de resultados."""
        merged: dict[str, Any] = {}
        for r in results:
            if r.action == HookAction.TRANSFORM and r.transformed_data:
                merged.update(r.transformed_data)
        return merged

    def collect_context(self, results: list[HookResult]) -> str:
        """Combina todo el contexto inyectado de una lista de resultados."""
        parts = [r.context for r in results if r.action == HookAction.INJECT_CONTEXT and r.context]
        return "\n".join(parts)

    def collect_notifications(self, results: list[HookResult]) -> list[dict]:
        """Recolecta configs de notificación para enviar de forma asíncrona."""
        return [
            r.notify_config
            for r in results
            if r.action == HookAction.NOTIFY and r.notify_config
        ]

    # ── Evaluación por tipo ────────────────────────────

    async def _evaluate_hook(
        self, hook: HookDefinition, ctx: HookContext
    ) -> HookResult:
        """Evalúa un hook individual según su tipo."""
        base = HookResult(hook_name=hook.name, hook_id=hook.id)

        if hook.hook_type == "rule":
            return self._eval_rule(hook, ctx, base)
        elif hook.hook_type == "validate":
            return self._eval_validate(hook, ctx, base)
        elif hook.hook_type == "transform":
            return self._eval_transform(hook, ctx, base)
        elif hook.hook_type == "notify":
            return self._eval_notify(hook, ctx, base)
        elif hook.hook_type == "prompt":
            return await self._eval_prompt(hook, ctx, base)
        elif hook.hook_type == "evaluator":
            return await self._eval_evaluator(hook, ctx, base)
        else:
            logger.warning("Tipo de hook desconocido: %s", hook.hook_type)
            return base

    def _eval_rule(
        self, hook: HookDefinition, ctx: HookContext, base: HookResult
    ) -> HookResult:
        """Evalúa un hook tipo 'rule' — condiciones if/then."""
        config = hook.config
        conditions = config.get("conditions", [])

        if not self._check_conditions(conditions, ctx):
            return base  # Condiciones no cumplidas → allow

        action_str = config.get("action", "block")
        message = config.get("message", "")

        if action_str == "block":
            base.action = HookAction.BLOCK
            base.message = message
        elif action_str == "inject_context":
            base.action = HookAction.INJECT_CONTEXT
            base.context = config.get("context", message)
        elif action_str == "speak":
            base.action = HookAction.SPEAK
            base.message = message
        elif action_str == "close_session":
            base.action = HookAction.CLOSE_SESSION
            base.message = message
        elif action_str == "replace_tool":
            base.action = HookAction.REPLACE_TOOL
            base.message = config.get("reason", message)
            base.transformed_data = {"replace_with": config.get("replace_with", "")}

        return base

    def _eval_validate(
        self, hook: HookDefinition, ctx: HookContext, base: HookResult
    ) -> HookResult:
        """Evalúa un hook tipo 'validate' — verifica datos requeridos."""
        validate = hook.config.get("validate", {})

        # Validar campos requeridos en tool_input
        required_fields = validate.get("required_fields", [])
        if required_fields and ctx.tool_input:
            missing = [f for f in required_fields if not ctx.tool_input.get(f)]
            if missing:
                base.action = HookAction.BLOCK
                base.message = validate.get(
                    "message",
                    f"Faltan datos requeridos: {', '.join(missing)}",
                )
                return base

        # Validar horario de negocio
        if validate.get("check") == "business_hours":
            if not self._check_business_hours(validate):
                action = validate.get("outside_hours_action", "block")
                if action == "auto_reply":
                    base.action = HookAction.SPEAK
                    base.message = validate.get(
                        "outside_hours_message",
                        "Estamos fuera de horario. Te atenderemos pronto.",
                    )
                else:
                    base.action = HookAction.BLOCK
                    base.message = validate.get("outside_hours_message", "Fuera de horario.")
                return base

        return base

    def _eval_transform(
        self, hook: HookDefinition, ctx: HookContext, base: HookResult
    ) -> HookResult:
        """Evalúa un hook tipo 'transform' — modifica input/output."""
        transform = hook.config.get("transform", {})
        conditions = hook.config.get("conditions", [])

        # Verificar condiciones opcionales
        if conditions and not self._check_conditions(conditions, ctx):
            return base

        base.action = HookAction.TRANSFORM
        base.transformed_data = transform

        # Si tiene un append, agregar al mensaje
        append = hook.config.get("append")
        if append:
            base.message = append

        return base

    def _eval_notify(
        self, hook: HookDefinition, ctx: HookContext, base: HookResult
    ) -> HookResult:
        """Evalúa un hook tipo 'notify' — side-effect sin bloquear."""
        conditions = hook.config.get("conditions", [])

        if conditions and not self._check_conditions(conditions, ctx):
            return base

        base.action = HookAction.NOTIFY
        base.notify_config = {
            "channel": hook.config.get("channel", "webhook"),
            "to": hook.config.get("to"),
            "url": hook.config.get("url"),
            "template": hook.config.get("template", ""),
            "payload": hook.config.get("payload", []),
            "hook_name": hook.name,
            "context": {
                "agent_id": ctx.agent_id,
                "client_id": ctx.client_id,
                "caller_phone": ctx.caller_phone,
                "contact_name": ctx.contact_name,
                "channel": ctx.channel,
            },
        }
        return base

    async def _eval_prompt(
        self, hook: HookDefinition, ctx: HookContext, base: HookResult
    ) -> HookResult:
        """Evalúa un hook tipo 'prompt' — consulta a un LLM rápido."""
        prompt_text = hook.config.get("prompt", "")
        on_fail = hook.config.get("on_fail", "block")
        message = hook.config.get("message", "No puedo ayudarte con eso.")

        if not prompt_text:
            return base

        try:
            result = await asyncio.wait_for(
                self._call_prompt_llm(prompt_text, ctx),
                timeout=3.0,
            )
            if not result:
                # El LLM dijo que no pasa
                if on_fail == "block":
                    base.action = HookAction.BLOCK
                    base.message = message
                elif on_fail == "inject_context":
                    base.action = HookAction.INJECT_CONTEXT
                    base.context = message
        except asyncio.TimeoutError:
            logger.warning("Timeout en prompt hook '%s' — permitiendo", hook.name)
        except Exception:
            logger.exception("Error en prompt hook '%s' — permitiendo", hook.name)

        return base

    async def _eval_evaluator(
        self, hook: HookDefinition, ctx: HookContext, base: HookResult
    ) -> HookResult:
        """Evalúa un hook tipo 'evaluator' — patrón evaluator-optimizer de Anthropic.

        Un segundo LLM evalúa la respuesta del agente contra criterios específicos.
        Si no pasa, retorna REGENERATE con feedback para que el agente regenere.

        Config esperada:
            criteria: str — criterios de evaluación (ej: "No debe contener diagnósticos médicos")
            max_retries: int — máximo intentos de regeneración (default 1)
            feedback_prefix: str — prefijo del feedback (default "Corrige tu respuesta:")
        """
        criteria = hook.config.get("criteria", "")
        feedback_prefix = hook.config.get("feedback_prefix", "Corrige tu respuesta:")

        if not criteria or not ctx.response_text:
            return base

        try:
            evaluation = await asyncio.wait_for(
                self._call_evaluator_llm(criteria, ctx),
                timeout=3.0,
            )
            if not evaluation["passed"]:
                base.action = HookAction.REGENERATE
                base.message = f"{feedback_prefix} {evaluation['feedback']}"
                logger.info(
                    "Evaluator hook '%s' rechazó respuesta: %s",
                    hook.name, evaluation["feedback"][:100],
                )
        except asyncio.TimeoutError:
            logger.warning("Timeout en evaluator hook '%s' — permitiendo", hook.name)
        except Exception:
            logger.exception("Error en evaluator hook '%s' — permitiendo", hook.name)

        return base

    @staticmethod
    async def _call_evaluator_llm(criteria: str, ctx: HookContext) -> dict:
        """Llama a un LLM rápido para evaluar una respuesta contra criterios.

        Returns:
            {"passed": bool, "feedback": str}
        """
        try:
            from google import genai

            client = genai.Client()
            eval_prompt = (
                f"Eres un evaluador de calidad. Evalúa la siguiente respuesta de un agente "
                f"contra los criterios dados.\n\n"
                f"## Criterios\n{criteria}\n\n"
                f"## Respuesta del agente\n{ctx.response_text}\n\n"
                f"## Contexto\n"
                f"- Mensaje del usuario: {ctx.user_text or 'N/A'}\n"
                f"- Canal: {ctx.channel}\n\n"
                f"Responde en formato:\n"
                f"RESULTADO: APROBADO o RECHAZADO\n"
                f"FEEDBACK: [si rechazado, explica qué corregir en 1-2 frases]\n"
            )

            response = await asyncio.to_thread(
                lambda: client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=eval_prompt,
                )
            )

            text = (response.text or "").strip()
            passed = "APROBADO" in text.upper()
            # Extraer feedback
            feedback = ""
            if "FEEDBACK:" in text:
                feedback = text.split("FEEDBACK:", 1)[1].strip()

            return {"passed": passed, "feedback": feedback}

        except Exception:
            logger.exception("Error en evaluator LLM")
            return {"passed": True, "feedback": ""}

    # ── Helpers ────────────────────────────────────────

    def _check_conditions(
        self, conditions: list[dict], ctx: HookContext
    ) -> bool:
        """Evalúa lista de condiciones (AND lógico). Retorna True si todas se cumplen."""
        if not conditions:
            return True

        for cond in conditions:
            field_name = cond.get("field", "")
            operator = cond.get("operator", "equals")
            value = cond.get("value")

            actual = self._resolve_field(field_name, ctx)

            if not self._compare(actual, operator, value):
                return False

        return True

    def _resolve_field(self, field_path: str, ctx: HookContext) -> Any:
        """Resuelve un campo del contexto usando dot notation.

        Ejemplos:
            "user_text" → ctx.user_text
            "tool_input.date" → ctx.tool_input["date"]
            "input.text" → alias para user_text
            "response.text" → alias para response_text
            "silence_seconds" → ctx.silence_seconds
            "metadata.key" → ctx.metadata["key"]
        """
        # Aliases comunes
        aliases = {
            "input.text": "user_text",
            "input.day_of_week": "_day_of_week",
            "response.text": "response_text",
            "response.contains_price": "_contains_price",
        }
        field_path = aliases.get(field_path, field_path)

        # Campos computados
        if field_path == "_day_of_week":
            return self._get_day_of_week()
        if field_path == "_contains_price":
            return self._text_contains_price(ctx.response_text or "")

        # Campos directos de HookContext
        parts = field_path.split(".", 1)
        root = parts[0]

        # Primero buscar en atributos directos
        if hasattr(ctx, root):
            val = getattr(ctx, root)
            if len(parts) == 1:
                return val
            # Sub-campo en un dict
            if isinstance(val, dict):
                return val.get(parts[1])
            return None

        return None

    @staticmethod
    def _compare(actual: Any, operator: str, expected: Any) -> bool:
        """Compara un valor actual contra esperado con un operador."""
        if actual is None and operator not in ("is_null", "is_not_null"):
            return False

        if operator == "equals":
            return actual == expected
        elif operator == "not_equals":
            return actual != expected
        elif operator == "contains":
            return isinstance(actual, str) and isinstance(expected, str) and expected.lower() in actual.lower()
        elif operator == "not_contains":
            return isinstance(actual, str) and isinstance(expected, str) and expected.lower() not in actual.lower()
        elif operator == "contains_any":
            if isinstance(actual, str) and isinstance(expected, list):
                actual_lower = actual.lower()
                return any(str(v).lower() in actual_lower for v in expected)
            return False
        elif operator == "contains_all":
            if isinstance(actual, str) and isinstance(expected, list):
                actual_lower = actual.lower()
                return all(str(v).lower() in actual_lower for v in expected)
            return False
        elif operator == "matches":
            return isinstance(actual, str) and bool(re.search(str(expected), actual, re.IGNORECASE))
        elif operator == "gt":
            return float(actual) > float(expected)
        elif operator == "gte":
            return float(actual) >= float(expected)
        elif operator == "lt":
            return float(actual) < float(expected)
        elif operator == "lte":
            return float(actual) <= float(expected)
        elif operator == "in":
            return actual in (expected if isinstance(expected, list) else [expected])
        elif operator == "not_in":
            return actual not in (expected if isinstance(expected, list) else [expected])
        elif operator == "is_null":
            return actual is None
        elif operator == "is_not_null":
            return actual is not None
        else:
            logger.warning("Operador desconocido: %s", operator)
            return False

    @staticmethod
    def _get_day_of_week() -> str:
        """Retorna el día de la semana actual en español (zona México)."""
        from datetime import datetime, timezone, timedelta

        # UTC-6 (México central)
        mx_tz = timezone(timedelta(hours=-6))
        now = datetime.now(mx_tz)
        days = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        return days[now.weekday()]

    @staticmethod
    def _text_contains_price(text: str) -> bool:
        """Detecta si un texto contiene menciones de precios."""
        price_patterns = [
            r"\$\s*\d+",
            r"\d+\s*(pesos|MXN|USD|dólares|dolares)",
            r"cuesta\s+\d+",
            r"precio\s*(de|es|:)\s*\d+",
            r"cobr[ao]\w*\s+\d+",
        ]
        for pattern in price_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _check_business_hours(validate: dict) -> bool:
        """Verifica si la hora actual está dentro del horario de negocio."""
        from datetime import datetime, timezone, timedelta
        import pytz

        tz_name = validate.get("timezone", "America/Mexico_City")
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = timezone(timedelta(hours=-6))

        now = datetime.now(tz) if hasattr(tz, "localize") else datetime.now(tz)
        day_abbr = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now.weekday()]

        hours = validate.get("hours", {})

        # Buscar regla para hoy
        schedule = None
        for key, val in hours.items():
            days_in_key = [d.strip().lower() for d in key.replace("-", ",").split(",")]
            # Expandir rangos como "mon-fri"
            all_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            if len(days_in_key) == 2 and days_in_key[0] in all_days and days_in_key[1] in all_days:
                start_idx = all_days.index(days_in_key[0])
                end_idx = all_days.index(days_in_key[1])
                expanded = all_days[start_idx : end_idx + 1]
                if day_abbr in expanded:
                    schedule = val
                    break
            elif day_abbr in days_in_key:
                schedule = val
                break

        if not schedule:
            return False  # No hay horario definido para hoy

        # Parsear "9:00-18:00"
        try:
            parts = schedule.split("-")
            open_h, open_m = map(int, parts[0].strip().split(":"))
            close_h, close_m = map(int, parts[1].strip().split(":"))
            current_minutes = now.hour * 60 + now.minute
            open_minutes = open_h * 60 + open_m
            close_minutes = close_h * 60 + close_m
            return open_minutes <= current_minutes <= close_minutes
        except (ValueError, IndexError):
            logger.warning("Formato de horario inválido: %s", schedule)
            return True  # En caso de error, permitir

    @staticmethod
    async def _call_prompt_llm(prompt: str, ctx: HookContext) -> bool:
        """Llama a un LLM rápido para evaluar una condición.

        Retorna True si el LLM dice que está bien, False si detecta problema.
        """
        try:
            from google import genai

            client = genai.Client()
            # Construir contexto para el LLM
            eval_prompt = (
                f"Evalúa lo siguiente y responde SOLO con 'SI' o 'NO'.\n\n"
                f"Pregunta: {prompt}\n\n"
                f"Contexto:\n"
                f"- Canal: {ctx.channel}\n"
                f"- Texto del usuario: {ctx.user_text or 'N/A'}\n"
                f"- Respuesta del agente: {ctx.response_text or 'N/A'}\n"
                f"- Tool: {ctx.tool_name or 'N/A'}\n"
                f"- Tool input: {ctx.tool_input or 'N/A'}\n\n"
                f"Responde SI si todo está bien, NO si hay un problema."
            )

            response = await asyncio.to_thread(
                lambda: client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=eval_prompt,
                )
            )

            answer = (response.text or "").strip().upper()
            return answer.startswith("SI") or answer.startswith("SÍ")

        except Exception:
            logger.exception("Error en prompt LLM hook")
            return True  # En caso de error, permitir


# ── Carga desde DB ─────────────────────────────────────


async def load_hooks_for_agent(agent_id: str) -> list[HookDefinition]:
    """Carga hooks activos de un agente desde Supabase.

    Args:
        agent_id: UUID del agente.

    Returns:
        Lista de HookDefinition ordenada por priority.
    """
    try:
        from agent.db import get_supabase

        sb = get_supabase()
        result = await asyncio.to_thread(
            lambda: sb.table("agent_hooks")
            .select("*")
            .eq("agent_id", agent_id)
            .eq("enabled", True)
            .order("priority")
            .execute()
        )
    except Exception:
        logger.exception("Error cargando hooks para agente %s", agent_id)
        return []

    if not result.data:
        return []

    hooks: list[HookDefinition] = []
    for row in result.data:
        hooks.append(
            HookDefinition(
                id=str(row["id"]),
                name=row.get("name", ""),
                hook_event=row["hook_event"],
                channel=row.get("channel"),
                hook_type=row["hook_type"],
                matcher=row.get("matcher", "*"),
                config=row.get("config") or {},
                priority=row.get("priority", 100),
            )
        )

    logger.info("Cargados %d hooks para agente %s", len(hooks), agent_id)
    return hooks
