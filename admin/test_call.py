"""Prueba rápida de un agente — crea un room de test en LiveKit."""

from __future__ import annotations

import asyncio
import os

import typer
from dotenv import load_dotenv
from livekit import api
from rich.console import Console
from rich.panel import Panel
from supabase import create_client

load_dotenv()

console = Console()
app = typer.Typer()


async def _create_test_room(slug: str) -> tuple[str, str]:
    """Crea un room de test y genera un token de acceso."""
    lk = api.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )

    room_name = f"test-{slug}"

    # Crear room
    await lk.room.create_room(
        api.CreateRoomRequest(name=room_name, empty_timeout=300)
    )

    # Generar token para conectarse desde el navegador
    token = (
        api.AccessToken(
            api_key=os.environ["LIVEKIT_API_KEY"],
            api_secret=os.environ["LIVEKIT_API_SECRET"],
        )
        .with_identity(f"tester-{slug}")
        .with_name("Tester")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
            )
        )
        .to_jwt()
    )

    await lk.aclose()
    return room_name, token


@app.command()
def test(
    client: str = typer.Option(..., help="Slug del cliente a probar"),
) -> None:
    """Crea un room de test para probar un agente."""
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    result = sb.table("clients").select("name, agent_name").eq("slug", client).limit(1).execute()
    if not result.data:
        console.print(f"[red]Cliente '{client}' no encontrado[/red]")
        raise typer.Exit(1)

    client_name = result.data[0]["name"]
    agent_name = result.data[0]["agent_name"]

    console.print(f"\n[bold cyan]Creando test para: {client_name} ({agent_name})[/bold cyan]\n")

    room_name, token = asyncio.run(_create_test_room(client))

    livekit_url = os.environ["LIVEKIT_URL"].replace("wss://", "")

    console.print(
        Panel(
            f"[bold green]Room de test creado[/bold green]\n\n"
            f"  Room:   {room_name}\n"
            f"  Token:  {token[:50]}...\n\n"
            f"[bold]Para probar desde el navegador:[/bold]\n"
            f"  https://agents-playground.livekit.io/\n\n"
            f"  URL:    wss://{livekit_url}\n"
            f"  Token:  (copia el token completo)\n\n"
            f"[bold]O corre el agente en modo dev:[/bold]\n"
            f"  python -m livekit.agents dev agent/main.py\n",
            title="Test Room",
        )
    )

    # Mostrar token completo para copiar
    console.print(f"\n[dim]Token completo:[/dim]\n{token}\n")


if __name__ == "__main__":
    app()
