"""Guardrails y safety layer para respuestas del agente.

Valida las respuestas del agente antes de enviarlas al usuario,
detectando temas prohibidos, prompt injection del caller, y
contenido potencialmente peligroso.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GuardrailsConfig:
    """Configuración de guardrails por agente."""

    enabled: bool = False
    prohibited_topics: list[str] = field(default_factory=list)
    """Temas que el agente NO debe mencionar (ej: precios competencia, datos legales)."""
    blocked_patterns: list[str] = field(default_factory=list)
    """Regex patterns que se bloquean en la respuesta del agente."""
    require_disclaimer: str | None = None
    """Disclaimer que debe incluirse en ciertos contextos."""
    max_response_length: int = 500
    """Máximo de caracteres por respuesta (evita monólogos)."""
    detect_prompt_injection: bool = True
    """Detectar intentos de prompt injection del caller."""

    @classmethod
    def from_dict(cls, data: dict | None) -> GuardrailsConfig:
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            prohibited_topics=data.get("prohibited_topics", []),
            blocked_patterns=data.get("blocked_patterns", []),
            require_disclaimer=data.get("require_disclaimer"),
            max_response_length=data.get("max_response_length", 500),
            detect_prompt_injection=data.get("detect_prompt_injection", True),
        )


# Patrones comunes de prompt injection en llamadas
_INJECTION_PATTERNS = [
    r"(?i)ignor[ae]\s+(todas?\s+las?\s+)?instrucciones",
    r"(?i)ignore\s+(all\s+)?(previous\s+)?instructions",
    r"(?i)olvida\s+(todo|tus\s+instrucciones)",
    r"(?i)forget\s+(your|all)\s+(instructions|rules)",
    r"(?i)ahora\s+eres\s+(un|una)",
    r"(?i)now\s+you\s+are\s+a",
    r"(?i)actua\s+como\s+si",
    r"(?i)pretend\s+(you\s+are|to\s+be)",
    r"(?i)nuevo\s+sistema?\s+prompt",
    r"(?i)system\s+prompt",
    r"(?i)repite\s+tus?\s+instrucciones",
    r"(?i)repeat\s+your\s+instructions",
    r"(?i)dime\s+tu\s+prompt",
    r"(?i)tell\s+me\s+your\s+prompt",
]


@dataclass
class GuardrailResult:
    """Resultado de la validación de guardrails."""

    passed: bool
    violations: list[str] = field(default_factory=list)
    modified_text: str | None = None
    """Texto modificado si se aplicó un fix automático."""


class GuardrailsEngine:
    """Valida respuestas del agente y inputs del usuario."""

    def __init__(self, config: GuardrailsConfig) -> None:
        self._config = config
        self._compiled_patterns: list[re.Pattern] = []
        self._compiled_injection: list[re.Pattern] = []
        self._violations_count = 0

        # Compilar patterns de bloqueo
        for pattern in config.blocked_patterns:
            try:
                self._compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error:
                logger.warning("Patrón de guardrail inválido: %s", pattern)

        # Compilar patterns de injection
        for pattern in _INJECTION_PATTERNS:
            try:
                self._compiled_injection.append(re.compile(pattern))
            except re.error:
                pass

    @property
    def violations_count(self) -> int:
        return self._violations_count

    def check_agent_response(self, text: str) -> GuardrailResult:
        """Valida la respuesta del agente antes de enviarla.

        Returns:
            GuardrailResult con el resultado de la validación.
        """
        violations: list[str] = []
        modified = text

        # 1. Verificar temas prohibidos
        text_lower = text.lower()
        for topic in self._config.prohibited_topics:
            if topic.lower() in text_lower:
                violations.append(f"Tema prohibido mencionado: '{topic}'")

        # 2. Verificar patrones bloqueados
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                violations.append(f"Patrón bloqueado detectado: {pattern.pattern}")

        # 3. Verificar longitud máxima
        if len(text) > self._config.max_response_length:
            modified = text[:self._config.max_response_length]
            violations.append(
                f"Respuesta truncada de {len(text)} a {self._config.max_response_length} chars"
            )

        if violations:
            self._violations_count += len(violations)
            for v in violations:
                logger.warning("Guardrail violation: %s", v)

        return GuardrailResult(
            passed=len(violations) == 0,
            violations=violations,
            modified_text=modified if modified != text else None,
        )

    def check_user_input(self, text: str) -> GuardrailResult:
        """Detecta prompt injection en el input del usuario.

        Returns:
            GuardrailResult indicando si se detectó injection.
        """
        if not self._config.detect_prompt_injection:
            return GuardrailResult(passed=True)

        violations: list[str] = []

        for pattern in self._compiled_injection:
            match = pattern.search(text)
            if match:
                violations.append(
                    f"Posible prompt injection: '{match.group()}'"
                )

        if violations:
            self._violations_count += len(violations)
            for v in violations:
                logger.warning("Guardrail (input): %s", v)

        return GuardrailResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def get_summary(self) -> dict:
        """Resumen de guardrails para la llamada."""
        return {
            "total_violations": self._violations_count,
            "prohibited_topics": self._config.prohibited_topics,
            "injection_detection": self._config.detect_prompt_injection,
        }
