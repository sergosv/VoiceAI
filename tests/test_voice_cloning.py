"""Tests para clonación de voces — servicio + endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import CurrentUser, get_current_user

client = TestClient(app, raise_server_exceptions=False)

ADMIN_USER = CurrentUser(
    id="admin-uuid", auth_user_id="auth-admin", email="admin@test.com",
    role="admin", client_id=None,
)

CLIENT_USER = CurrentUser(
    id="client-uuid", auth_user_id="auth-client", email="cli@test.com",
    role="client", client_id="client-1",
)

CLIENT_USER_2 = CurrentUser(
    id="client-uuid-2", auth_user_id="auth-client-2", email="cli2@test.com",
    role="client", client_id="client-2",
)


# ── Tests del servicio voice_cloning ──────────────────


@pytest.mark.asyncio
async def test_clone_voice_cartesia_success():
    """Clonación exitosa en Cartesia retorna voice ID."""
    from api.services.voice_cloning import clone_voice_cartesia

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "cart-voice-123",
        "name": "Test Voice",
        "language": "es",
    }

    with patch("api.services.voice_cloning.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await clone_voice_cartesia(
            audio_data=b"fake_audio_data_" * 100,
            name="Test Voice",
            language="es",
            api_key="test-key",
        )

    assert result["id"] == "cart-voice-123"
    assert result["name"] == "Test Voice"


@pytest.mark.asyncio
async def test_clone_voice_cartesia_error():
    """Error en Cartesia lanza RuntimeError."""
    from api.services.voice_cloning import clone_voice_cartesia

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request: invalid audio"

    with patch("api.services.voice_cloning.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        with pytest.raises(RuntimeError, match="Error clonando voz en Cartesia"):
            await clone_voice_cartesia(
                audio_data=b"fake_audio",
                name="Test",
                api_key="test-key",
            )


@pytest.mark.asyncio
async def test_clone_voice_elevenlabs_success():
    """Clonación exitosa en ElevenLabs retorna voice_id."""
    from api.services.voice_cloning import clone_voice_elevenlabs

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "voice_id": "el-voice-456",
        "name": "Test EL Voice",
    }

    with patch("api.services.voice_cloning.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await clone_voice_elevenlabs(
            audio_data=b"fake_audio_data_" * 100,
            name="Test EL Voice",
            api_key="test-el-key",
        )

    assert result["voice_id"] == "el-voice-456"


@pytest.mark.asyncio
async def test_clone_voice_elevenlabs_no_key():
    """Sin API key de ElevenLabs lanza ValueError."""
    from api.services.voice_cloning import clone_voice_elevenlabs

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="API key de ElevenLabs requerida"):
            await clone_voice_elevenlabs(
                audio_data=b"fake",
                name="Test",
            )


@pytest.mark.asyncio
async def test_delete_voice_cartesia_success():
    """Eliminación exitosa en Cartesia retorna True."""
    from api.services.voice_cloning import delete_voice_cartesia

    mock_response = MagicMock()
    mock_response.status_code = 204

    with patch("api.services.voice_cloning.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.delete = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await delete_voice_cartesia("cart-voice-123", api_key="test-key")

    assert result is True


@pytest.mark.asyncio
async def test_delete_voice_cartesia_failure():
    """Error en eliminación retorna False."""
    from api.services.voice_cloning import delete_voice_cartesia

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"

    with patch("api.services.voice_cloning.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.delete = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await delete_voice_cartesia("nonexistent", api_key="test-key")

    assert result is False


@pytest.mark.asyncio
async def test_preview_voice_cartesia_success():
    """Preview genera bytes de audio."""
    from api.services.voice_cloning import preview_voice_cartesia

    fake_wav = b"RIFF" + b"\x00" * 1000

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = fake_wav

    with patch("api.services.voice_cloning.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await preview_voice_cartesia(
            voice_id="cart-voice-123",
            text="Hola mundo",
            api_key="test-key",
        )

    assert len(result) > 0
    assert result[:4] == b"RIFF"


@pytest.mark.asyncio
async def test_cartesia_no_api_key():
    """Sin CARTESIA_API_KEY env var lanza ValueError."""
    from api.services.voice_cloning import clone_voice_cartesia

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="CARTESIA_API_KEY no configurada"):
            await clone_voice_cartesia(
                audio_data=b"fake",
                name="Test",
            )


# ── Tests de endpoints ────────────────────────────────


class TestCloneEndpoint:
    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_rejects_small_audio(self):
        """Audio demasiado pequeño es rechazado."""
        resp = client.post(
            "/api/voices/clone",
            data={
                "name": "Test Voice",
                "client_id": "client-1",
                "language": "es",
                "provider": "cartesia",
            },
            files={"audio": ("tiny.wav", b"tiny", "audio/wav")},
        )
        assert resp.status_code == 400

    def test_rejects_large_audio(self):
        """Audio demasiado grande es rechazado."""
        large_audio = b"\x00" * (11 * 1024 * 1024)
        resp = client.post(
            "/api/voices/clone",
            data={
                "name": "Test Voice",
                "client_id": "client-1",
                "language": "es",
                "provider": "cartesia",
            },
            files={"audio": ("big.wav", large_audio, "audio/wav")},
        )
        assert resp.status_code == 400

    def test_rejects_bad_format(self):
        """Formato no soportado es rechazado."""
        resp = client.post(
            "/api/voices/clone",
            data={
                "name": "Test Voice",
                "client_id": "client-1",
                "language": "es",
                "provider": "cartesia",
            },
            files={"audio": ("doc.pdf", b"fake_pdf_" * 200, "application/pdf")},
        )
        assert resp.status_code == 400

    @patch("api.routes.voices.clone_voice_cartesia", new_callable=AsyncMock)
    @patch("api.routes.voices.get_supabase")
    def test_clone_success(self, mock_get_sb, mock_clone):
        """Clonación exitosa end-to-end."""
        mock_clone.return_value = {"id": "cart-new-voice", "name": "Mi Voz"}

        mock_sb = MagicMock()
        # agents.select (BYOK check) -> no data
        agent_q = MagicMock()
        agent_q.eq.return_value = agent_q
        agent_q.limit.return_value = agent_q
        agent_q.execute.return_value = MagicMock(data=[])

        # cloned_voices.insert
        insert_q = MagicMock()
        insert_q.execute.return_value = MagicMock(data=[{
            "id": "cv-new",
            "client_id": "client-1",
            "agent_id": None,
            "provider": "cartesia",
            "external_voice_id": "cart-new-voice",
            "name": "Mi Voz",
            "language": "es",
            "description": "",
            "duration_seconds": None,
            "status": "ready",
            "created_at": "2026-03-08T12:00:00Z",
        }])

        def table_fn(name):
            t = MagicMock()
            if name == "agents":
                t.select.return_value = agent_q
            elif name == "cloned_voices":
                t.insert.return_value = insert_q
            return t

        mock_sb.table.side_effect = table_fn
        mock_get_sb.return_value = mock_sb

        audio_data = b"\x00" * 5000
        resp = client.post(
            "/api/voices/clone",
            data={
                "name": "Mi Voz",
                "client_id": "client-1",
                "language": "es",
                "provider": "cartesia",
            },
            files={"audio": ("sample.wav", audio_data, "audio/wav")},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Mi Voz"
        assert data["external_voice_id"] == "cart-new-voice"
        assert data["status"] == "ready"


class TestListClonedVoices:
    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch("api.routes.voices.get_supabase")
    def test_empty_list(self, mock_get_sb):
        """Listar sin voces retorna lista vacía."""
        mock_sb = MagicMock()
        q = MagicMock()
        q.eq.return_value = q
        q.order.return_value = q
        q.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value.select.return_value = q
        mock_get_sb.return_value = mock_sb

        resp = client.get("/api/voices/cloned/client-1")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("api.routes.voices.get_supabase")
    def test_with_data(self, mock_get_sb):
        """Listar retorna voces clonadas."""
        mock_sb = MagicMock()
        q = MagicMock()
        q.eq.return_value = q
        q.order.return_value = q
        q.execute.return_value = MagicMock(data=[{
            "id": "cv-1",
            "client_id": "client-1",
            "agent_id": None,
            "provider": "cartesia",
            "external_voice_id": "cart-123",
            "name": "Mi Voz",
            "language": "es",
            "description": "Voz del dueno",
            "duration_seconds": 8.5,
            "status": "ready",
            "created_at": "2026-03-08T10:00:00Z",
        }])
        mock_sb.table.return_value.select.return_value = q
        mock_get_sb.return_value = mock_sb

        resp = client.get("/api/voices/cloned/client-1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Mi Voz"
        assert data[0]["external_voice_id"] == "cart-123"


class TestDeleteClonedVoice:
    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch("api.routes.voices.get_supabase")
    def test_not_found(self, mock_get_sb):
        """Eliminar voz inexistente retorna 404."""
        mock_sb = MagicMock()
        q = MagicMock()
        q.eq.return_value = q
        q.limit.return_value = q
        q.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value.select.return_value = q
        mock_get_sb.return_value = mock_sb

        resp = client.delete("/api/voices/cloned/nonexistent-id")
        assert resp.status_code == 404

    @patch("api.routes.voices.delete_voice_cartesia", new_callable=AsyncMock, return_value=True)
    @patch("api.routes.voices.get_supabase")
    def test_success(self, mock_get_sb, mock_delete):
        """Eliminar voz existente funciona."""
        mock_sb = MagicMock()

        select_q = MagicMock()
        select_q.eq.return_value = select_q
        select_q.limit.return_value = select_q
        select_q.execute.return_value = MagicMock(data=[{
            "id": "cv-1",
            "client_id": "client-1",
            "agent_id": None,
            "provider": "cartesia",
            "external_voice_id": "cart-123",
        }])

        delete_q = MagicMock()
        delete_q.eq.return_value = delete_q
        delete_q.execute.return_value = MagicMock(data=[])

        t = MagicMock()
        t.select.return_value = select_q
        t.delete.return_value = delete_q
        mock_sb.table.return_value = t
        mock_get_sb.return_value = mock_sb

        resp = client.delete("/api/voices/cloned/cv-1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"


class TestAssignVoice:
    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch("api.routes.voices.get_supabase")
    def test_assign_success(self, mock_get_sb):
        """Asignar voz a agente actualiza voice_config."""
        mock_sb = MagicMock()

        call_count = 0

        def table_fn(name):
            nonlocal call_count
            call_count += 1
            t = MagicMock()
            q = MagicMock()
            q.eq.return_value = q
            q.limit.return_value = q

            if name == "cloned_voices" and call_count == 1:
                q.execute.return_value = MagicMock(data=[{
                    "id": "cv-1",
                    "client_id": "client-1",
                    "provider": "cartesia",
                    "external_voice_id": "cart-123",
                }])
                t.select.return_value = q
            elif name == "agents":
                q.execute.return_value = MagicMock(data=[{
                    "voice_config": {"provider": "cartesia"},
                    "client_id": "client-1",
                }])
                t.select.return_value = q
                uq = MagicMock()
                uq.eq.return_value = uq
                uq.execute.return_value = MagicMock(data=[{}])
                t.update.return_value = uq
            else:
                uq = MagicMock()
                uq.eq.return_value = uq
                uq.execute.return_value = MagicMock(data=[{}])
                t.update.return_value = uq

            return t

        mock_sb.table.side_effect = table_fn
        mock_get_sb.return_value = mock_sb

        resp = client.post("/api/voices/cloned/cv-1/assign?agent_id=agent-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "assigned"
        assert data["external_voice_id"] == "cart-123"


class TestAccessControl:
    def test_client_cannot_access_other_clients_voices(self):
        """Un cliente no puede ver voces de otro cliente."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER_2
        try:
            resp = client.get("/api/voices/cloned/client-1")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_client_cannot_clone_for_other_client(self):
        """Un cliente no puede clonar para otro cliente."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER_2
        try:
            resp = client.post(
                "/api/voices/clone",
                data={
                    "name": "Hack",
                    "client_id": "client-1",
                    "provider": "cartesia",
                },
                files={"audio": ("s.wav", b"\x00" * 5000, "audio/wav")},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()
