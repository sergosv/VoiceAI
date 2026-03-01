"""Sistema de memoria de largo plazo para agentes.

Permite que los agentes recuerden interacciones pasadas con contactos
a través de todos los canales (voz, WhatsApp, web chat).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from google import genai
from google.genai import types as genai_types
from supabase import Client, create_client

from agent.embeddings import generate_embedding

logger = logging.getLogger(__name__)

# Modelo para análisis de conversaciones
ANALYSIS_MODEL = "gemini-2.5-flash"

# Iconos por canal para el contexto del agente
CHANNEL_ICONS = {
    "call": "📞",
    "outbound_call": "📞↗",
    "whatsapp": "💬",
    "web_chat": "🌐",
}


def _get_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _get_gemini() -> genai.Client:
    return genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


class AgentMemory:
    """Memoria de largo plazo por contacto.

    Fases:
    1. identify() — Resuelve o crea contacto por identificador
    2. build_memory_context() — Genera contexto para inyectar en el prompt
    3. store() — Analiza y guarda memoria al final de la interacción
    """

    def __init__(self, client_id: str, channel: str = "call") -> None:
        self._client_id = client_id
        self._channel = channel
        self._sb = _get_supabase()

        # Se llenan en identify()
        self.contact_id: str | None = None
        self.contact: dict | None = None
        self.memories: list[dict] = []
        self.identifiers: list[dict] = []
        self._is_new_contact = False

    async def identify(
        self,
        identifier_value: str | None,
        identifier_type: str = "phone",
    ) -> str | None:
        """Resuelve o crea un contacto por identificador.

        Returns:
            contact_id si se encontró/creó, None si no hay identifier_value.
        """
        if not identifier_value:
            return None

        # Intentar resolver via RPC
        try:
            result = self._sb.rpc(
                "resolve_contact",
                {
                    "p_client_id": self._client_id,
                    "p_identifier_type": identifier_type,
                    "p_identifier_value": identifier_value,
                },
            ).execute()

            contact_id = result.data if isinstance(result.data, str) else None
        except Exception:
            logger.exception("Error en resolve_contact RPC")
            contact_id = None

        if contact_id:
            # Contacto conocido — cargar datos
            self.contact_id = contact_id
            await self._load_contact_data()
            logger.info(
                "Contacto reconocido: %s (%s) — %d memorias previas",
                self.contact.get("name") or "Sin nombre",
                identifier_value,
                len(self.memories),
            )
        else:
            # Contacto nuevo — crear con identificador
            try:
                result = self._sb.rpc(
                    "create_contact_with_identifier",
                    {
                        "p_client_id": self._client_id,
                        "p_identifier_type": identifier_type,
                        "p_identifier_value": identifier_value,
                    },
                ).execute()
                contact_id = result.data if isinstance(result.data, str) else None
            except Exception:
                logger.exception("Error en create_contact_with_identifier RPC")
                # Fallback: buscar por teléfono en tabla contacts directamente
                if identifier_type == "phone":
                    contact_id = self._fallback_find_by_phone(identifier_value)

            if contact_id:
                self.contact_id = contact_id
                self._is_new_contact = True
                self.contact = {"id": contact_id, "name": None}
                self.memories = []
                self.identifiers = []
                logger.info("Contacto nuevo creado: %s (%s)", contact_id, identifier_value)

        return self.contact_id

    def _fallback_find_by_phone(self, phone: str) -> str | None:
        """Busca contacto por teléfono directamente en tabla contacts."""
        try:
            result = (
                self._sb.table("contacts")
                .select("id")
                .eq("client_id", self._client_id)
                .eq("phone", phone)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]["id"]
        except Exception:
            logger.exception("Error en fallback find by phone")
        return None

    async def _load_contact_data(self) -> None:
        """Carga el contacto, memorias recientes e identificadores."""
        if not self.contact_id:
            return

        # Contacto
        try:
            result = (
                self._sb.table("contacts")
                .select("*")
                .eq("id", self.contact_id)
                .limit(1)
                .execute()
            )
            self.contact = result.data[0] if result.data else {}
        except Exception:
            logger.exception("Error cargando contacto")
            self.contact = {}

        # Memorias recientes (todos los canales)
        try:
            result = self._sb.rpc(
                "get_recent_memories",
                {
                    "p_client_id": self._client_id,
                    "p_contact_id": self.contact_id,
                    "p_limit": 5,
                },
            ).execute()
            self.memories = result.data if isinstance(result.data, list) else []
        except Exception:
            logger.exception("Error cargando memorias")
            self.memories = []

        # Identificadores
        try:
            result = (
                self._sb.table("contact_identifiers")
                .select("*")
                .eq("contact_id", self.contact_id)
                .execute()
            )
            self.identifiers = result.data or []
        except Exception:
            logger.exception("Error cargando identificadores")
            self.identifiers = []

    def build_memory_context(self) -> str:
        """Construye el bloque de contexto de memoria para el prompt.

        Returns:
            String con el contexto de memoria, vacío si el contacto es nuevo.
        """
        if self._is_new_contact or not self.contact:
            return ""

        contact = self.contact
        name = contact.get("name")
        if not name and not self.memories:
            return ""

        lines: list[str] = ["\n\n## CONTEXTO DEL CLIENTE"]

        # Datos básicos
        if name:
            lines.append(f"- Nombre: {name}")

        preferences = contact.get("preferences") or {}
        if preferences:
            prefs_str = ", ".join(f"{k}: {v}" for k, v in preferences.items())
            lines.append(f"- Preferencias: {prefs_str}")

        key_facts = contact.get("key_facts") or []
        if key_facts:
            facts_str = "; ".join(str(f) for f in key_facts[:5])
            lines.append(f"- Datos importantes: {facts_str}")

        tags = contact.get("tags") or []
        if tags:
            lines.append(f"- Tags: {', '.join(tags)}")

        # Estadísticas de interacción
        call_count = contact.get("call_count") or 0
        last_channel = contact.get("last_interaction_channel")
        if call_count > 0:
            interaction_info = f"- Interacciones previas: {call_count}"
            if last_channel:
                icon = CHANNEL_ICONS.get(last_channel, "")
                interaction_info += f" (último canal: {icon} {last_channel})"
            lines.append(interaction_info)

        # Resumen acumulado
        summary = contact.get("summary")
        if summary:
            lines.append(f"- Resumen: {summary}")

        # Memorias recientes (últimas 3)
        if self.memories:
            lines.append("\n### Interacciones recientes")
            for mem in self.memories[:3]:
                created = mem.get("created_at", "")
                if created:
                    try:
                        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        date_str = dt.strftime("%d/%m/%Y")
                    except (ValueError, TypeError):
                        date_str = created[:10]
                else:
                    date_str = "?"

                channel = mem.get("channel", "call")
                icon = CHANNEL_ICONS.get(channel, "")
                sentiment = mem.get("sentiment", "")
                sentiment_str = f" [{sentiment}]" if sentiment else ""

                lines.append(f"- {date_str} {icon}: {mem.get('summary', '')}{sentiment_str}")

                # Action items pendientes (solo de la última memoria)
                if mem == self.memories[0]:
                    action_items = mem.get("action_items") or []
                    if action_items:
                        items_str = "; ".join(str(a) for a in action_items[:3])
                        lines.append(f"  → Pendiente: {items_str}")

        lines.append("")
        lines.append(
            "USA esta información naturalmente en la conversación. "
            "No recites los datos, úsalos para dar un servicio personalizado."
        )

        return "\n".join(lines)

    async def store(
        self,
        transcript: str,
        agent_id: str | None = None,
        agent_name: str | None = None,
        duration_seconds: int | None = None,
    ) -> None:
        """Analiza la conversación y almacena la memoria.

        Args:
            transcript: Texto de la conversación (líneas "Cliente: ..." / "Agente: ...")
            agent_id: ID del agente que atendió
            agent_name: Nombre del agente
            duration_seconds: Duración de la interacción en segundos
        """
        if not self.contact_id or not transcript or len(transcript) < 20:
            logger.info("store() skip: contact_id=%s, transcript_len=%d", self.contact_id, len(transcript or ""))
            return

        # 1. Analizar conversación con Gemini
        logger.info("Analizando conversación para memoria (contacto %s)...", self.contact_id)
        try:
            analysis = await self._analyze_conversation(transcript)
        except Exception:
            logger.exception("Error en _analyze_conversation")
            analysis = None

        if not analysis:
            logger.warning("No se pudo analizar la conversación para memoria")
            return

        summary = analysis.get("summary", "")
        if not summary:
            logger.warning("Análisis sin summary, abortando store")
            return

        logger.info("Análisis OK: summary='%s...', sentiment=%s", summary[:60], analysis.get("sentiment"))

        # 2. Generar embedding del resumen
        try:
            embedding = await generate_embedding(summary)
            logger.info("Embedding generado: %d dims", len(embedding))
        except Exception:
            logger.exception("Error generando embedding")
            return

        # 3. Guardar memoria
        try:
            # pgvector espera formato string "[0.1, 0.2, ...]"
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
            memory_data = {
                "client_id": self._client_id,
                "contact_id": self.contact_id,
                "summary": summary,
                "embedding": embedding_str,
                "channel": self._channel,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "duration_seconds": duration_seconds,
                "sentiment": analysis.get("sentiment"),
                "topics": analysis.get("topics", []),
                "action_items": analysis.get("action_items", []),
                "extracted_data": analysis.get("extracted_data", {}),
            }
            self._sb.table("memories").insert(memory_data).execute()
            logger.info("Memoria guardada para contacto %s", self.contact_id)
        except Exception:
            logger.exception("Error insertando memoria en DB")
            return

        # 4. Actualizar perfil del contacto
        try:
            await self._update_contact_profile(analysis, embedding)
        except Exception:
            logger.exception("Error actualizando perfil de contacto")

        # 5. Vincular identificadores detectados
        try:
            await self._link_detected_identifiers(analysis)
        except Exception:
            logger.exception("Error vinculando identificadores")

    async def _analyze_conversation(self, transcript: str) -> dict | None:
        """Analiza la conversación con Gemini Flash para extraer datos estructurados."""
        prompt = f"""Analiza esta conversación y extrae la información en JSON.

CONVERSACIÓN:
{transcript[:3000]}

Responde SOLO con JSON válido, sin markdown:
{{
  "summary": "Resumen breve (2-3 frases) de lo que se habló y acordó",
  "sentiment": "positivo|neutral|negativo",
  "topics": ["tema1", "tema2"],
  "action_items": ["pendiente1", "pendiente2"],
  "contact_name": "nombre si se mencionó o null",
  "contact_email": "email si se mencionó o null",
  "contact_phone": "teléfono adicional si se mencionó o null",
  "preferences": {{"clave": "valor detectado"}},
  "key_facts": ["dato importante 1", "dato importante 2"],
  "extracted_data": {{"cualquier otro dato relevante": "valor"}}
}}"""

        try:
            client = _get_gemini()
            response = await client.aio.models.generate_content(
                model=ANALYSIS_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            text = response.text or ""
            return json.loads(text)
        except (json.JSONDecodeError, Exception) as e:
            logger.error("Error analizando conversación: %s", e)
            return None

    async def _update_contact_profile(
        self,
        analysis: dict,
        summary_embedding: list[float],
    ) -> None:
        """Actualiza el perfil del contacto con datos extraídos de la conversación."""
        if not self.contact_id:
            return

        updates: dict = {
            "last_interaction_channel": self._channel,
        }

        # Nombre si no tiene
        contact_name = analysis.get("contact_name")
        if contact_name and not (self.contact or {}).get("name"):
            updates["name"] = contact_name

        # Sentimiento promedio
        new_sentiment = analysis.get("sentiment")
        if new_sentiment:
            updates["average_sentiment"] = new_sentiment

        # Resumen acumulado: combinar con existente
        new_summary = analysis.get("summary", "")
        existing_summary = (self.contact or {}).get("summary") or ""
        if new_summary:
            if existing_summary:
                # Mantener resumen compacto combinando
                combined = f"{existing_summary} | {new_summary}"
                if len(combined) > 1000:
                    combined = combined[-1000:]
                updates["summary"] = combined
            else:
                updates["summary"] = new_summary
            # pgvector espera formato string "[0.1, 0.2, ...]"
            updates["summary_embedding"] = "[" + ",".join(str(v) for v in summary_embedding) + "]"

        # Preferencias: merge con existentes
        new_prefs = analysis.get("preferences") or {}
        if new_prefs:
            existing_prefs = (self.contact or {}).get("preferences") or {}
            merged_prefs = {**existing_prefs, **new_prefs}
            updates["preferences"] = merged_prefs

        # Key facts: merge sin duplicados
        new_facts = analysis.get("key_facts") or []
        if new_facts:
            existing_facts = (self.contact or {}).get("key_facts") or []
            existing_set = set(str(f) for f in existing_facts)
            merged_facts = list(existing_facts)
            for fact in new_facts:
                if str(fact) not in existing_set:
                    merged_facts.append(fact)
            # Mantener solo los últimos 10
            updates["key_facts"] = merged_facts[-10:]

        try:
            self._sb.table("contacts").update(updates).eq("id", self.contact_id).execute()
            logger.info("Perfil de contacto actualizado: %s", self.contact_id)
        except Exception:
            logger.exception("Error actualizando perfil de contacto")

    async def _link_detected_identifiers(self, analysis: dict) -> None:
        """Vincula identificadores detectados en la conversación."""
        if not self.contact_id:
            return

        existing_values = {i.get("identifier_value") for i in self.identifiers}

        identifiers_to_link: list[tuple[str, str]] = []

        email = analysis.get("contact_email")
        if email and email not in existing_values:
            identifiers_to_link.append(("email", email))

        phone = analysis.get("contact_phone")
        if phone and phone not in existing_values:
            identifiers_to_link.append(("phone", phone))

        for id_type, id_value in identifiers_to_link:
            try:
                self._sb.rpc(
                    "link_identifier_to_contact",
                    {
                        "p_client_id": self._client_id,
                        "p_contact_id": self.contact_id,
                        "p_identifier_type": id_type,
                        "p_identifier_value": id_value,
                    },
                ).execute()
                logger.info(
                    "Identificador vinculado: %s=%s → contacto %s",
                    id_type, id_value, self.contact_id,
                )
            except Exception:
                logger.exception("Error vinculando identificador %s=%s", id_type, id_value)
