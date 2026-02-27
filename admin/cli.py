"""CLI principal para administración de Voice AI Platform."""

from __future__ import annotations

import typer
from dotenv import load_dotenv

from admin.create_client import app as create_app
from admin.upload_docs import app as upload_app
from admin.assign_phone import app as phone_app
from admin.list_clients import app as list_app
from admin.test_call import app as test_app

load_dotenv()

app = typer.Typer(
    name="voice-ai",
    help="Voice AI Platform — Herramientas de administración",
)

app.add_typer(create_app, name="create", help="Crear nuevo cliente")
app.add_typer(upload_app, name="docs", help="Gestionar documentos")
app.add_typer(phone_app, name="phone", help="Asignar números telefónicos")
app.add_typer(list_app, name="list", help="Listar clientes")
app.add_typer(test_app, name="test", help="Probar agentes")

if __name__ == "__main__":
    app()
