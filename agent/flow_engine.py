"""Motor de ejecución de flujos de conversación visual.

Parsea el JSON de React Flow (nodos + edges) y genera prompts dinámicos
para guiar al LLM paso a paso según el flujo diseñado por el usuario.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


MAX_STEPS = 50  # Protección contra loops infinitos en runtime


@dataclass
class FlowState:
    """Estado actual del flujo durante una llamada."""

    current_node_id: str
    variables: dict[str, Any] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    retry_count: int = 0
    awaiting_input: bool = False
    completed: bool = False
    step_count: int = 0


@dataclass
class FlowAction:
    """Acción que el engine indica al agente que debe ejecutar."""

    type: str  # "say", "collect", "action", "end", "advance", "transfer", "wait"
    message: str | None = None
    tool_name: str | None = None
    tool_params: dict[str, Any] = field(default_factory=dict)
    hangup: bool = False
    transfer_number: str | None = None
    wait_seconds: int = 0


class FlowEngine:
    """Parsea y ejecuta flujos de conversación definidos en React Flow."""

    def __init__(self, flow_json: dict, enabled_tools: list[str] | None = None) -> None:
        self._nodes: dict[str, dict] = {}
        self._edges: list[dict] = []
        self._adjacency: dict[str, list[dict]] = {}  # node_id → [edges salientes]
        self._enabled_tools = enabled_tools or []

        self._parse(flow_json)

    def _parse(self, flow_json: dict) -> None:
        """Parsea nodos y edges del JSON de React Flow."""
        for node in flow_json.get("nodes", []):
            self._nodes[node["id"]] = node

        self._edges = flow_json.get("edges", [])

        # Construir mapa de adyacencia (edges salientes por nodo)
        for edge in self._edges:
            source = edge["source"]
            if source not in self._adjacency:
                self._adjacency[source] = []
            self._adjacency[source].append(edge)

    def start(self, initial_variables: dict[str, Any] | None = None) -> FlowState:
        """Inicializa el estado del flujo encontrando el nodo Start."""
        start_node = self._find_start_node()
        if not start_node:
            raise ValueError("El flujo no tiene un nodo de inicio (start)")

        state = FlowState(current_node_id=start_node["id"])
        state.history.append(start_node["id"])
        if initial_variables:
            state.variables.update(initial_variables)
        return state

    def get_greeting(self, state: FlowState) -> str:
        """Retorna el greeting del nodo Start."""
        node = self._nodes.get(state.current_node_id)
        if not node:
            return ""
        data = node.get("data", {})
        return self._interpolate(data.get("greeting", ""), state.variables)

    def build_system_prompt(self, state: FlowState, base_rules: str = "") -> str:
        """Genera un system prompt dinámico según el nodo actual del flujo."""
        # Si se alcanzó MAX_STEPS, generar prompt de despedida
        if state.completed and state.variables.get("_max_steps_reached"):
            parts = [base_rules] if base_rules else []
            parts.append(
                "\n\n## Flujo de conversación — Límite alcanzado\n"
                "El flujo ha llegado al máximo de pasos permitidos. "
                "Despide al usuario amablemente e informa que un agente humano "
                "lo contactará para continuar con su solicitud."
            )
            return "\n".join(parts)

        node = self._nodes.get(state.current_node_id)
        if not node:
            return base_rules

        node_type = node.get("type", "")
        data = node.get("data", {})
        prompt_parts = [base_rules] if base_rules else []

        prompt_parts.append(
            "\n\n## Flujo de conversación — Instrucción actual\n"
            "Estás siguiendo un flujo de conversación predefinido. "
            "Sigue la instrucción del paso actual de forma NATURAL y conversacional."
        )

        if node_type == "start":
            greeting = self._interpolate(data.get("greeting", ""), state.variables)
            prompt_parts.append(f"\n**Paso actual**: INICIO\nSaluda al usuario con: {greeting}")

        elif node_type == "message":
            message = self._interpolate(data.get("message", ""), state.variables)
            prompt_parts.append(f"\n**Paso actual**: MENSAJE\nDi al usuario: {message}")
            if data.get("waitForResponse"):
                prompt_parts.append("Espera la respuesta del usuario antes de continuar.")
            else:
                prompt_parts.append("Continúa inmediatamente con el siguiente paso.")

        elif node_type == "collectInput":
            var_name = data.get("variableName", "dato")
            var_type = data.get("variableType", "text")
            prompt_text = self._interpolate(
                data.get("prompt", f"¿Cuál es tu {var_name}?"), state.variables
            )
            retry_msg = data.get("retryMessage", "")
            max_retries = data.get("maxRetries", 3)

            type_instructions = {
                "text": "Acepta cualquier texto.",
                "phone": "Debe ser un número de teléfono válido (10 dígitos México, o con código de país).",
                "email": "Debe ser un correo electrónico válido con @.",
                "date": "Debe ser una fecha. Acepta formatos naturales como 'mañana', 'el lunes', '15 de marzo'.",
                "time": "Debe ser una hora. Acepta formatos como '3 de la tarde', '15:00', '10am'.",
                "number": "Debe ser un número.",
                "yes_no": "Debe ser una respuesta de sí o no.",
            }

            prompt_parts.append(
                f"\n**Paso actual**: RECOPILAR DATO\n"
                f"Necesitas obtener: **{var_name}** (tipo: {var_type})\n"
                f"Pregunta: {prompt_text}\n"
                f"Validación: {type_instructions.get(var_type, 'Acepta cualquier texto.')}\n"
            )
            if state.retry_count > 0 and retry_msg:
                prompt_parts.append(
                    f"El usuario ya intentó {state.retry_count} vez/veces. "
                    f"Usa este mensaje de reintento: {retry_msg}"
                )
            if state.retry_count >= max_retries:
                prompt_parts.append(
                    f"Se alcanzó el máximo de {max_retries} intentos. Avanza al siguiente paso."
                )

            prompt_parts.append(
                f"\nIMPORTANTE: Cuando el usuario dé el dato, extrae el valor de '{var_name}' "
                f"y confirma lo que entendiste. Si el dato es válido, continúa."
            )

        elif node_type == "action":
            action_type = data.get("actionType", "")
            params = data.get("parameters", {})
            fail_msg = data.get("onFailureMessage", "Hubo un error, disculpa.")

            # Determinar nombre de herramienta para el prompt
            if action_type.startswith("api:"):
                api_name = action_type[4:]  # Quitar prefijo "api:"
                tool_display = f"call_api (integración: {api_name})"
            elif action_type.startswith("mcp:"):
                tool_display = action_type
            else:
                tool_display = action_type

            prompt_parts.append(
                f"\n**Paso actual**: ACCIÓN\n"
                f"Ejecuta la herramienta: **{tool_display}**\n"
            )
            if params:
                params_interpolated = {
                    k: self._interpolate(str(v), state.variables)
                    for k, v in params.items()
                }
                prompt_parts.append(f"Parámetros: {params_interpolated}")
            prompt_parts.append(
                f"Si falla, di: {fail_msg}\n"
                "Informa al usuario del resultado y continúa."
            )

        elif node_type == "transfer":
            message = self._interpolate(data.get("message", ""), state.variables)
            number = data.get("transferNumber", "")
            prompt_parts.append(
                f"\n**Paso actual**: TRANSFERIR\n"
                f"Informa al usuario: {message}\n"
                f"La llamada será transferida a: {number}\n"
                f"Usa la herramienta transfer_to_human con el motivo de la transferencia."
            )

        elif node_type == "wait":
            seconds = data.get("seconds", 2)
            message = self._interpolate(data.get("message", ""), state.variables)
            if message:
                prompt_parts.append(
                    f"\n**Paso actual**: ESPERA\n"
                    f"Di al usuario: {message}\n"
                    f"Habrá una pausa de {seconds} segundos."
                )
            else:
                prompt_parts.append(
                    f"\n**Paso actual**: ESPERA\n"
                    f"Pausa silenciosa de {seconds} segundos. No digas nada."
                )

        elif node_type == "end":
            message = self._interpolate(data.get("message", ""), state.variables)
            prompt_parts.append(
                f"\n**Paso actual**: FIN\n"
                f"Despide al usuario con: {message}"
            )
            if data.get("hangup"):
                prompt_parts.append("Después de despedirte, la llamada terminará.")

        # Agregar variables recopiladas al contexto
        if state.variables:
            vars_str = ", ".join(f"{k}={v}" for k, v in state.variables.items())
            prompt_parts.append(f"\n**Datos recopilados**: {vars_str}")

        return "\n".join(prompt_parts)

    def process_user_input(
        self,
        state: FlowState,
        user_text: str,
        extracted_value: str | None = None,
    ) -> tuple[FlowState, FlowAction]:
        """Procesa la respuesta del usuario y avanza el flujo."""
        node = self._nodes.get(state.current_node_id)
        if not node:
            state.completed = True
            return state, FlowAction(type="end", message="Flujo completado.")

        node_type = node.get("type", "")
        data = node.get("data", {})

        if node_type == "start":
            # Despues del saludo, avanzar al siguiente nodo
            state = self._advance(state, "default")
            return state, self._action_for_current_node(state)

        elif node_type == "message":
            if data.get("waitForResponse"):
                # Esperaba respuesta, avanzar
                state = self._advance(state, "default")
                return state, self._action_for_current_node(state)
            else:
                # Auto-avance (no espera respuesta)
                state = self._advance(state, "default")
                return state, self._action_for_current_node(state)

        elif node_type == "collectInput":
            var_name = data.get("variableName", "dato")
            var_type = data.get("variableType", "text")
            max_retries = data.get("maxRetries", 3)

            # Usar valor extraído o el texto completo
            value = extracted_value or user_text

            # Validar según tipo
            if self._validate_input(value, var_type):
                state.variables[var_name] = value
                state.retry_count = 0
                # Si es yes_no, avanzar por handle específico
                if var_type == "yes_no":
                    normalized = value.lower().strip()
                    yes_defaults = {"sí", "si", "yes", "claro", "ok", "sale", "va"}
                    # Merge con keywords personalizadas del nodo
                    custom_yes = data.get("yesKeywords", "")
                    if custom_yes:
                        for kw in custom_yes.split(","):
                            kw = kw.strip().lower()
                            if kw:
                                yes_defaults.add(kw)
                    if normalized in yes_defaults:
                        state = self._advance(state, "yes")
                    else:
                        state = self._advance(state, "no")
                else:
                    state = self._advance(state, "default")
                return state, self._action_for_current_node(state)
            else:
                state.retry_count += 1
                if state.retry_count >= max_retries:
                    state.retry_count = 0
                    state = self._advance(state, "maxRetries")
                    return state, self._action_for_current_node(state)
                retry_msg = data.get("retryMessage", f"No entendí tu {var_name}, ¿puedes repetirlo?")
                return state, FlowAction(
                    type="collect",
                    message=self._interpolate(retry_msg, state.variables),
                )

        elif node_type == "action":
            # Despues de la acción, avanzar por success/failure
            result_var = data.get("resultVariable")
            if result_var and extracted_value:
                state.variables[result_var] = extracted_value
            # Determinar handle: success si hay valor extraído válido, failure si error
            if extracted_value and extracted_value != "_error_":
                handle = "success"
            elif extracted_value == "_error_":
                handle = "failure"
            else:
                handle = "default"
            state = self._advance(state, handle)
            return state, self._action_for_current_node(state)

        elif node_type == "condition":
            # Las condiciones se evalúan automáticamente
            handle = self._evaluate_conditions(node, state)
            state = self._advance(state, handle)
            return state, self._action_for_current_node(state)

        elif node_type == "transfer":
            state.completed = True
            return state, FlowAction(
                type="transfer",
                message=self._interpolate(data.get("message", ""), state.variables),
                transfer_number=data.get("transferNumber", ""),
            )

        elif node_type == "wait":
            # Después de la espera, avanzar
            state = self._advance(state, "default")
            return state, self._action_for_current_node(state)

        elif node_type == "end":
            state.completed = True
            return state, FlowAction(
                type="end",
                message=self._interpolate(data.get("message", ""), state.variables),
                hangup=data.get("hangup", False),
            )

        # Fallback
        state = self._advance(state, "default")
        return state, self._action_for_current_node(state)

    def get_tools_for_current_node(self, state: FlowState) -> list[str]:
        """Retorna las tools habilitadas para el nodo actual."""
        node = self._nodes.get(state.current_node_id)
        if not node:
            return []

        node_type = node.get("type", "")
        data = node.get("data", {})

        if node_type == "action":
            action_type = data.get("actionType", "")
            if action_type.startswith("api:"):
                return ["call_api"]
            if action_type in self._enabled_tools:
                return [action_type]
        # search_knowledge siempre disponible si está habilitada
        if "search_knowledge" in self._enabled_tools:
            return ["search_knowledge"]
        return []

    def _advance(self, state: FlowState, handle: str) -> FlowState:
        """Navega al siguiente nodo según el handle de salida."""
        state.step_count += 1
        if state.step_count > MAX_STEPS:
            logger.warning(
                "Flujo abortado: se alcanzó el límite de %d pasos (posible loop infinito)",
                MAX_STEPS,
            )
            state.completed = True
            state.variables["_max_steps_reached"] = "true"
            return state

        edges = self._adjacency.get(state.current_node_id, [])

        # Buscar edge que coincida con el handle
        next_node_id: str | None = None
        for edge in edges:
            source_handle = edge.get("sourceHandle", "default")
            if source_handle == handle:
                next_node_id = edge["target"]
                break

        # Fallback: si no hay edge con el handle exacto, tomar el primero
        if not next_node_id and edges:
            next_node_id = edges[0]["target"]

        if not next_node_id:
            state.completed = True
            return state

        state.current_node_id = next_node_id
        state.history.append(next_node_id)
        state.awaiting_input = False

        # Auto-avanzar nodos de condición (se evalúan sin input del usuario)
        next_node = self._nodes.get(next_node_id)
        if next_node and next_node.get("type") == "condition":
            cond_handle = self._evaluate_conditions(next_node, state)
            return self._advance(state, cond_handle)

        return state

    def _evaluate_conditions(self, node: dict, state: FlowState) -> str:
        """Evalúa condiciones de un nodo condition, retorna el handle ganador.

        Variables de sistema disponibles (prefijo _):
        - _turn_count: número de pasos ejecutados
        - _sentiment: último sentimiento detectado (si está activo)
        - _sentiment_score: score promedio de sentimiento (-2 a +2)
        - _consecutive_negative: turnos negativos consecutivos
        Todas las variables del flow están accesibles por su nombre.
        """
        data = node.get("data", {})
        conditions = data.get("conditions", [])

        # Variables de sistema inyectadas automáticamente
        system_vars = {
            "_turn_count": str(state.step_count),
        }
        # Merge: variables del flow + sistema (flow tiene prioridad)
        all_vars = {**system_vars, **state.variables}

        for cond in conditions:
            variable = cond.get("variable", "")
            operator = cond.get("operator", "equals")
            value = cond.get("value", "")
            handle_id = cond.get("handleId", "default")

            var_value = str(all_vars.get(variable, ""))

            if self._eval_operator(var_value, operator, value):
                return handle_id

        # Retornar default handle
        return data.get("defaultHandleId", "default")

    def _eval_operator(self, var_value: str, operator: str, target: str) -> bool:
        """Evalúa un operador de comparación."""
        if operator == "equals":
            return var_value.lower().strip() == target.lower().strip()
        elif operator == "not_equals":
            return var_value.lower().strip() != target.lower().strip()
        elif operator == "contains":
            return target.lower() in var_value.lower()
        elif operator == "not_contains":
            return target.lower() not in var_value.lower()
        elif operator == "starts_with":
            return var_value.lower().strip().startswith(target.lower().strip())
        elif operator == "ends_with":
            return var_value.lower().strip().endswith(target.lower().strip())
        elif operator == "not_empty":
            return bool(var_value.strip())
        elif operator == "empty":
            return not var_value.strip()
        elif operator == "gt":
            try:
                return float(var_value) > float(target)
            except (ValueError, TypeError):
                return False
        elif operator == "gte":
            try:
                return float(var_value) >= float(target)
            except (ValueError, TypeError):
                return False
        elif operator == "lt":
            try:
                return float(var_value) < float(target)
            except (ValueError, TypeError):
                return False
        elif operator == "lte":
            try:
                return float(var_value) <= float(target)
            except (ValueError, TypeError):
                return False
        elif operator == "regex":
            try:
                return bool(re.search(target, var_value, re.IGNORECASE))
            except re.error:
                logger.warning("Regex inválido en condición: %s", target)
                return False
        elif operator == "in":
            # target es lista separada por comas: "a,b,c"
            options = [o.strip().lower() for o in target.split(",")]
            return var_value.lower().strip() in options
        elif operator == "not_in":
            options = [o.strip().lower() for o in target.split(",")]
            return var_value.lower().strip() not in options
        return False

    def _validate_input(self, value: str, var_type: str) -> bool:
        """Valida un input del usuario según el tipo esperado."""
        value = value.strip()
        if not value:
            return False

        if var_type == "text":
            return True
        elif var_type == "phone":
            digits = re.sub(r"[^\d]", "", value)
            return len(digits) >= 7
        elif var_type == "email":
            return "@" in value and "." in value
        elif var_type == "number":
            try:
                float(re.sub(r"[^\d.\-]", "", value))
                return True
            except ValueError:
                return False
        elif var_type == "date":
            # Acepta casi todo ya que el LLM normaliza
            return len(value) >= 2
        elif var_type == "time":
            return len(value) >= 2
        elif var_type == "yes_no":
            return len(value) >= 1
        return True

    def _interpolate(self, template: str, variables: dict[str, Any]) -> str:
        """Reemplaza {{variable}} con valores del estado."""
        if not template:
            return template

        def replacer(match: re.Match) -> str:
            key = match.group(1).strip()
            return str(variables.get(key, match.group(0)))

        return re.sub(r"\{\{(\w+)\}\}", replacer, template)

    def _find_start_node(self) -> dict | None:
        """Busca el nodo de tipo 'start' en el flujo."""
        for node in self._nodes.values():
            if node.get("type") == "start":
                return node
        return None

    def _action_for_current_node(self, state: FlowState) -> FlowAction:
        """Genera la acción correspondiente al nodo actual."""
        if state.completed:
            return FlowAction(type="end")

        node = self._nodes.get(state.current_node_id)
        if not node:
            state.completed = True
            return FlowAction(type="end")

        node_type = node.get("type", "")
        data = node.get("data", {})

        if node_type == "message":
            state.awaiting_input = data.get("waitForResponse", False)
            return FlowAction(
                type="say",
                message=self._interpolate(data.get("message", ""), state.variables),
            )
        elif node_type == "collectInput":
            state.awaiting_input = True
            return FlowAction(
                type="collect",
                message=self._interpolate(data.get("prompt", ""), state.variables),
            )
        elif node_type == "action":
            return FlowAction(
                type="action",
                tool_name=data.get("actionType"),
                tool_params={
                    k: self._interpolate(str(v), state.variables)
                    for k, v in (data.get("parameters") or {}).items()
                },
            )
        elif node_type == "transfer":
            state.completed = True
            return FlowAction(
                type="transfer",
                message=self._interpolate(data.get("message", ""), state.variables),
                transfer_number=data.get("transferNumber", ""),
            )
        elif node_type == "wait":
            return FlowAction(
                type="wait",
                message=self._interpolate(data.get("message", ""), state.variables),
                wait_seconds=data.get("seconds", 2),
            )
        elif node_type == "end":
            state.completed = True
            return FlowAction(
                type="end",
                message=self._interpolate(data.get("message", ""), state.variables),
                hangup=data.get("hangup", False),
            )
        elif node_type == "condition":
            # Auto-evaluar condición y avanzar
            handle = self._evaluate_conditions(node, state)
            state = self._advance(state, handle)
            return self._action_for_current_node(state)

        return FlowAction(type="advance")

    @staticmethod
    def validate_flow(flow_json: dict) -> tuple[bool, list[str], list[str]]:
        """Validación estática del flujo. Retorna (valid, errors, warnings)."""
        errors: list[str] = []
        warnings: list[str] = []

        nodes = flow_json.get("nodes", [])
        edges = flow_json.get("edges", [])

        if not nodes:
            errors.append("El flujo no tiene nodos.")
            return False, errors, warnings

        node_ids = {n["id"] for n in nodes}
        node_types = {n["id"]: n.get("type", "") for n in nodes}

        # Verificar que hay un nodo Start
        start_nodes = [n for n in nodes if n.get("type") == "start"]
        if not start_nodes:
            errors.append("El flujo necesita un nodo de Inicio (Start).")
        elif len(start_nodes) > 1:
            errors.append("El flujo solo puede tener un nodo de Inicio.")

        # Verificar que hay al menos un nodo End
        end_nodes = [n for n in nodes if n.get("type") == "end"]
        if not end_nodes:
            warnings.append("El flujo no tiene nodo de Fin (End). La conversación podría no terminar correctamente.")

        # Verificar edges apuntan a nodos existentes
        for edge in edges:
            if edge.get("source") not in node_ids:
                errors.append(f"Edge apunta a nodo origen inexistente: {edge.get('source')}")
            if edge.get("target") not in node_ids:
                errors.append(f"Edge apunta a nodo destino inexistente: {edge.get('target')}")

        # Detectar nodos huérfanos (sin edges entrantes ni salientes, excepto Start)
        connected = set()
        for edge in edges:
            connected.add(edge.get("source"))
            connected.add(edge.get("target"))
        for node in nodes:
            nid = node["id"]
            if nid not in connected and node.get("type") != "start":
                warnings.append(f"Nodo '{node.get('data', {}).get('label', nid)}' no está conectado a ningún otro nodo.")

        # Verificar que Start tiene salida
        if start_nodes:
            start_id = start_nodes[0]["id"]
            start_has_output = any(e["source"] == start_id for e in edges)
            if not start_has_output:
                errors.append("El nodo de Inicio no tiene conexión de salida.")

        # Recopilar variables definidas en el flujo
        defined_vars: set[str] = set()
        for node in nodes:
            ntype = node.get("type", "")
            ndata = node.get("data", {})
            if ntype == "collectInput" and ndata.get("variableName"):
                defined_vars.add(ndata["variableName"])
            if ntype == "start" and ndata.get("injectCallerInfo"):
                defined_vars.add("caller_number")
            if ntype == "action" and ndata.get("resultVariable"):
                defined_vars.add(ndata["resultVariable"])

        # Verificar nodos collectInput tienen variableName
        for node in nodes:
            if node.get("type") == "collectInput":
                data = node.get("data", {})
                if not data.get("variableName"):
                    errors.append(
                        f"Nodo '{data.get('label', node['id'])}' (Recopilar Dato) "
                        "necesita un nombre de variable."
                    )
                if not (data.get("prompt") or "").strip():
                    warnings.append(
                        f"Nodo '{data.get('label', node['id'])}' (Recopilar Dato) "
                        "no tiene pregunta al usuario."
                    )

        # Verificar message/end con contenido vacío
        for node in nodes:
            data = node.get("data", {})
            nid = node["id"]
            if node.get("type") == "message" and not (data.get("message") or "").strip():
                warnings.append(f"Nodo mensaje '{nid}' tiene mensaje vacío.")
            if node.get("type") == "end" and not (data.get("message") or "").strip():
                warnings.append(f"Nodo fin '{nid}' tiene mensaje de despedida vacío.")

        # Verificar que nodos transfer tienen número
        for node in nodes:
            if node.get("type") == "transfer":
                data = node.get("data", {})
                if not data.get("transferNumber"):
                    warnings.append(
                        f"Nodo transferir '{data.get('label', node['id'])}' no tiene número de transferencia."
                    )

        # Operadores válidos para condiciones
        valid_operators = {
            "equals", "not_equals", "contains", "not_contains",
            "starts_with", "ends_with", "not_empty", "empty",
            "gt", "gte", "lt", "lte", "regex", "in", "not_in",
        }
        # Variables de sistema (no requieren definición en el flujo)
        system_vars = {"_turn_count", "_sentiment", "_sentiment_score", "_consecutive_negative"}

        # Verificar que nodos condition tienen condiciones
        for node in nodes:
            if node.get("type") == "condition":
                data = node.get("data", {})
                if not data.get("conditions"):
                    warnings.append(
                        f"Nodo condición '{data.get('label', node['id'])}' no tiene condiciones definidas."
                    )
                # Verificar variables y operadores en condiciones
                for cond in data.get("conditions", []):
                    var_name = cond.get("variable", "")
                    if var_name and var_name not in defined_vars and var_name not in system_vars:
                        warnings.append(
                            f"Nodo condición '{node['id']}': variable '{var_name}' "
                            "no está definida en ningún nodo del flujo."
                        )
                    op = cond.get("operator", "")
                    if op and op not in valid_operators:
                        warnings.append(
                            f"Nodo condición '{node['id']}': operador '{op}' no reconocido. "
                            f"Válidos: {', '.join(sorted(valid_operators))}"
                        )

        # Verificar action nodes sin failure edge
        edge_handles: dict[str, set[str]] = {}
        for edge in edges:
            src = edge.get("source", "")
            handle = edge.get("sourceHandle", "default")
            edge_handles.setdefault(src, set()).add(handle)

        for node in nodes:
            if node.get("type") == "action":
                data = node.get("data", {})
                if data.get("actionType"):
                    handles = edge_handles.get(node["id"], set())
                    if "failure" not in handles:
                        warnings.append(
                            f"Nodo acción '{node['id']}' no tiene ruta de error (failure)."
                        )

        # Verificar variables huérfanas en mensajes/prompts
        var_pattern = re.compile(r"\{\{(\w+)\}\}")
        for node in nodes:
            data = node.get("data", {})
            ntype = node.get("type", "")
            texts: list[str] = []
            if ntype == "message":
                texts.append(data.get("message", ""))
            elif ntype == "end":
                texts.append(data.get("message", ""))
            elif ntype == "collectInput":
                texts.append(data.get("prompt", ""))
                texts.append(data.get("retryMessage", ""))
            elif ntype == "start":
                texts.append(data.get("greeting", ""))
            elif ntype == "action":
                texts.append(data.get("onFailureMessage", ""))
            elif ntype == "transfer":
                texts.append(data.get("message", ""))
            elif ntype == "wait":
                texts.append(data.get("message", ""))

            for txt in texts:
                for match in var_pattern.finditer(txt):
                    vname = match.group(1)
                    if vname not in defined_vars:
                        warnings.append(
                            f"Nodo '{node['id']}': variable '{{{{{vname}}}}}' "
                            "no está definida en el flujo."
                        )

        # Detectar ciclos mediante DFS
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            if src in node_ids and tgt in node_ids:
                adjacency.setdefault(src, []).append(tgt)

        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycle_nodes: set[str] = set()

        def _dfs_cycle(nid: str, path: list[str]) -> None:
            visited.add(nid)
            rec_stack.add(nid)
            for neighbor in adjacency.get(nid, []):
                if neighbor not in visited:
                    _dfs_cycle(neighbor, path + [neighbor])
                elif neighbor in rec_stack:
                    # Reconstruir el ciclo desde neighbor
                    cycle_start = path.index(neighbor) if neighbor in path else -1
                    if cycle_start >= 0:
                        cycle_path = path[cycle_start:] + [neighbor]
                        cycle_nodes.update(cycle_path)
                        cycle_str = " → ".join(cycle_path)
                        warnings.append(f"Ciclo detectado: {cycle_str}")
                    else:
                        cycle_nodes.add(neighbor)
                        cycle_nodes.add(nid)
                        warnings.append(f"Ciclo detectado entre nodos {nid} y {neighbor}")
            rec_stack.discard(nid)

        for nid in node_ids:
            if nid not in visited:
                _dfs_cycle(nid, [nid])

        valid = len(errors) == 0
        return valid, errors, warnings
