"""Tests para ModeEngine — motor de modos de conversación."""

import pytest

from agent.mode_engine import ModeEngine, ModeState


# ── Survey ──


class TestSurveyMode:
    def _make_engine(self, questions=None, thank_you="Gracias!"):
        if questions is None:
            questions = [
                {"id": "q1", "text": "¿Cómo calificas el servicio?", "type": "multiple_choice",
                 "options": ["Bueno", "Regular", "Malo"]},
                {"id": "q2", "text": "¿Algún comentario?", "type": "text"},
            ]
        return ModeEngine("survey", {"questions": questions, "thank_you_message": thank_you})

    def test_start_survey(self):
        engine = self._make_engine()
        state = engine.start()
        assert state.mode == "survey"
        assert state.current_question_idx == 0
        assert state.max_score == 0

    def test_question_count(self):
        engine = self._make_engine()
        assert engine.question_count == 2

    def test_get_current_question(self):
        engine = self._make_engine()
        state = engine.start()
        q = engine.get_current_question(state)
        assert q["id"] == "q1"
        assert q["type"] == "multiple_choice"

    def test_process_answers_and_complete(self):
        engine = self._make_engine()
        state = engine.start()
        state, msg = engine.process_answer(state, "Bueno")
        assert state.current_question_idx == 1
        assert len(state.answers) == 1
        assert state.answers[0]["answer"] == "Bueno"
        assert not state.completed

        state, msg = engine.process_answer(state, "Todo bien")
        assert state.completed
        assert msg == "Gracias!"
        assert len(state.answers) == 2

    def test_survey_results(self):
        engine = self._make_engine()
        state = engine.start()
        state, _ = engine.process_answer(state, "Bueno")
        state, _ = engine.process_answer(state, "Nada más")
        results = engine.get_results(state)
        assert results["mode"] == "survey"
        assert results["completed"] is True
        assert len(results["answers"]) == 2

    def test_survey_prompt(self):
        engine = self._make_engine()
        state = engine.start()
        prompt = engine.build_system_prompt(state, "Base rules")
        assert "Modo Encuesta" in prompt
        assert "1/2" in prompt
        assert "¿Cómo calificas el servicio?" in prompt
        assert "Opciones validas" in prompt

    def test_survey_completed_prompt(self):
        engine = self._make_engine()
        state = engine.start()
        state, _ = engine.process_answer(state, "A")
        state, _ = engine.process_answer(state, "B")
        prompt = engine.build_system_prompt(state, "Base")
        assert "ha terminado" in prompt

    def test_empty_survey(self):
        engine = self._make_engine(questions=[])
        state = engine.start()
        state, msg = engine.process_answer(state, "x")
        assert state.completed


# ── Quiz ──


class TestQuizMode:
    def _make_engine(self, questions=None, passing=70, show_explanations=True):
        if questions is None:
            questions = [
                {"id": "q1", "text": "2+2=?", "correct_answer": "4", "points": 10,
                 "options": ["3", "4", "5"], "explanation": "Suma básica."},
                {"id": "q2", "text": "Capital de México?", "correct_answer": "CDMX", "points": 20,
                 "options": ["GDL", "CDMX", "MTY"]},
            ]
        return ModeEngine("quiz", {
            "questions": questions, "passing_score": passing,
            "show_explanations": show_explanations,
        })

    def test_start_quiz(self):
        engine = self._make_engine()
        state = engine.start()
        assert state.max_score == 30
        assert state.score == 0

    def test_correct_answer(self):
        engine = self._make_engine()
        state = engine.start()
        state, feedback = engine.process_answer(state, "4")
        assert state.score == 10
        assert state.answers[0]["is_correct"] is True
        assert "Correcto" in feedback

    def test_incorrect_answer(self):
        engine = self._make_engine()
        state = engine.start()
        state, feedback = engine.process_answer(state, "3")
        assert state.score == 0
        assert state.answers[0]["is_correct"] is False
        assert "Incorrecto" in feedback
        assert "Suma básica" in feedback

    def test_quiz_completion_pass(self):
        engine = self._make_engine()
        state = engine.start()
        state, _ = engine.process_answer(state, "4")
        state, feedback = engine.process_answer(state, "CDMX")
        assert state.completed
        assert state.score == 30
        assert "aprobaste" in feedback

    def test_quiz_completion_fail(self):
        engine = self._make_engine()
        state = engine.start()
        state, _ = engine.process_answer(state, "3")
        state, feedback = engine.process_answer(state, "GDL")
        assert state.completed
        assert state.score == 0
        assert "no alcanzaste" in feedback

    def test_quiz_results(self):
        engine = self._make_engine()
        state = engine.start()
        state, _ = engine.process_answer(state, "4")
        state, _ = engine.process_answer(state, "GDL")
        results = engine.get_results(state)
        assert results["score"] == 10
        assert results["max_score"] == 30
        assert results["percentage"] == pytest.approx(33.3, rel=0.1)
        assert results["passed"] is False

    def test_quiz_prompt(self):
        engine = self._make_engine()
        state = engine.start()
        prompt = engine.build_system_prompt(state, "Base")
        assert "Modo Quiz" in prompt
        assert "2+2=?" in prompt
        assert "Puntaje actual: 0/30" in prompt

    def test_quiz_case_insensitive(self):
        engine = self._make_engine()
        state = engine.start()
        state, _ = engine.process_answer(state, "  4  ")
        assert state.answers[0]["is_correct"] is True

    def test_no_explanations(self):
        engine = self._make_engine(show_explanations=False)
        state = engine.start()
        state, feedback = engine.process_answer(state, "3")
        assert feedback == ""


# ── Interview ──


class TestInterviewMode:
    def _make_engine(self, questions=None):
        if questions is None:
            questions = [
                {"id": "q1", "text": "Háblame de ti", "category": "general", "weight": 2,
                 "evaluation_criteria": "Claridad y estructura"},
                {"id": "q2", "text": "¿Cuál es tu experiencia con Python?", "category": "technical",
                 "weight": 3, "evaluation_criteria": "Profundidad técnica"},
            ]
        return ModeEngine("interview", {
            "questions": questions, "required_score": 60,
        })

    def test_start_interview(self):
        engine = self._make_engine()
        state = engine.start()
        assert state.max_score == 50  # (2*10 + 3*10)
        assert state.mode == "interview"

    def test_process_answers(self):
        engine = self._make_engine()
        state = engine.start()
        state, msg = engine.process_answer(state, "Soy ingeniero")
        assert len(state.answers) == 1
        assert state.answers[0]["category"] == "general"
        assert msg == ""

        state, msg = engine.process_answer(state, "5 años con Python")
        assert state.completed
        assert "Gracias" in msg

    def test_interview_prompt(self):
        engine = self._make_engine()
        state = engine.start()
        prompt = engine.build_system_prompt(state, "Base")
        assert "Modo Entrevista" in prompt
        assert "Háblame de ti" in prompt
        assert "Evalua: Claridad" in prompt

    def test_interview_results(self):
        engine = self._make_engine()
        state = engine.start()
        state, _ = engine.process_answer(state, "x")
        state, _ = engine.process_answer(state, "y")
        results = engine.get_results(state)
        assert results["mode"] == "interview"
        assert results["max_score"] == 50
        assert results["completed"] is True


# ── Negotiation ──


class TestNegotiationMode:
    def _make_engine(self):
        return ModeEngine("negotiation", {
            "product_catalog": [
                {"name": "Plan Pro", "base_price": 500, "min_price": 400, "max_discount_pct": 20},
            ],
            "authority_level": "agent",
            "escalation_threshold_pct": 25,
            "discount_rules": [
                {"condition": "pago anual", "extra_discount_pct": 5},
            ],
            "closing_phrases": ["¿Cerramos el trato?", "¿Le parece bien?"],
        })

    def test_start_negotiation(self):
        engine = self._make_engine()
        state = engine.start()
        assert state.mode == "negotiation"
        assert state.metadata["negotiation_history"] == []

    def test_no_fixed_questions(self):
        engine = self._make_engine()
        state = engine.start()
        assert engine.get_current_question(state) is None

    def test_process_customer_message(self):
        engine = self._make_engine()
        state = engine.start()
        state, _ = engine.process_answer(state, "Quiero un descuento del 10%")
        assert len(state.metadata["negotiation_history"]) == 1
        assert state.metadata["negotiation_history"][0]["role"] == "customer"

    def test_record_offer(self):
        engine = self._make_engine()
        state = engine.start()
        state = engine.record_negotiation_offer(state, "plan_pro", 450.0, accepted=False)
        assert len(state.metadata["negotiation_history"]) == 1
        assert not state.completed

        state = engine.record_negotiation_offer(state, "plan_pro", 420.0, accepted=True)
        assert state.completed
        assert state.metadata["deal_closed"] is True
        assert state.metadata["final_offer"]["price"] == 420.0

    def test_negotiation_prompt(self):
        engine = self._make_engine()
        state = engine.start()
        prompt = engine.build_system_prompt(state, "Base")
        assert "Modo Negociacion" in prompt
        assert "Plan Pro" in prompt
        assert "$500" in prompt
        assert "$400" in prompt
        assert "NUNCA bajes del precio minimo" in prompt
        assert "Cerramos el trato" in prompt

    def test_negotiation_results(self):
        engine = self._make_engine()
        state = engine.start()
        state = engine.record_negotiation_offer(state, "pro", 450.0, accepted=True)
        results = engine.get_results(state)
        assert results["deal_closed"] is True
        assert results["final_offer"]["price"] == 450.0

    def test_negotiation_history_in_prompt(self):
        engine = self._make_engine()
        state = engine.start()
        state, _ = engine.process_answer(state, "¿Cuánto cuesta?")
        prompt = engine.build_system_prompt(state, "Base")
        assert "Historial reciente" in prompt
        assert "customer" in prompt


# ── Edge cases ──


class TestModeEngineEdgeCases:
    def test_unknown_mode(self):
        engine = ModeEngine("unknown", {"questions": []})
        state = engine.start()
        state, msg = engine.process_answer(state, "test")
        assert msg == ""

    def test_unknown_mode_prompt(self):
        engine = ModeEngine("unknown", {})
        state = engine.start()
        prompt = engine.build_system_prompt(state, "Base rules")
        assert prompt == "Base rules"
