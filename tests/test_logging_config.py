"""Tests para api/logging_config.py — structured logging con correlation IDs."""

import logging

import pytest


def test_request_id_filter_default():
    """RequestIdFilter inyecta request_id='-' por default."""
    from api.logging_config import RequestIdFilter

    f = RequestIdFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
    assert f.filter(record) is True
    assert record.request_id == "-"


def test_request_id_filter_with_contextvar():
    """RequestIdFilter usa el valor del ContextVar."""
    from api.logging_config import RequestIdFilter, request_id_var

    token = request_id_var.set("abc123")
    try:
        f = RequestIdFilter()
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        f.filter(record)
        assert record.request_id == "abc123"
    finally:
        request_id_var.reset(token)


def test_setup_logging_text():
    """setup_logging(json_format=False) no explota."""
    from api.logging_config import setup_logging

    setup_logging(json_format=False)
    logger = logging.getLogger("test_setup")
    # Verificar que el handler tiene el filter
    root = logging.getLogger()
    assert any(
        isinstance(f, type) or hasattr(f, "filter")
        for h in root.handlers
        for f in h.filters
    )


def test_setup_logging_json():
    """setup_logging(json_format=True) no explota."""
    from api.logging_config import setup_logging

    setup_logging(json_format=True)


def test_request_id_middleware_generates_id():
    """RequestIdMiddleware genera X-Request-ID en la respuesta."""
    from starlette.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    from api.logging_config import RequestIdMiddleware

    async def home(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/", home)])
    app.add_middleware(RequestIdMiddleware)

    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) == 12


def test_request_id_middleware_passes_client_id():
    """RequestIdMiddleware usa X-Request-ID del cliente si se envía."""
    from starlette.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    from api.logging_config import RequestIdMiddleware

    async def home(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/", home)])
    app.add_middleware(RequestIdMiddleware)

    client = TestClient(app)
    resp = client.get("/", headers={"X-Request-ID": "my-custom-id"})
    assert resp.headers["X-Request-ID"] == "my-custom-id"
