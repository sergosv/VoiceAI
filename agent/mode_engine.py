"""Motor de modos de conversacion estructurados (encuesta, quiz, negociacion, entrevista)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModeState:
    """Estado de un modo de conversacion."""

    mode: str
    current_question_idx: int = 0
    answers: list[dict] = field(default_factory=list)
    score: float = 0
    max_score: float = 0
    completed: bool = False
    metadata: dict = field(default_factory=dict)


class ModeEngine:
    """Motor que maneja la progresion de preguntas/logica segun el modo."""

    def __init__(self, mode: str, config: dict) -> None:
        self._mode = mode
        self._config = config
        self._questions: list[dict] = config.get("questions", [])

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def config(self) -> dict:
        return self._config

    @property
    def question_count(self) -> int:
        return len(self._questions)

    def start(self) -> ModeState:
        """Inicializa el estado del modo."""
        max_score = 0.0
        if self._mode == "quiz":
            max_score = sum(q.get("points", 10) for q in self._questions)
        elif self._mode == "interview":
            max_score = sum(q.get("weight", 1) * 10 for q in self._questions)

        return ModeState(
            mode=self._mode,
            max_score=max_score,
            metadata={"negotiation_history": []} if self._mode == "negotiation" else {},
        )

    def get_current_question(self, state: ModeState) -> dict | None:
        """Retorna la pregunta actual o None si se completaron todas."""
        if self._mode == "negotiation":
            return None  # Negociacion no tiene preguntas fijas
        if state.current_question_idx >= len(self._questions):
            return None
        return self._questions[state.current_question_idx]

    def process_answer(
        self, state: ModeState, answer: str
    ) -> tuple[ModeState, str]:
        """Procesa la respuesta del usuario y avanza el estado.

        Returns:
            Tuple de (nuevo_estado, mensaje_para_el_agente).
        """
        if self._mode == "survey":
            return self._process_survey(state, answer)
        if self._mode == "quiz":
            return self._process_quiz(state, answer)
        if self._mode == "interview":
            return self._process_interview(state, answer)
        if self._mode == "negotiation":
            return self._process_negotiation(state, answer)
        return state, ""

    def build_system_prompt(self, state: ModeState, base_rules: str) -> str:
        """Genera el system prompt dinamico segun el estado actual."""
        if self._mode == "survey":
            return self._prompt_survey(state, base_rules)
        if self._mode == "quiz":
            return self._prompt_quiz(state, base_rules)
        if self._mode == "interview":
            return self._prompt_interview(state, base_rules)
        if self._mode == "negotiation":
            return self._prompt_negotiation(state, base_rules)
        return base_rules

    def get_results(self, state: ModeState) -> dict[str, Any]:
        """Retorna los resultados estructurados del modo."""
        results: dict[str, Any] = {
            "mode": self._mode,
            "answers": state.answers,
            "completed": state.completed,
        }

        if self._mode == "quiz":
            passing = self._config.get("passing_score", 70)
            pct = (state.score / state.max_score * 100) if state.max_score else 0
            results["score"] = state.score
            results["max_score"] = state.max_score
            results["percentage"] = round(pct, 1)
            results["passed"] = pct >= passing

        elif self._mode == "interview":
            req = self._config.get("required_score", 60)
            pct = (state.score / state.max_score * 100) if state.max_score else 0
            results["score"] = state.score
            results["max_score"] = state.max_score
            results["percentage"] = round(pct, 1)
            results["passed"] = pct >= req
            results["category_scores"] = state.metadata.get("category_scores", {})

        elif self._mode == "negotiation":
            results["negotiation_history"] = state.metadata.get("negotiation_history", [])
            results["final_offer"] = state.metadata.get("final_offer")
            results["deal_closed"] = state.metadata.get("deal_closed", False)

        return results

    # ── Survey ──

    def _process_survey(self, state: ModeState, answer: str) -> tuple[ModeState, str]:
        q = self.get_current_question(state)
        if not q:
            state.completed = True
            return state, self._config.get("thank_you_message", "Gracias por tus respuestas.")

        state.answers.append({
            "question_id": q.get("id", f"q{state.current_question_idx}"),
            "question_text": q.get("text", ""),
            "answer": answer,
            "type": q.get("type", "text"),
        })
        state.current_question_idx += 1

        next_q = self.get_current_question(state)
        if not next_q:
            state.completed = True
            return state, self._config.get("thank_you_message", "Gracias por tus respuestas.")

        return state, ""

    def _prompt_survey(self, state: ModeState, base_rules: str) -> str:
        q = self.get_current_question(state)
        if not q or state.completed:
            return base_rules + "\n\nLa encuesta ha terminado. Agradece al usuario."

        progress = f"{state.current_question_idx + 1}/{len(self._questions)}"
        q_type = q.get("type", "text")
        options_text = ""
        if q_type == "multiple_choice" and q.get("options"):
            opts = ", ".join(q["options"])
            options_text = f"\nOpciones validas: {opts}"

        return (
            f"{base_rules}\n\n"
            f"## Modo Encuesta (pregunta {progress})\n"
            f"Haz EXACTAMENTE esta pregunta al usuario:\n"
            f'"{q["text"]}"{options_text}\n\n'
            f"Instrucciones:\n"
            f"- Haz solo esta pregunta, no inventes otras\n"
            f"- Si el usuario responde algo irrelevante, redirige amablemente\n"
            f"- Acepta cualquier respuesta valida y avanza\n"
            f"- Tipo de respuesta esperada: {q_type}"
        )

    # ── Quiz ──

    def _process_quiz(self, state: ModeState, answer: str) -> tuple[ModeState, str]:
        q = self.get_current_question(state)
        if not q:
            state.completed = True
            return state, ""

        correct = q.get("correct_answer", "")
        is_correct = answer.strip().lower() == correct.strip().lower()
        points = q.get("points", 10)

        if is_correct:
            state.score += points

        entry: dict[str, Any] = {
            "question_id": q.get("id", f"q{state.current_question_idx}"),
            "question_text": q.get("text", ""),
            "answer": answer,
            "correct_answer": correct,
            "is_correct": is_correct,
            "points_earned": points if is_correct else 0,
            "points_possible": points,
        }
        state.answers.append(entry)
        state.current_question_idx += 1

        feedback = ""
        if self._config.get("show_explanations", True):
            if is_correct:
                feedback = "Correcto!"
            else:
                feedback = f"Incorrecto. La respuesta correcta era: {correct}."
            explanation = q.get("explanation", "")
            if explanation:
                feedback += f" {explanation}"

        next_q = self.get_current_question(state)
        if not next_q:
            state.completed = True
            pct = (state.score / state.max_score * 100) if state.max_score else 0
            passing = self._config.get("passing_score", 70)
            result = "aprobaste" if pct >= passing else "no alcanzaste el puntaje minimo"
            feedback += f" Quiz terminado. Obtuviste {state.score}/{state.max_score} ({pct:.0f}%), {result}."

        return state, feedback

    def _prompt_quiz(self, state: ModeState, base_rules: str) -> str:
        q = self.get_current_question(state)
        if not q or state.completed:
            pct = (state.score / state.max_score * 100) if state.max_score else 0
            return (
                f"{base_rules}\n\n"
                f"## Quiz Terminado\n"
                f"Puntaje: {state.score}/{state.max_score} ({pct:.0f}%)\n"
                f"Informa el resultado al usuario y despidete."
            )

        progress = f"{state.current_question_idx + 1}/{len(self._questions)}"
        options = q.get("options", [])
        options_text = ""
        if options:
            options_text = "\nOpciones:\n" + "\n".join(f"- {o}" for o in options)

        return (
            f"{base_rules}\n\n"
            f"## Modo Quiz (pregunta {progress})\n"
            f"Haz esta pregunta:\n"
            f'"{q["text"]}"{options_text}\n\n'
            f"- Espera la respuesta del usuario\n"
            f"- No des pistas ni reveles la respuesta\n"
            f"- Puntaje actual: {state.score}/{state.max_score}"
        )

    # ── Interview ──

    def _process_interview(self, state: ModeState, answer: str) -> tuple[ModeState, str]:
        q = self.get_current_question(state)
        if not q:
            state.completed = True
            return state, ""

        weight = q.get("weight", 1)
        category = q.get("category", "general")

        entry: dict[str, Any] = {
            "question_id": q.get("id", f"q{state.current_question_idx}"),
            "question_text": q.get("text", ""),
            "answer": answer,
            "category": category,
            "weight": weight,
            "evaluation_criteria": q.get("evaluation_criteria", ""),
        }
        state.answers.append(entry)
        state.current_question_idx += 1

        # Scoring se hace post-call con LLM (no inline para no agregar latencia)
        next_q = self.get_current_question(state)
        if not next_q:
            state.completed = True
            return state, "Esas son todas las preguntas. Gracias por tu tiempo."

        return state, ""

    def _prompt_interview(self, state: ModeState, base_rules: str) -> str:
        q = self.get_current_question(state)
        if not q or state.completed:
            return (
                f"{base_rules}\n\n"
                f"## Entrevista Terminada\n"
                f"Agradece al candidato y dile que recibira noticias pronto."
            )

        progress = f"{state.current_question_idx + 1}/{len(self._questions)}"
        category = q.get("category", "general")
        criteria = q.get("evaluation_criteria", "")
        criteria_note = f"\n(Evalua: {criteria})" if criteria else ""

        return (
            f"{base_rules}\n\n"
            f"## Modo Entrevista (pregunta {progress}, categoria: {category})\n"
            f"Haz esta pregunta:\n"
            f'"{q["text"]}"{criteria_note}\n\n'
            f"- Escucha atentamente y haz follow-up si la respuesta es vaga\n"
            f"- Mantente profesional y amable\n"
            f"- No evalues en voz alta, solo registra la respuesta"
        )

    # ── Negotiation ──

    def _process_negotiation(self, state: ModeState, answer: str) -> tuple[ModeState, str]:
        history = state.metadata.setdefault("negotiation_history", [])
        history.append({"role": "customer", "message": answer})
        return state, ""

    def _prompt_negotiation(self, state: ModeState, base_rules: str) -> str:
        catalog = self._config.get("product_catalog", [])
        authority = self._config.get("authority_level", "agent")
        escalation = self._config.get("escalation_threshold_pct", 25)
        closing = self._config.get("closing_phrases", [])

        products_text = ""
        for p in catalog:
            name = p.get("name", "Producto")
            base = p.get("base_price", 0)
            min_p = p.get("min_price", 0)
            max_disc = p.get("max_discount_pct", 0)
            products_text += (
                f"- {name}: precio base ${base}, "
                f"minimo aceptable ${min_p} (max {max_disc}% descuento)\n"
            )

        rules_text = ""
        for rule in self._config.get("discount_rules", []):
            rules_text += f"- {rule.get('condition', '')}: {rule.get('extra_discount_pct', 0)}% extra\n"

        closing_text = ""
        if closing:
            closing_text = f"\nFrases de cierre sugeridas: {', '.join(closing)}"

        history = state.metadata.get("negotiation_history", [])
        history_text = ""
        if history:
            recent = history[-6:]  # Ultimas 6 interacciones
            history_text = "\n\nHistorial reciente de negociacion:\n"
            for h in recent:
                history_text += f"- {h['role']}: {h['message']}\n"

        return (
            f"{base_rules}\n\n"
            f"## Modo Negociacion\n"
            f"Eres un negociador con nivel de autoridad: {authority}\n\n"
            f"### Catalogo de productos\n{products_text}\n"
            f"### Reglas de descuento\n{rules_text}\n"
            f"### Limites\n"
            f"- NUNCA bajes del precio minimo\n"
            f"- Si el cliente pide mas de {escalation}% de descuento, "
            f"menciona que necesitas consultar con un supervisor\n"
            f"- Ofrece descuentos gradualmente, no todo de golpe\n"
            f"- Busca cerrar el trato cuando el cliente muestre interes\n"
            f"{closing_text}"
            f"{history_text}"
        )

    def record_negotiation_offer(
        self, state: ModeState, product_id: str, price: float, accepted: bool
    ) -> ModeState:
        """Registra una oferta de negociacion."""
        history = state.metadata.setdefault("negotiation_history", [])
        history.append({
            "role": "agent_offer",
            "product_id": product_id,
            "price": price,
            "accepted": accepted,
        })
        if accepted:
            state.metadata["final_offer"] = {"product_id": product_id, "price": price}
            state.metadata["deal_closed"] = True
            state.completed = True
        return state
