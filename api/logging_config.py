"""Logging estructurado con correlation IDs para la API."""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# ContextVar para el request_id (propagado automáticamente en async)
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Inyecta request_id en cada log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")  # type: ignore[attr-defined]
        return True


import re as _re

# Patrones de PII a enmascarar en logs
_PHONE_PATTERN = _re.compile(r"(?<!\d)(\+?\d{10,15})(?!\d)")
_EMAIL_PATTERN = _re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


class PIIMaskFilter(logging.Filter):
    """Enmascara números de teléfono y emails en logs de producción."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _PHONE_PATTERN.sub(self._mask_phone, record.msg)
            record.msg = _EMAIL_PATTERN.sub(self._mask_email, record.msg)
        if record.args and isinstance(record.args, tuple):
            record.args = tuple(
                self._mask_arg(a) for a in record.args
            )
        return True

    @staticmethod
    def _mask_phone(match: _re.Match) -> str:
        digits = match.group(0)
        return f"***{digits[-4:]}"

    @staticmethod
    def _mask_email(match: _re.Match) -> str:
        email = match.group(0)
        local, domain = email.split("@", 1)
        return f"{local[0]}***@{domain}" if local else f"***@{domain}"

    @staticmethod
    def _mask_arg(arg: object) -> object:
        if isinstance(arg, str):
            arg = _PHONE_PATTERN.sub(lambda m: f"***{m.group(0)[-4:]}", arg)
            arg = _EMAIL_PATTERN.sub(
                lambda m: f"{m.group(0).split('@')[0][0]}***@{m.group(0).split('@')[1]}" if "@" in m.group(0) else "***",
                arg,
            )
        return arg


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware que genera un request_id por petición y lo loguea."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request_id_var.set(rid)

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


def setup_logging(*, json_format: bool = False) -> None:
    """Configura logging estructurado para toda la API.

    Args:
        json_format: Si True, usa formato JSON (para producción).
    """
    if json_format:
        fmt = (
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","request_id":"%(request_id)s",'
            '"message":"%(message)s"}'
        )
    else:
        fmt = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s — %(message)s"

    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.addFilter(PIIMaskFilter())
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Silenciar loggers ruidosos
    for noisy in ("httpcore", "httpx", "hpack", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
