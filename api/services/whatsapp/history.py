"""Serialización de historial Gemini Content ↔ JSONB."""

from __future__ import annotations

from google.genai import types


def serialize_history(contents: list[types.Content]) -> list[dict]:
    """Convierte lista de Gemini Content a lista de dicts para JSONB."""
    result: list[dict] = []
    for content in contents:
        parts_data: list[dict] = []
        for part in content.parts:
            if part.text is not None:
                parts_data.append({"type": "text", "text": part.text})
            elif part.function_call is not None:
                fc = part.function_call
                parts_data.append({
                    "type": "function_call",
                    "name": fc.name,
                    "args": dict(fc.args) if fc.args else {},
                })
            elif part.function_response is not None:
                fr = part.function_response
                parts_data.append({
                    "type": "function_response",
                    "name": fr.name,
                    "response": dict(fr.response) if fr.response else {},
                })
            # Otros tipos de parts se omiten (no aplican a texto WA)

        result.append({
            "role": content.role,
            "parts": parts_data,
        })
    return result


def deserialize_history(data: list[dict]) -> list[types.Content]:
    """Convierte lista de dicts JSONB a lista de Gemini Content."""
    contents: list[types.Content] = []
    for item in data:
        role = item.get("role", "user")
        parts: list[types.Part] = []

        for p in item.get("parts", []):
            ptype = p.get("type", "text")
            if ptype == "text":
                parts.append(types.Part.from_text(text=p.get("text", "")))
            elif ptype == "function_call":
                parts.append(types.Part(
                    function_call=types.FunctionCall(
                        name=p.get("name", ""),
                        args=p.get("args", {}),
                    )
                ))
            elif ptype == "function_response":
                parts.append(types.Part.from_function_response(
                    name=p.get("name", ""),
                    response=p.get("response", {}),
                ))

        if parts:
            contents.append(types.Content(role=role, parts=parts))

    return contents
