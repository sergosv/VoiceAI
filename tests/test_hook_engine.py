"""Tests para el motor de lifecycle hooks."""

import pytest
from agent.hook_engine import (
    HookAction,
    HookContext,
    HookDefinition,
    HookEngine,
    HookResult,
)


# ── Helpers ──────────────────────────────────────────────


def _make_hook(
    event: str = "PreToolCall",
    hook_type: str = "rule",
    matcher: str = "*",
    channel: str | None = None,
    config: dict | None = None,
    priority: int = 100,
    name: str = "test-hook",
) -> HookDefinition:
    return HookDefinition(
        id="h1",
        name=name,
        hook_event=event,
        channel=channel,
        hook_type=hook_type,
        matcher=matcher,
        config=config or {},
        priority=priority,
    )


def _make_ctx(
    event: str = "PreToolCall",
    channel: str = "voice",
    tool_name: str | None = None,
    tool_input: dict | None = None,
    user_text: str | None = None,
    response_text: str | None = None,
    silence_seconds: float = 0,
) -> HookContext:
    return HookContext(
        event=event,
        channel=channel,
        agent_id="agent-1",
        client_id="client-1",
        tool_name=tool_name,
        tool_input=tool_input or {},
        user_text=user_text,
        response_text=response_text,
        silence_seconds=silence_seconds,
    )


# ── Tests de condiciones y operadores ────────────────────


class TestConditions:
    """Tests para evaluación de condiciones."""

    @pytest.mark.asyncio
    async def test_no_conditions_passes(self):
        """Sin condiciones, el hook siempre se activa."""
        hook = _make_hook(config={"conditions": [], "action": "block", "message": "blocked"})
        engine = HookEngine([hook])
        ctx = _make_ctx()
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 1
        assert results[0].action == HookAction.BLOCK

    @pytest.mark.asyncio
    async def test_equals_operator(self):
        hook = _make_hook(config={
            "conditions": [{"field": "user_text", "operator": "equals", "value": "hola"}],
            "action": "block", "message": "match",
        })
        engine = HookEngine([hook])

        # Match
        ctx = _make_ctx(user_text="hola")
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 1

        # No match
        ctx = _make_ctx(user_text="adiós")
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_contains_operator(self):
        hook = _make_hook(config={
            "conditions": [{"field": "user_text", "operator": "contains", "value": "cita"}],
            "action": "block", "message": "tiene cita",
        })
        engine = HookEngine([hook])

        ctx = _make_ctx(user_text="Quiero agendar una cita para mañana")
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_contains_any_operator(self):
        hook = _make_hook(config={
            "conditions": [{"field": "user_text", "operator": "contains_any", "value": ["demanda", "abogado", "legal"]}],
            "action": "inject_context", "context": "tema legal detectado",
        })
        engine = HookEngine([hook])

        ctx = _make_ctx(user_text="Voy a llamar a mi abogado")
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 1
        assert results[0].action == HookAction.INJECT_CONTEXT

        ctx = _make_ctx(user_text="Quiero una cita")
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_gte_operator(self):
        hook = _make_hook(
            event="OnInactivity",
            config={
                "conditions": [{"field": "silence_seconds", "operator": "gte", "value": 5}],
                "action": "speak", "message": "¿Sigue ahí?",
            },
        )
        engine = HookEngine([hook])

        ctx = _make_ctx(event="OnInactivity", silence_seconds=7.0)
        results = await engine.evaluate("OnInactivity", ctx)
        assert len(results) == 1
        assert results[0].action == HookAction.SPEAK

        ctx = _make_ctx(event="OnInactivity", silence_seconds=3.0)
        results = await engine.evaluate("OnInactivity", ctx)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_not_equals_operator(self):
        hook = _make_hook(config={
            "conditions": [{"field": "channel", "operator": "not_equals", "value": "voice"}],
            "action": "block", "message": "not voice",
        })
        engine = HookEngine([hook])

        # channel no está como campo directo en HookContext pero está en la comparación
        ctx = _make_ctx(user_text="test")
        # channel = "voice" → no debería matchear not_equals "voice"
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 0


# ── Tests de filtros ─────────────────────────────────────


class TestFilters:
    """Tests para filtro por canal y matcher."""

    @pytest.mark.asyncio
    async def test_channel_filter(self):
        """Hook con channel='whatsapp' no se dispara para voice."""
        hook = _make_hook(
            channel="whatsapp",
            config={"conditions": [], "action": "block", "message": "wa only"},
        )
        engine = HookEngine([hook])

        # Voice → no matchea
        ctx = _make_ctx(channel="voice")
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 0

        # WhatsApp → matchea
        ctx = _make_ctx(channel="whatsapp")
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_null_channel_matches_all(self):
        """Hook con channel=None se dispara para todos los canales."""
        hook = _make_hook(channel=None, config={"conditions": [], "action": "block", "message": "all"})
        engine = HookEngine([hook])

        for ch in ("voice", "whatsapp", "widget", "ghl"):
            ctx = _make_ctx(channel=ch)
            results = await engine.evaluate("PreToolCall", ctx)
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_tool_matcher(self):
        """Hook con matcher='schedule_appointment' solo matchea esa tool."""
        hook = _make_hook(
            matcher="schedule_appointment",
            config={"conditions": [], "action": "block", "message": "no schedule"},
        )
        engine = HookEngine([hook])

        # schedule_appointment → matchea
        ctx = _make_ctx(tool_name="schedule_appointment")
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 1

        # send_whatsapp → no matchea
        ctx = _make_ctx(tool_name="send_whatsapp")
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_wildcard_matcher(self):
        """Hook con matcher='*' matchea cualquier tool."""
        hook = _make_hook(matcher="*", config={"conditions": [], "action": "block", "message": "all tools"})
        engine = HookEngine([hook])

        for tool in ("schedule_appointment", "send_whatsapp", "call_api"):
            ctx = _make_ctx(tool_name=tool)
            results = await engine.evaluate("PreToolCall", ctx)
            assert len(results) == 1


# ── Tests de tipos de hook ───────────────────────────────


class TestHookTypes:
    """Tests para cada tipo de hook."""

    @pytest.mark.asyncio
    async def test_rule_block(self):
        hook = _make_hook(config={
            "conditions": [{"field": "user_text", "operator": "contains", "value": "cancelar"}],
            "action": "block",
            "message": "No se puede cancelar por este medio.",
        })
        engine = HookEngine([hook])
        ctx = _make_ctx(user_text="Quiero cancelar mi cita")
        results = await engine.evaluate("PreToolCall", ctx)
        assert results[0].action == HookAction.BLOCK
        assert "cancelar" in results[0].message

    @pytest.mark.asyncio
    async def test_rule_inject_context(self):
        hook = _make_hook(config={
            "conditions": [],
            "action": "inject_context",
            "context": "El cliente es VIP, trátalo con especial atención.",
        })
        engine = HookEngine([hook])
        ctx = _make_ctx()
        results = await engine.evaluate("PreToolCall", ctx)
        assert results[0].action == HookAction.INJECT_CONTEXT
        assert "VIP" in results[0].context

    @pytest.mark.asyncio
    async def test_rule_speak(self):
        hook = _make_hook(config={
            "conditions": [{"field": "silence_seconds", "operator": "gte", "value": 5}],
            "action": "speak",
            "message": "¿Me escucha?",
        })
        engine = HookEngine([hook])
        ctx = _make_ctx(silence_seconds=6.0)
        results = await engine.evaluate("PreToolCall", ctx)
        assert results[0].action == HookAction.SPEAK

    @pytest.mark.asyncio
    async def test_validate_required_fields(self):
        hook = _make_hook(hook_type="validate", config={
            "validate": {
                "required_fields": ["patient_name", "date"],
                "message": "Faltan datos.",
            },
        })
        engine = HookEngine([hook])

        # Missing fields
        ctx = _make_ctx(tool_input={"patient_name": "Juan"})
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 1
        assert results[0].action == HookAction.BLOCK

        # All fields present
        ctx = _make_ctx(tool_input={"patient_name": "Juan", "date": "2026-03-25"})
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_transform(self):
        hook = _make_hook(hook_type="transform", config={
            "transform": {"max_length": 500},
            "append": "Precios sujetos a cambio.",
        })
        engine = HookEngine([hook])
        ctx = _make_ctx()
        results = await engine.evaluate("PreToolCall", ctx)
        assert results[0].action == HookAction.TRANSFORM
        assert results[0].transformed_data == {"max_length": 500}
        assert "Precios" in results[0].message

    @pytest.mark.asyncio
    async def test_notify(self):
        hook = _make_hook(hook_type="notify", config={
            "channel": "whatsapp",
            "to": "owner",
            "template": "Nueva cita para {{caller_phone}}",
        })
        engine = HookEngine([hook])
        ctx = _make_ctx()
        results = await engine.evaluate("PreToolCall", ctx)
        assert results[0].action == HookAction.NOTIFY
        assert results[0].notify_config["channel"] == "whatsapp"


# ── Tests de prioridad y cadena ──────────────────────────


class TestPriorityAndChain:
    """Tests para orden de evaluación y detención en BLOCK."""

    @pytest.mark.asyncio
    async def test_priority_order(self):
        """Hooks se evalúan en orden de prioridad (menor primero)."""
        h1 = _make_hook(name="high", priority=200, config={"conditions": [], "action": "inject_context", "context": "high"})
        h1.id = "h1"
        h2 = _make_hook(name="low", priority=50, config={"conditions": [], "action": "inject_context", "context": "low"})
        h2.id = "h2"

        engine = HookEngine([h1, h2])
        ctx = _make_ctx()
        results = await engine.evaluate("PreToolCall", ctx)
        assert results[0].hook_name == "low"
        assert results[1].hook_name == "high"

    @pytest.mark.asyncio
    async def test_block_stops_chain(self):
        """Un BLOCK detiene la evaluación de hooks posteriores."""
        h1 = _make_hook(name="blocker", priority=10, config={"conditions": [], "action": "block", "message": "stop"})
        h1.id = "h1"
        h2 = _make_hook(name="after", priority=20, config={"conditions": [], "action": "inject_context", "context": "never"})
        h2.id = "h2"

        engine = HookEngine([h1, h2])
        ctx = _make_ctx()
        results = await engine.evaluate("PreToolCall", ctx)
        assert len(results) == 1
        assert results[0].hook_name == "blocker"


# ── Tests de helpers ─────────────────────────────────────


class TestHelpers:
    """Tests para collect_transforms, collect_context, etc."""

    def test_collect_context(self):
        results = [
            HookResult(action=HookAction.INJECT_CONTEXT, context="Contexto 1"),
            HookResult(action=HookAction.INJECT_CONTEXT, context="Contexto 2"),
            HookResult(action=HookAction.BLOCK, message="blocked"),
        ]
        engine = HookEngine([])
        ctx = engine.collect_context(results)
        assert "Contexto 1" in ctx
        assert "Contexto 2" in ctx

    def test_collect_transforms(self):
        results = [
            HookResult(action=HookAction.TRANSFORM, transformed_data={"max_length": 500}),
            HookResult(action=HookAction.TRANSFORM, transformed_data={"allow_emojis": True}),
        ]
        engine = HookEngine([])
        transforms = engine.collect_transforms(results)
        assert transforms == {"max_length": 500, "allow_emojis": True}

    def test_collect_notifications(self):
        results = [
            HookResult(action=HookAction.NOTIFY, notify_config={"channel": "webhook", "url": "https://x.com"}),
            HookResult(action=HookAction.ALLOW),
        ]
        engine = HookEngine([])
        notifs = engine.collect_notifications(results)
        assert len(notifs) == 1

    @pytest.mark.asyncio
    async def test_has_hooks_for(self):
        hook = _make_hook(event="OnUserMessage")
        engine = HookEngine([hook])
        assert engine.has_hooks_for("OnUserMessage")
        assert not engine.has_hooks_for("PreToolCall")

    @pytest.mark.asyncio
    async def test_evaluate_first_block(self):
        h1 = _make_hook(config={"conditions": [], "action": "inject_context", "context": "ctx"})
        h1.id = "h1"
        h2 = _make_hook(name="blocker", config={"conditions": [], "action": "block", "message": "stop"})
        h2.id = "h2"
        h2.priority = 200

        engine = HookEngine([h1, h2])
        ctx = _make_ctx()
        result = await engine.evaluate_first_block("PreToolCall", ctx)
        assert result is not None
        assert result.action == HookAction.BLOCK


# ── Tests de campos computados ───────────────────────────


class TestComputedFields:
    """Tests para campos computados como contains_price."""

    def test_contains_price_detection(self):
        assert HookEngine._text_contains_price("El costo es $500 pesos")
        assert HookEngine._text_contains_price("Cobra 1500 pesos")
        assert HookEngine._text_contains_price("El precio es: 200 MXN")
        assert not HookEngine._text_contains_price("Hola, buenos días")
        assert not HookEngine._text_contains_price("Tenemos 5 doctores disponibles")

    def test_day_of_week_returns_spanish(self):
        day = HookEngine._get_day_of_week()
        valid_days = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        assert day in valid_days
