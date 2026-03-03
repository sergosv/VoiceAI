"""Tests para el motor de flujos de conversación."""

import pytest

from agent.flow_engine import FlowEngine, FlowState


# ── Helpers ──────────────────────────────────────────────


def _make_flow(nodes: list[dict], edges: list[dict]) -> dict:
    """Crea un flow JSON minimal."""
    return {"nodes": nodes, "edges": edges}


def _start_node(node_id: str = "start-1", greeting: str = "Hola, bienvenido") -> dict:
    return {
        "id": node_id,
        "type": "start",
        "data": {"greeting": greeting},
        "position": {"x": 0, "y": 0},
    }


def _message_node(
    node_id: str,
    message: str,
    wait_for_response: bool = True,
) -> dict:
    return {
        "id": node_id,
        "type": "message",
        "data": {"message": message, "waitForResponse": wait_for_response},
        "position": {"x": 0, "y": 100},
    }


def _collect_node(
    node_id: str,
    variable_name: str,
    variable_type: str = "text",
    prompt: str = "",
    retry_message: str = "No entendí, ¿puedes repetirlo?",
    max_retries: int = 3,
) -> dict:
    return {
        "id": node_id,
        "type": "collectInput",
        "data": {
            "variableName": variable_name,
            "variableType": variable_type,
            "prompt": prompt or f"¿Cuál es tu {variable_name}?",
            "retryMessage": retry_message,
            "maxRetries": max_retries,
        },
        "position": {"x": 0, "y": 200},
    }


def _condition_node(
    node_id: str,
    conditions: list[dict],
    default_handle: str = "default",
) -> dict:
    return {
        "id": node_id,
        "type": "condition",
        "data": {
            "conditions": conditions,
            "defaultHandleId": default_handle,
        },
        "position": {"x": 0, "y": 300},
    }


def _action_node(
    node_id: str,
    action_type: str,
    parameters: dict | None = None,
    result_variable: str | None = None,
) -> dict:
    return {
        "id": node_id,
        "type": "action",
        "data": {
            "actionType": action_type,
            "parameters": parameters or {},
            "resultVariable": result_variable,
            "onFailureMessage": "Hubo un error.",
        },
        "position": {"x": 0, "y": 400},
    }


def _end_node(node_id: str = "end-1", message: str = "Adiós", hangup: bool = False) -> dict:
    return {
        "id": node_id,
        "type": "end",
        "data": {"message": message, "hangup": hangup},
        "position": {"x": 0, "y": 500},
    }


def _transfer_node(
    node_id: str = "transfer-1",
    message: str = "Te voy a transferir",
    transfer_number: str = "+525551234567",
) -> dict:
    return {
        "id": node_id,
        "type": "transfer",
        "data": {"message": message, "transferNumber": transfer_number},
        "position": {"x": 0, "y": 500},
    }


def _wait_node(
    node_id: str = "wait-1",
    seconds: int = 3,
    message: str = "",
) -> dict:
    return {
        "id": node_id,
        "type": "wait",
        "data": {"seconds": seconds, "message": message},
        "position": {"x": 0, "y": 350},
    }


def _edge(source: str, target: str, source_handle: str = "default") -> dict:
    return {
        "id": f"e-{source}-{target}",
        "source": source,
        "target": target,
        "sourceHandle": source_handle,
    }


# ── Tests ────────────────────────────────────────────────


class TestFlowStart:
    def test_start_initializes_state(self) -> None:
        flow = _make_flow(
            [_start_node(), _end_node()],
            [_edge("start-1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()

        assert state.current_node_id == "start-1"
        assert state.variables == {}
        assert state.history == ["start-1"]
        assert state.retry_count == 0
        assert not state.completed

    def test_start_greeting(self) -> None:
        flow = _make_flow(
            [_start_node(greeting="¡Hola! Soy Dr. García."), _end_node()],
            [_edge("start-1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        greeting = engine.get_greeting(state)

        assert greeting == "¡Hola! Soy Dr. García."

    def test_no_start_node_raises(self) -> None:
        flow = _make_flow([_end_node()], [])
        engine = FlowEngine(flow)

        with pytest.raises(ValueError, match="nodo de inicio"):
            engine.start()


class TestAdvancement:
    def test_advance_through_message_nodes(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _message_node("msg-1", "Bienvenido a la clínica"),
                _message_node("msg-2", "¿En qué puedo ayudarle?"),
                _end_node(),
            ],
            [
                _edge("start-1", "msg-1"),
                _edge("msg-1", "msg-2"),
                _edge("msg-2", "end-1"),
            ],
        )
        engine = FlowEngine(flow)
        state = engine.start()

        # Avanzar desde start
        state, action = engine.process_user_input(state, "")
        assert state.current_node_id == "msg-1"
        assert action.type == "say"

        # Avanzar desde msg-1
        state, action = engine.process_user_input(state, "ok")
        assert state.current_node_id == "msg-2"
        assert action.type == "say"

        # Avanzar desde msg-2
        state, action = engine.process_user_input(state, "quiero una cita")
        assert state.current_node_id == "end-1"
        assert action.type == "end"


class TestCollectInput:
    def test_collect_input_extracts_variable(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _collect_node("c1", "nombre", "text", "¿Cómo te llamas?"),
                _end_node(),
            ],
            [_edge("start-1", "c1"), _edge("c1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()

        # Avanzar desde start a collect
        state, action = engine.process_user_input(state, "")
        assert state.current_node_id == "c1"
        assert action.type == "collect"

        # Dar el nombre
        state, action = engine.process_user_input(state, "Juan Pérez", "Juan Pérez")
        assert state.variables["nombre"] == "Juan Pérez"
        assert state.current_node_id == "end-1"

    def test_collect_phone_validation(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _collect_node("c1", "telefono", "phone", "¿Tu teléfono?"),
                _end_node(),
            ],
            [_edge("start-1", "c1"), _edge("c1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")

        # Teléfono inválido
        state, action = engine.process_user_input(state, "abc")
        assert action.type == "collect"  # Retry
        assert state.retry_count == 1

        # Teléfono válido
        state, action = engine.process_user_input(state, "9991234567")
        assert state.variables["telefono"] == "9991234567"

    def test_collect_max_retries(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _collect_node("c1", "email", "email", "¿Tu correo?", max_retries=2),
                _end_node(),
            ],
            [_edge("start-1", "c1"), _edge("c1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")

        # Fallar 2 veces → avanza automáticamente
        state, action = engine.process_user_input(state, "no es correo")
        assert action.type == "collect"
        state, action = engine.process_user_input(state, "tampoco")
        # Después de max_retries, avanza
        assert state.current_node_id == "end-1"


class TestConditionEvaluation:
    def test_condition_equals(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _collect_node("c1", "tipo", "text", "¿Consulta o urgencia?"),
                _condition_node(
                    "cond-1",
                    [
                        {"variable": "tipo", "operator": "equals", "value": "consulta", "handleId": "h-consulta"},
                        {"variable": "tipo", "operator": "equals", "value": "urgencia", "handleId": "h-urgencia"},
                    ],
                    default_handle="h-default",
                ),
                _message_node("msg-consulta", "Agendando consulta..."),
                _message_node("msg-urgencia", "Transfiriendo a urgencias..."),
                _message_node("msg-default", "No entendí la opción"),
                _end_node(),
            ],
            [
                _edge("start-1", "c1"),
                _edge("c1", "cond-1"),
                _edge("cond-1", "msg-consulta", "h-consulta"),
                _edge("cond-1", "msg-urgencia", "h-urgencia"),
                _edge("cond-1", "msg-default", "h-default"),
                _edge("msg-consulta", "end-1"),
                _edge("msg-urgencia", "end-1"),
                _edge("msg-default", "end-1"),
            ],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")  # start → c1

        # Responder "consulta"
        state, action = engine.process_user_input(state, "consulta", "consulta")
        # Condición evaluada, debería estar en msg-consulta
        assert state.current_node_id == "msg-consulta"
        assert action.type == "say"
        assert "consulta" in action.message.lower()

    def test_condition_not_empty(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _collect_node("c1", "dato", "text"),
                _condition_node(
                    "cond-1",
                    [{"variable": "dato", "operator": "not_empty", "value": "", "handleId": "h-yes"}],
                    default_handle="h-no",
                ),
                _message_node("msg-yes", "Dato recibido"),
                _message_node("msg-no", "Sin dato"),
                _end_node(),
            ],
            [
                _edge("start-1", "c1"),
                _edge("c1", "cond-1"),
                _edge("cond-1", "msg-yes", "h-yes"),
                _edge("cond-1", "msg-no", "h-no"),
                _edge("msg-yes", "end-1"),
                _edge("msg-no", "end-1"),
            ],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")
        state, action = engine.process_user_input(state, "algo", "algo")
        assert state.current_node_id == "msg-yes"

    def test_condition_default_fallback(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _collect_node("c1", "opcion", "text"),
                _condition_node(
                    "cond-1",
                    [{"variable": "opcion", "operator": "equals", "value": "A", "handleId": "h-a"}],
                    default_handle="h-default",
                ),
                _message_node("msg-a", "Opción A"),
                _message_node("msg-default", "Opción por defecto"),
                _end_node(),
            ],
            [
                _edge("start-1", "c1"),
                _edge("c1", "cond-1"),
                _edge("cond-1", "msg-a", "h-a"),
                _edge("cond-1", "msg-default", "h-default"),
                _edge("msg-a", "end-1"),
                _edge("msg-default", "end-1"),
            ],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")
        state, action = engine.process_user_input(state, "X", "X")  # No coincide con "A"
        assert state.current_node_id == "msg-default"

    def test_condition_gt_lt(self) -> None:
        engine = FlowEngine({"nodes": [], "edges": []})
        assert engine._eval_operator("10", "gt", "5")
        assert not engine._eval_operator("3", "gt", "5")
        assert engine._eval_operator("3", "lt", "5")
        assert not engine._eval_operator("10", "lt", "5")


class TestInterpolation:
    def test_interpolate_variables(self) -> None:
        engine = FlowEngine({"nodes": [], "edges": []})
        result = engine._interpolate(
            "Hola {{nombre}}, tu cita es el {{fecha}}",
            {"nombre": "Juan", "fecha": "lunes"},
        )
        assert result == "Hola Juan, tu cita es el lunes"

    def test_interpolate_missing_variable(self) -> None:
        engine = FlowEngine({"nodes": [], "edges": []})
        result = engine._interpolate("Hola {{nombre}}", {})
        assert result == "Hola {{nombre}}"  # Se queda tal cual

    def test_interpolate_empty_template(self) -> None:
        engine = FlowEngine({"nodes": [], "edges": []})
        assert engine._interpolate("", {"x": "1"}) == ""


class TestValidation:
    def test_validate_flow_no_start(self) -> None:
        flow = _make_flow([_end_node()], [])
        valid, errors, warnings = FlowEngine.validate_flow(flow)
        assert not valid
        assert any("Inicio" in e for e in errors)

    def test_validate_flow_no_end(self) -> None:
        flow = _make_flow([_start_node()], [])
        valid, errors, warnings = FlowEngine.validate_flow(flow)
        # No end es un warning, no un error
        assert any("Fin" in w for w in warnings)
        # Pero sin salida del start es error
        assert any("salida" in e for e in errors)

    def test_validate_flow_orphan_nodes(self) -> None:
        flow = _make_flow(
            [_start_node(), _message_node("orphan", "solo"), _end_node()],
            [_edge("start-1", "end-1")],
        )
        valid, errors, warnings = FlowEngine.validate_flow(flow)
        assert any("no está conectado" in w for w in warnings)

    def test_validate_flow_valid(self) -> None:
        flow = _make_flow(
            [_start_node(), _message_node("m1", "Hola"), _end_node()],
            [_edge("start-1", "m1"), _edge("m1", "end-1")],
        )
        valid, errors, warnings = FlowEngine.validate_flow(flow)
        assert valid
        assert len(errors) == 0

    def test_validate_collect_without_variable(self) -> None:
        node = _collect_node("c1", "", "text")  # Sin variable name
        flow = _make_flow(
            [_start_node(), node, _end_node()],
            [_edge("start-1", "c1"), _edge("c1", "end-1")],
        )
        valid, errors, warnings = FlowEngine.validate_flow(flow)
        assert not valid
        assert any("variable" in e.lower() for e in errors)

    def test_validate_empty_flow(self) -> None:
        valid, errors, warnings = FlowEngine.validate_flow({"nodes": [], "edges": []})
        assert not valid
        assert any("no tiene nodos" in e for e in errors)


class TestSystemPrompt:
    def test_build_system_prompt_message_node(self) -> None:
        flow = _make_flow(
            [_start_node(), _message_node("m1", "Bienvenido al consultorio"), _end_node()],
            [_edge("start-1", "m1"), _edge("m1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")  # start → m1

        prompt = engine.build_system_prompt(state, "Eres un asistente.")
        assert "Eres un asistente." in prompt
        assert "Bienvenido al consultorio" in prompt
        assert "MENSAJE" in prompt

    def test_build_system_prompt_collect_node(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _collect_node("c1", "nombre", "text", "¿Cómo te llamas?"),
                _end_node(),
            ],
            [_edge("start-1", "c1"), _edge("c1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")

        prompt = engine.build_system_prompt(state)
        assert "RECOPILAR DATO" in prompt
        assert "nombre" in prompt

    def test_build_system_prompt_with_variables(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _message_node("m1", "Hola {{nombre}}, confirmamos tu cita"),
                _end_node(),
            ],
            [_edge("start-1", "m1"), _edge("m1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state.variables["nombre"] = "María"
        state, _ = engine.process_user_input(state, "")

        prompt = engine.build_system_prompt(state)
        assert "María" in prompt


class TestTransferNode:
    def test_transfer_completes_flow(self) -> None:
        flow = _make_flow(
            [_start_node(), _transfer_node()],
            [_edge("start-1", "transfer-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()

        state, action = engine.process_user_input(state, "")
        assert state.current_node_id == "transfer-1"
        assert action.type == "transfer"
        assert action.transfer_number == "+525551234567"
        assert "transferir" in action.message.lower()

    def test_transfer_with_interpolation(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _collect_node("c1", "nombre", "text"),
                _transfer_node(message="Transferiendo a {{nombre}}"),
            ],
            [_edge("start-1", "c1"), _edge("c1", "transfer-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")
        state, _ = engine.process_user_input(state, "Carlos", "Carlos")
        state, action = engine.process_user_input(state, "")
        assert "Carlos" in action.message

    def test_transfer_system_prompt(self) -> None:
        flow = _make_flow(
            [_start_node(), _transfer_node()],
            [_edge("start-1", "transfer-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")

        prompt = engine.build_system_prompt(state)
        assert "TRANSFERIR" in prompt

    def test_validate_transfer_without_number(self) -> None:
        node = _transfer_node(transfer_number="")
        flow = _make_flow(
            [_start_node(), node],
            [_edge("start-1", "transfer-1")],
        )
        _, _, warnings = FlowEngine.validate_flow(flow)
        assert any("transferencia" in w.lower() for w in warnings)


class TestWaitNode:
    def test_wait_then_advance(self) -> None:
        flow = _make_flow(
            [
                _start_node(),
                _wait_node(seconds=5, message="Un momento..."),
                _end_node(),
            ],
            [_edge("start-1", "wait-1"), _edge("wait-1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start()

        # Start → wait
        state, action = engine.process_user_input(state, "")
        assert state.current_node_id == "wait-1"
        assert action.type == "wait"
        assert action.wait_seconds == 5

        # Wait → advance → end
        state, action = engine.process_user_input(state, "")
        assert state.current_node_id == "end-1"
        assert state.completed

    def test_wait_action_for_current_node(self) -> None:
        flow = _make_flow(
            [_start_node(), _wait_node(seconds=3, message="Espere..."), _end_node()],
            [_edge("start-1", "wait-1"), _edge("wait-1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = FlowState(current_node_id="wait-1")

        action = engine._action_for_current_node(state)
        assert action.type == "wait"
        assert action.wait_seconds == 3
        assert action.message == "Espere..."

    def test_wait_system_prompt(self) -> None:
        flow = _make_flow(
            [_start_node(), _wait_node(seconds=2, message="Procesando...")],
            [_edge("start-1", "wait-1")],
        )
        engine = FlowEngine(flow)
        state = FlowState(current_node_id="wait-1")

        prompt = engine.build_system_prompt(state)
        assert "ESPERA" in prompt
        assert "Procesando" in prompt

    def test_wait_silent(self) -> None:
        flow = _make_flow(
            [_start_node(), _wait_node(seconds=2, message="")],
            [_edge("start-1", "wait-1")],
        )
        engine = FlowEngine(flow)
        state = FlowState(current_node_id="wait-1")

        prompt = engine.build_system_prompt(state)
        assert "silenciosa" in prompt.lower()


class TestCycleDetection:
    def test_simple_cycle_detected(self) -> None:
        """Ciclo directo: A → B → A."""
        flow = _make_flow(
            [
                _start_node(),
                _message_node("m1", "Hola"),
                _message_node("m2", "Loop"),
                _end_node(),
            ],
            [
                _edge("start-1", "m1"),
                _edge("m1", "m2"),
                _edge("m2", "m1"),  # Ciclo
                _edge("m1", "end-1"),
            ],
        )
        valid, errors, _ = FlowEngine.validate_flow(flow)
        assert not valid
        assert any("Ciclo" in e or "ciclo" in e.lower() for e in errors)

    def test_multi_hop_cycle_detected(self) -> None:
        """Ciclo multi-hop: A → B → C → A."""
        flow = _make_flow(
            [
                _start_node(),
                _message_node("m1", "A"),
                _message_node("m2", "B"),
                _message_node("m3", "C"),
                _end_node(),
            ],
            [
                _edge("start-1", "m1"),
                _edge("m1", "m2"),
                _edge("m2", "m3"),
                _edge("m3", "m1"),  # Ciclo de 3 nodos
            ],
        )
        valid, errors, _ = FlowEngine.validate_flow(flow)
        assert not valid
        assert any("Ciclo" in e or "ciclo" in e.lower() for e in errors)

    def test_no_cycle_valid(self) -> None:
        """Flujo lineal sin ciclos debe ser válido."""
        flow = _make_flow(
            [_start_node(), _message_node("m1", "Hola"), _end_node()],
            [_edge("start-1", "m1"), _edge("m1", "end-1")],
        )
        valid, errors, _ = FlowEngine.validate_flow(flow)
        assert valid
        assert not any("Ciclo" in e for e in errors)


class TestRuntimeLoopProtection:
    def test_step_count_limit_aborts(self) -> None:
        """Flujo con ciclo en runtime debe abortar tras MAX_STEPS."""
        # Crear ciclo: start → m1 → m2 → m1 (loop)
        flow = _make_flow(
            [
                _start_node(),
                _message_node("m1", "A", wait_for_response=True),
                _message_node("m2", "B", wait_for_response=False),
            ],
            [
                _edge("start-1", "m1"),
                _edge("m1", "m2"),
                _edge("m2", "m1"),  # Ciclo
            ],
        )
        engine = FlowEngine(flow)
        state = engine.start()

        # Avanzar muchas veces — no debe colgar, debe abortar
        for _ in range(100):
            if state.completed:
                break
            state, action = engine.process_user_input(state, "ok")

        assert state.completed
        assert state.step_count > 0


class TestActionHandles:
    def test_action_success_handle(self) -> None:
        """Acción exitosa avanza por handle 'success'."""
        flow = _make_flow(
            [
                _start_node(),
                _action_node("a1", "search_knowledge", result_variable="resultado"),
                _message_node("m-ok", "Exito"),
                _message_node("m-err", "Error"),
                _end_node(),
            ],
            [
                _edge("start-1", "a1"),
                _edge("a1", "m-ok", "success"),
                _edge("a1", "m-err", "failure"),
                _edge("m-ok", "end-1"),
                _edge("m-err", "end-1"),
            ],
        )
        engine = FlowEngine(flow, enabled_tools=["search_knowledge"])
        state = engine.start()
        state, _ = engine.process_user_input(state, "")  # start → a1

        # Acción exitosa con valor extraído
        state, action = engine.process_user_input(state, "", "valor_encontrado")
        assert state.current_node_id == "m-ok"
        assert state.variables["resultado"] == "valor_encontrado"

    def test_action_failure_handle(self) -> None:
        """Acción fallida avanza por handle 'failure'."""
        flow = _make_flow(
            [
                _start_node(),
                _action_node("a1", "search_knowledge", result_variable="resultado"),
                _message_node("m-ok", "Exito"),
                _message_node("m-err", "Error"),
                _end_node(),
            ],
            [
                _edge("start-1", "a1"),
                _edge("a1", "m-ok", "success"),
                _edge("a1", "m-err", "failure"),
                _edge("m-ok", "end-1"),
                _edge("m-err", "end-1"),
            ],
        )
        engine = FlowEngine(flow, enabled_tools=["search_knowledge"])
        state = engine.start()
        state, _ = engine.process_user_input(state, "")  # start → a1

        # Acción fallida
        state, action = engine.process_user_input(state, "", "_error_")
        assert state.current_node_id == "m-err"

    def test_action_default_fallback(self) -> None:
        """Acción sin handles success/failure usa fallback al primer edge."""
        flow = _make_flow(
            [
                _start_node(),
                _action_node("a1", "search_knowledge"),
                _end_node(),
            ],
            [
                _edge("start-1", "a1"),
                _edge("a1", "end-1"),  # Solo handle "default"
            ],
        )
        engine = FlowEngine(flow, enabled_tools=["search_knowledge"])
        state = engine.start()
        state, _ = engine.process_user_input(state, "")

        # Sin extracted_value → handle "default", fallback al primer edge
        state, action = engine.process_user_input(state, "")
        assert state.current_node_id == "end-1"


class TestCollectInputMaxRetries:
    def test_max_retries_handle(self) -> None:
        """CollectInput alcanza maxRetries y avanza por handle 'maxRetries'."""
        flow = _make_flow(
            [
                _start_node(),
                _collect_node("c1", "email", "email", "Tu correo?", max_retries=2),
                _message_node("m-ok", "Gracias"),
                _message_node("m-retry", "No pudimos obtener tu correo"),
                _end_node(),
            ],
            [
                _edge("start-1", "c1"),
                _edge("c1", "m-ok", "default"),
                _edge("c1", "m-retry", "maxRetries"),
                _edge("m-ok", "end-1"),
                _edge("m-retry", "end-1"),
            ],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")  # start → c1

        # Fallar 2 veces
        state, action = engine.process_user_input(state, "no es correo")
        assert action.type == "collect"  # Retry
        state, action = engine.process_user_input(state, "tampoco")
        # Después de maxRetries, avanza por handle "maxRetries"
        assert state.current_node_id == "m-retry"

    def test_max_retries_fallback_without_handle(self) -> None:
        """CollectInput maxRetries sin handle específico usa fallback."""
        flow = _make_flow(
            [
                _start_node(),
                _collect_node("c1", "email", "email", "Tu correo?", max_retries=1),
                _end_node(),
            ],
            [
                _edge("start-1", "c1"),
                _edge("c1", "end-1"),  # Solo handle "default"
            ],
        )
        engine = FlowEngine(flow)
        state = engine.start()
        state, _ = engine.process_user_input(state, "")
        state, _ = engine.process_user_input(state, "no-correo")
        # Fallback al primer edge
        assert state.current_node_id == "end-1"


class TestInitialVariables:
    def test_start_with_initial_variables(self) -> None:
        """start() acepta initial_variables y las inyecta en el estado."""
        flow = _make_flow(
            [
                _start_node(greeting="Hola {{caller_number}}"),
                _end_node(),
            ],
            [_edge("start-1", "end-1")],
        )
        engine = FlowEngine(flow)
        state = engine.start(initial_variables={"caller_number": "+525551234567"})

        assert state.variables["caller_number"] == "+525551234567"
        greeting = engine.get_greeting(state)
        assert "+525551234567" in greeting



    def test_full_flow_dental_appointment(self) -> None:
        """Test de integración: flujo completo de cita dental."""
        flow = _make_flow(
            [
                _start_node(greeting="Hola, clínica dental del Dr. García"),
                _collect_node("c-nombre", "nombre", "text", "¿A nombre de quién la cita?"),
                _collect_node("c-tel", "telefono", "phone", "¿Su número de teléfono?"),
                _collect_node(
                    "c-tipo", "tipo_cita", "yes_no",
                    "¿Es su primera vez con nosotros?",
                ),
                _condition_node(
                    "cond-tipo",
                    [
                        {
                            "variable": "tipo_cita",
                            "operator": "equals",
                            "value": "sí",
                            "handleId": "h-nuevo",
                        },
                    ],
                    default_handle="h-recurrente",
                ),
                _message_node("msg-nuevo", "Perfecto, como paciente nuevo le daremos una cita más larga."),
                _message_node("msg-recurrente", "Muy bien, le agendaremos su cita regular."),
                _end_node(message="Gracias {{nombre}}, le confirmaremos por teléfono al {{telefono}}."),
            ],
            [
                _edge("start-1", "c-nombre"),
                _edge("c-nombre", "c-tel"),
                _edge("c-tel", "c-tipo"),
                _edge("c-tipo", "cond-tipo"),
                _edge("cond-tipo", "msg-nuevo", "h-nuevo"),
                _edge("cond-tipo", "msg-recurrente", "h-recurrente"),
                _edge("msg-nuevo", "end-1"),
                _edge("msg-recurrente", "end-1"),
            ],
        )

        engine = FlowEngine(flow, enabled_tools=["search_knowledge"])
        state = engine.start()

        # Verificar greeting
        assert "Dr. García" in engine.get_greeting(state)

        # Start → primer collect
        state, action = engine.process_user_input(state, "")
        assert state.current_node_id == "c-nombre"
        assert action.type == "collect"

        # Dar nombre
        state, action = engine.process_user_input(state, "Ana López", "Ana López")
        assert state.variables["nombre"] == "Ana López"
        assert state.current_node_id == "c-tel"

        # Dar teléfono
        state, action = engine.process_user_input(state, "999 123 4567", "9991234567")
        assert state.variables["telefono"] == "9991234567"
        assert state.current_node_id == "c-tipo"

        # Responder sí (primera vez)
        state, action = engine.process_user_input(state, "sí", "sí")
        assert state.variables["tipo_cita"] == "sí"
        # Debería haber pasado por condición → msg-nuevo
        assert state.current_node_id == "msg-nuevo"
        assert action.type == "say"

        # Avanzar desde msg-nuevo → end
        state, action = engine.process_user_input(state, "ok")
        assert state.current_node_id == "end-1"
        assert state.completed
        assert action.type == "end"
        assert "Ana López" in action.message
        assert "9991234567" in action.message
