"""Rutas para asistente IA de prompts — genera y mejora system prompts."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from google import genai
from google.genai import types

from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import GeneratePromptRequest, ImprovePromptRequest, PromptAIResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Referencia: template generico como ejemplo de formato
_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "config" / "prompts" / "templates"


def _load_template_reference() -> str:
    """Carga el template generico.txt como referencia de formato."""
    path = _TEMPLATE_DIR / "generico.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _call_gemini(system_instruction: str, user_prompt: str) -> str:
    """Llama a Gemini 2.5 Flash y retorna el texto generado."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GOOGLE_API_KEY no configurada",
        )
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.8,
        ),
    )
    return response.text.strip()


# Meta-prompt para generar prompts desde cero
_GENERATE_SYSTEM = """\
Eres un experto en diseño de system prompts para agentes de voz telefónica con IA \
en español mexicano. Tu tarea es generar un system prompt completo y optimizado \
para un agente de voz.

## Reglas de voz telefónica (OBLIGATORIAS en el prompt generado):
- Máximo 2 frases por turno. Si necesita explicar más, preguntar si quieren que continúe.
- Siempre terminar con pregunta o siguiente paso concreto.
- Usar muletillas mexicanas naturales: "Mire...", "Claro que sí...", "Perfecto...", "Con gusto..."
- Confirmar datos repitiendo: "Su nombre es María López, ¿verdad?"
- Números de teléfono: repetir dígito por dígito.
- Fechas: incluir día de la semana. "El martes 5 de marzo a las 3 de la tarde."

## Formato de salida:
Genera SOLO el system prompt, sin explicaciones ni comentarios. \
Usa el siguiente template como referencia de estructura y formato:

---
{template_reference}
---

Adapta el contenido al negocio y función específica del usuario. \
Incluye secciones: personalidad, estilo de comunicación, escenarios [INBOUND]/[OUTBOUND] \
según aplique, y 3-5 ejemplos de conversación realistas."""

_GENERATE_CAMPAIGN_SYSTEM = """\
Eres un experto en diseño de scripts para campañas de llamadas outbound con IA \
en español mexicano. Tu tarea es generar un script/system prompt optimizado para \
un agente que hace llamadas salientes.

## Reglas de voz telefónica (OBLIGATORIAS):
- Máximo 2 frases por turno.
- Gancho en los primeros 10 segundos — captar atención inmediata.
- Usar muletillas mexicanas: "Mire...", "Fíjese que...", "Le platico rapidito..."
- Manejar objeciones con empatía, no confrontar.
- Confirmar datos repitiendo.
- Siempre cerrar con siguiente paso concreto.

## Formato de salida:
Genera SOLO el script/prompt del agente, sin explicaciones. \
Incluye: presentación, gancho, pitch, manejo de objeciones, cierre, \
y 3-5 ejemplos de conversación."""

# Meta-prompt para mejorar prompts existentes
_IMPROVE_SYSTEM = """\
Eres un experto en optimización de system prompts para agentes de voz telefónica \
con IA en español mexicano. Tu tarea es mejorar el prompt que te dan.

## Optimizaciones que debes aplicar:
1. **Voz natural mexicana**: agregar muletillas naturales (Mire, Claro que sí, Perfecto, \
Con gusto, Fíjese que). NO sonar robótico.
2. **Brevedad**: máximo 2 frases por turno en los ejemplos. Respuestas concisas.
3. **Personalidad**: agregar calidez y personalidad al agente. Que suene humano.
4. **Estructura**: organizar con secciones claras (personalidad, estilo, escenarios, ejemplos).
5. **Ejemplos**: si no tiene, agregar 3-5 ejemplos de conversación realistas.
6. **Cierre activo**: cada turno debe terminar con pregunta o siguiente paso.
7. **Datos**: confirmar repitiendo. Teléfonos dígito por dígito. Fechas con día de semana.

## Reglas:
- Mantener la intención y contexto original del prompt.
- NO agregar información inventada sobre el negocio.
- NO cambiar el nombre del agente ni del negocio si están definidos.
- Genera SOLO el prompt mejorado, sin explicaciones ni comentarios."""


@router.post("/generate-prompt", response_model=PromptAIResponse)
async def generate_prompt(
    req: GeneratePromptRequest,
    user: CurrentUser = Depends(get_current_user),
) -> PromptAIResponse:
    """Genera un system prompt desde cero usando IA."""
    template_ref = _load_template_reference()

    if req.type == "campaign":
        system = _GENERATE_CAMPAIGN_SYSTEM
        parts = ["Genera un script para campaña outbound con estos datos:"]
        if req.objective:
            parts.append(f"- Objetivo: {req.objective}")
        if req.product:
            parts.append(f"- Producto/servicio: {req.product}")
        if req.hook:
            parts.append(f"- Gancho/apertura: {req.hook}")
        if req.data_to_capture:
            parts.append(f"- Datos a capturar: {req.data_to_capture}")
        if req.objection_handling:
            parts.append(f"- Manejo de objeciones: {req.objection_handling}")
        if req.business_name:
            parts.append(f"- Nombre del negocio: {req.business_name}")
        if req.agent_name:
            parts.append(f"- Nombre del agente: {req.agent_name}")
    else:
        system = _GENERATE_SYSTEM.replace("{template_reference}", template_ref)
        parts = ["Genera un system prompt para un agente de voz con estos datos:"]
        if req.business_name:
            parts.append(f"- Negocio: {req.business_name}")
        if req.business_type:
            parts.append(f"- Giro: {req.business_type}")
        if req.agent_name:
            parts.append(f"- Nombre del agente: {req.agent_name}")
        if req.tone:
            parts.append(f"- Tono: {req.tone}")
        if req.main_function:
            parts.append(f"- Función principal: {req.main_function}")

    user_prompt = "\n".join(parts)
    logger.info("generate_prompt type=%s user=%s", req.type, user.id)

    try:
        result = _call_gemini(system, user_prompt)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en Gemini generate: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error generando prompt: {exc}",
        ) from exc

    return PromptAIResponse(prompt=result)


@router.post("/improve-prompt", response_model=PromptAIResponse)
async def improve_prompt(
    req: ImprovePromptRequest,
    user: CurrentUser = Depends(get_current_user),
) -> PromptAIResponse:
    """Mejora un system prompt existente usando IA."""
    if not req.prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El prompt no puede estar vacío",
        )

    context = "agente de voz inbound" if req.type == "agent" else "campaña outbound"
    user_prompt = (
        f"Mejora el siguiente prompt para {context}. "
        f"Mantenlo en español mexicano:\n\n{req.prompt}"
    )

    logger.info("improve_prompt type=%s user=%s", req.type, user.id)

    try:
        result = _call_gemini(_IMPROVE_SYSTEM, user_prompt)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en Gemini improve: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error mejorando prompt: {exc}",
        ) from exc

    return PromptAIResponse(prompt=result)
