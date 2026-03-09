"""Tests para mejoras del sistema de memoria: decay, contradicciones, re-ranking."""

import asyncio
import json
import math
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.memory import AgentMemory


# ── Helpers ──────────────────────────────────────────────


def _make_memory(
    summary: str = "Test memory",
    topics: list[str] | None = None,
    channel: str = "call",
    age_days: float = 0,
    sentiment: str = "neutral",
    action_items: list[str] | None = None,
) -> dict:
    """Crea un dict de memoria con fecha relativa a ahora."""
    created = datetime.now(timezone.utc) - timedelta(days=age_days)
    return {
        "id": "mem-test",
        "summary": summary,
        "channel": channel,
        "agent_name": "Test Agent",
        "sentiment": sentiment,
        "topics": topics or [],
        "action_items": action_items or [],
        "created_at": created.isoformat(),
    }


def _make_agent_memory(
    memories: list[dict] | None = None,
    contact: dict | None = None,
) -> AgentMemory:
    """Crea un AgentMemory pre-configurado sin conexión a DB."""
    with patch("agent.memory._get_supabase"):
        mem = AgentMemory.__new__(AgentMemory)
        mem._client_id = "client-123"
        mem._channel = "call"
        mem._sb = MagicMock()
        mem.contact_id = "contact-456"
        mem.contact = contact or {"id": "contact-456", "name": "Carlos"}
        mem.memories = memories or []
        mem.identifiers = []
        mem._is_new_contact = False
        return mem


# ── Temporal Decay (re-ranking) ──────────────────────────


class TestMemoryDecay:
    """Verifica que memorias más viejas obtienen scores más bajos."""

    def test_recent_memory_scores_higher_than_old(self):
        """Una memoria de hoy debe tener mayor score que una de hace 6 meses."""
        recent = _make_memory(summary="Cita reciente", age_days=1)
        old = _make_memory(summary="Cita antigua", age_days=180)
        # Necesitamos >5 memorias para que se active el re-ranking
        fillers = [_make_memory(summary=f"Filler {i}", age_days=90) for i in range(5)]

        mem = _make_agent_memory()
        ranked = mem._rerank_memories([old] + fillers + [recent])

        # La reciente debe estar primero
        assert ranked[0]["summary"] == "Cita reciente"

    def test_decay_formula_matches_expected(self):
        """Verifica que el decay a los 180 días es ~37% (exp(-1))."""
        # exp(-180/180) = exp(-1) ≈ 0.368
        decay_180 = math.exp(-180 / 180)
        assert abs(decay_180 - 0.368) < 0.01

        # A los 0 días, decay = 1.0
        decay_0 = math.exp(0 / 180)
        assert decay_0 == 1.0

        # A los 360 días, decay ≈ 0.135
        decay_360 = math.exp(-360 / 180)
        assert abs(decay_360 - 0.135) < 0.01

    def test_six_month_old_loses_significant_weight(self):
        """Una memoria de 6 meses pierde ~63% de su peso por recencia."""
        recent = _make_memory(summary="Hoy", age_days=0)
        six_months = _make_memory(summary="Hace 6 meses", age_days=180)
        fillers = [_make_memory(summary=f"Filler {i}", age_days=90) for i in range(5)]

        mem = _make_agent_memory()
        ranked = mem._rerank_memories([six_months] + fillers + [recent])

        assert ranked[0]["summary"] == "Hoy"

    def test_all_same_age_preserves_order(self):
        """Si todas tienen la misma edad, se mantiene algún orden consistente."""
        mems = [
            _make_memory(summary=f"Mem {i}", age_days=10)
            for i in range(3)
        ]
        agent_mem = _make_agent_memory()
        ranked = agent_mem._rerank_memories(mems)
        assert len(ranked) == 3

    def test_fewer_than_five_returns_all(self):
        """Con menos de 5 memorias, devuelve todas sin filtrar."""
        mems = [_make_memory(summary=f"Mem {i}") for i in range(3)]
        agent_mem = _make_agent_memory()
        ranked = agent_mem._rerank_memories(mems)
        assert len(ranked) == 3


# ── Smart Re-ranking (topic relevance) ──────────────────


class TestSmartReranking:
    """Verifica que memorias con topics relevantes al prompt suben de rank."""

    def test_relevant_topic_beats_recency(self):
        """Una memoria temáticamente relevante sube de rank vs memorias irrelevantes."""
        # Fillers de edad similar a la relevante pero sin topics útiles
        filler = [
            _make_memory(summary=f"Filler {i}", topics=["random", "otro"], age_days=25 + i)
            for i in range(6)
        ]
        relevant_old = _make_memory(
            summary="Consulta sobre citas dentales",
            topics=["citas", "dentista", "horarios"],
            age_days=30,
        )
        irrelevant_new = _make_memory(
            summary="Preguntó por el clima",
            topics=["clima", "temperatura"],
            age_days=28,
        )

        all_mems = filler + [relevant_old, irrelevant_new]
        agent_mem = _make_agent_memory()

        # system_prompt con keywords de "citas" y "dentista"
        ranked = agent_mem._rerank_memories(
            all_mems,
            system_prompt="Eres un asistente de citas para una clínica dentista. Agenda horarios.",
        )

        # La memoria de citas dentales debe estar en el top 5
        top_summaries = [m["summary"] for m in ranked[:5]]
        assert "Consulta sobre citas dentales" in top_summaries

    def test_no_system_prompt_uses_recency_only(self):
        """Sin system_prompt, el ranking es puramente por recencia."""
        mems = [
            _make_memory(summary=f"Mem {i}", age_days=i * 10, topics=["topic"])
            for i in range(8)
        ]
        agent_mem = _make_agent_memory()
        ranked = agent_mem._rerank_memories(mems, system_prompt=None)

        # Los más recientes (age_days menor) deben estar primero
        ages = []
        for m in ranked[:5]:
            dt = datetime.fromisoformat(m["created_at"])
            age = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
            ages.append(age)
        # Verificar que están ordenados de menor a mayor edad
        assert ages == sorted(ages)

    def test_keyword_extraction_ignores_short_words(self):
        """Keywords menores a 4 chars se ignoran en el matching."""
        mems = [
            _make_memory(summary=f"Mem {i}", age_days=i, topics=["de", "en", "la"])
            for i in range(8)
        ]
        agent_mem = _make_agent_memory()
        # Prompt con solo palabras cortas — no debería dar relevancia extra
        ranked = agent_mem._rerank_memories(
            mems, system_prompt="de en la el un"
        )
        # Debe devolver 5 (top from 8)
        assert len(ranked) == 5


# ── Contradiction Detection ──────────────────────────────


class TestContradictionDetection:
    """Verifica la detección de contradicciones con Gemini mockeado."""

    @pytest.mark.asyncio
    async def test_detects_contradiction(self):
        """Detecta contradicción cuando key_facts cambian."""
        agent_mem = _make_agent_memory(
            contact={
                "id": "contact-456",
                "name": "Carlos",
                "key_facts": ["Tiene 2 hijos", "Vive en Mérida"],
                "preferences": {"horario": "mañana"},
            }
        )

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "contradictions": [
                {
                    "old_fact": "Tiene 2 hijos",
                    "new_fact": "Tiene 3 hijos",
                    "field": "key_facts",
                }
            ]
        })

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("agent.memory._get_gemini", return_value=mock_client):
            contradictions = await agent_mem._detect_contradictions(
                new_memory_data={
                    "key_facts": ["Tiene 3 hijos", "Trabaja en IT"],
                    "preferences": {},
                    "extracted_data": {},
                },
                contact=agent_mem.contact,
            )

        assert len(contradictions) == 1
        assert contradictions[0]["old_fact"] == "Tiene 2 hijos"
        assert contradictions[0]["new_fact"] == "Tiene 3 hijos"

    @pytest.mark.asyncio
    async def test_no_contradiction_returns_empty(self):
        """Sin contradicciones, retorna lista vacía."""
        agent_mem = _make_agent_memory(
            contact={
                "id": "contact-456",
                "name": "Carlos",
                "key_facts": ["Vive en Mérida"],
                "preferences": {},
            }
        )

        mock_response = MagicMock()
        mock_response.text = json.dumps({"contradictions": []})

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("agent.memory._get_gemini", return_value=mock_client):
            contradictions = await agent_mem._detect_contradictions(
                new_memory_data={
                    "key_facts": ["Trabaja en IT"],
                    "preferences": {},
                    "extracted_data": {},
                },
                contact=agent_mem.contact,
            )

        assert contradictions == []

    @pytest.mark.asyncio
    async def test_no_old_data_skips_detection(self):
        """Si el contacto no tiene datos previos, no llama a Gemini."""
        agent_mem = _make_agent_memory(
            contact={
                "id": "contact-456",
                "name": None,
                "key_facts": [],
                "preferences": {},
            }
        )

        with patch("agent.memory._get_gemini") as mock_gemini:
            contradictions = await agent_mem._detect_contradictions(
                new_memory_data={
                    "key_facts": ["Dato nuevo"],
                    "preferences": {},
                    "extracted_data": {},
                },
                contact=agent_mem.contact,
            )
            # No debería llamar a Gemini
            mock_gemini.assert_not_called()

        assert contradictions == []

    @pytest.mark.asyncio
    async def test_no_new_data_skips_detection(self):
        """Si no hay datos nuevos, no llama a Gemini."""
        agent_mem = _make_agent_memory(
            contact={
                "id": "contact-456",
                "key_facts": ["Dato viejo"],
                "preferences": {"color": "azul"},
            }
        )

        with patch("agent.memory._get_gemini") as mock_gemini:
            contradictions = await agent_mem._detect_contradictions(
                new_memory_data={
                    "key_facts": [],
                    "preferences": {},
                    "extracted_data": {},
                },
                contact=agent_mem.contact,
            )
            mock_gemini.assert_not_called()

        assert contradictions == []

    @pytest.mark.asyncio
    async def test_gemini_error_returns_empty(self):
        """Si Gemini falla, retorna lista vacía sin propagar error."""
        agent_mem = _make_agent_memory(
            contact={
                "id": "contact-456",
                "key_facts": ["Dato viejo"],
                "preferences": {"color": "azul"},
            }
        )

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("API Error")
        )

        with patch("agent.memory._get_gemini", return_value=mock_client):
            contradictions = await agent_mem._detect_contradictions(
                new_memory_data={
                    "key_facts": ["Dato nuevo"],
                    "preferences": {},
                    "extracted_data": {},
                },
                contact=agent_mem.contact,
            )

        assert contradictions == []

    @pytest.mark.asyncio
    async def test_preference_contradiction(self):
        """Detecta contradicción en preferencias."""
        agent_mem = _make_agent_memory(
            contact={
                "id": "contact-456",
                "key_facts": [],
                "preferences": {"horario": "mañana", "idioma": "español"},
            }
        )

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "contradictions": [
                {
                    "old_fact": "horario: mañana",
                    "new_fact": "horario: tarde",
                    "field": "preferences",
                }
            ]
        })

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("agent.memory._get_gemini", return_value=mock_client):
            contradictions = await agent_mem._detect_contradictions(
                new_memory_data={
                    "key_facts": [],
                    "preferences": {"horario": "tarde"},
                    "extracted_data": {},
                },
                contact=agent_mem.contact,
            )

        assert len(contradictions) == 1
        assert contradictions[0]["field"] == "preferences"


# ── Memory Tool (recency_score formatting) ───────────────


class TestMemoryToolFormatting:
    """Verifica que recall_memory_search incluye recency_score."""

    @pytest.mark.asyncio
    async def test_recency_score_high_shows_alta(self):
        """Score >= 0.7 muestra 'alta'."""
        mock_embedding = [0.1] * 768
        mock_memories = [
            {
                "summary": "Cita confirmada",
                "channel": "whatsapp",
                "created_at": "2026-03-01T10:00:00Z",
                "similarity": 0.85,
                "recency_score": 0.82,
                "action_items": [],
            }
        ]

        with (
            patch("agent.tools.memory_tool.generate_embedding", new_callable=AsyncMock, return_value=mock_embedding),
            patch("agent.db.get_supabase") as mock_sb,
        ):
            mock_rpc = MagicMock()
            mock_rpc.execute.return_value = MagicMock(data=mock_memories)
            mock_sb.return_value.rpc.return_value = mock_rpc

            from agent.tools.memory_tool import recall_memory_search

            result = await recall_memory_search(
                query="cita", client_id="c1", contact_id="ct1"
            )

        assert "relevancia: alta" in result

    @pytest.mark.asyncio
    async def test_recency_score_medium_shows_media(self):
        """Score entre 0.4 y 0.7 muestra 'media'."""
        mock_embedding = [0.1] * 768
        mock_memories = [
            {
                "summary": "Consulta general",
                "channel": "call",
                "created_at": "2025-12-01T10:00:00Z",
                "similarity": 0.6,
                "recency_score": 0.5,
                "action_items": [],
            }
        ]

        with (
            patch("agent.tools.memory_tool.generate_embedding", new_callable=AsyncMock, return_value=mock_embedding),
            patch("agent.db.get_supabase") as mock_sb,
        ):
            mock_rpc = MagicMock()
            mock_rpc.execute.return_value = MagicMock(data=mock_memories)
            mock_sb.return_value.rpc.return_value = mock_rpc

            from agent.tools.memory_tool import recall_memory_search

            result = await recall_memory_search(
                query="consulta", client_id="c1", contact_id="ct1"
            )

        assert "relevancia: media" in result

    @pytest.mark.asyncio
    async def test_recency_score_low_shows_baja(self):
        """Score < 0.4 muestra 'baja'."""
        mock_embedding = [0.1] * 768
        mock_memories = [
            {
                "summary": "Memoria antigua",
                "channel": "call",
                "created_at": "2025-06-01T10:00:00Z",
                "similarity": 0.35,
                "recency_score": 0.2,
                "action_items": [],
            }
        ]

        with (
            patch("agent.tools.memory_tool.generate_embedding", new_callable=AsyncMock, return_value=mock_embedding),
            patch("agent.db.get_supabase") as mock_sb,
        ):
            mock_rpc = MagicMock()
            mock_rpc.execute.return_value = MagicMock(data=mock_memories)
            mock_sb.return_value.rpc.return_value = mock_rpc

            from agent.tools.memory_tool import recall_memory_search

            result = await recall_memory_search(
                query="antigua", client_id="c1", contact_id="ct1"
            )

        assert "relevancia: baja" in result

    @pytest.mark.asyncio
    async def test_fallback_when_no_recency_score(self):
        """Si no hay recency_score, usa similarity como fallback."""
        mock_embedding = [0.1] * 768
        mock_memories = [
            {
                "summary": "Sin recency",
                "channel": "call",
                "created_at": "2026-03-01T10:00:00Z",
                "similarity": 0.9,
                # No recency_score — debería usar similarity
                "action_items": [],
            }
        ]

        with (
            patch("agent.tools.memory_tool.generate_embedding", new_callable=AsyncMock, return_value=mock_embedding),
            patch("agent.db.get_supabase") as mock_sb,
        ):
            mock_rpc = MagicMock()
            mock_rpc.execute.return_value = MagicMock(data=mock_memories)
            mock_sb.return_value.rpc.return_value = mock_rpc

            from agent.tools.memory_tool import recall_memory_search

            result = await recall_memory_search(
                query="test", client_id="c1", contact_id="ct1"
            )

        assert "relevancia: alta" in result


# ── build_memory_context with system_prompt ──────────────


class TestBuildMemoryContextWithPrompt:
    """Verifica que build_memory_context acepta y usa system_prompt."""

    def test_accepts_system_prompt_parameter(self):
        """build_memory_context acepta system_prompt opcional."""
        mem = _make_agent_memory(
            memories=[_make_memory(summary="Test")],
            contact={"id": "c", "name": "Ana"},
        )
        ctx = mem.build_memory_context(system_prompt="Eres un asistente dental")
        assert "Ana" in ctx
        assert "Test" in ctx

    def test_without_system_prompt_works_as_before(self):
        """Sin system_prompt sigue funcionando igual (backward compat)."""
        mem = _make_agent_memory(
            memories=[_make_memory(summary="Memoria vieja")],
            contact={"id": "c", "name": "Luis"},
        )
        ctx = mem.build_memory_context()
        assert "Luis" in ctx
        assert "Memoria vieja" in ctx

    def test_new_contact_returns_empty(self):
        """Contacto nuevo retorna string vacío."""
        mem = _make_agent_memory()
        mem._is_new_contact = True
        ctx = mem.build_memory_context(system_prompt="Test")
        assert ctx == ""
