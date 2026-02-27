"""Crea un nuevo cliente en DB y su FileSearchStore en Gemini."""

from __future__ import annotations

import os

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from supabase import create_client

load_dotenv()

from api.services.client_service import (
    build_greeting,
    build_system_prompt,
    create_client_in_db,
    create_gemini_store,
    load_voice_id,
)

console = Console()
app = typer.Typer()


def _get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


@app.command()
def create(
    name: str = typer.Option(..., help="Nombre del negocio"),
    slug: str = typer.Option(..., help="Slug único (ej: dr-garcia)"),
    business_type: str = typer.Option("generic", help="Tipo: dental, gym, restaurant, generic"),
    agent_name: str = typer.Option("María", help="Nombre del agente de voz"),
    voice: str = typer.Option("es_female_warm", help="Key de voz del catálogo"),
    language: str = typer.Option("es", help="Idioma: es, en, es-en"),
    greeting: str = typer.Option(None, help="Saludo personalizado (auto-genera si no se da)"),
    system_prompt: str = typer.Option(None, help="System prompt completo (usa template si no se da)"),
    owner_email: str = typer.Option(None, help="Email del dueño del negocio"),
    skip_store: bool = typer.Option(False, help="No crear FileSearchStore en Gemini"),
) -> None:
    """Crea un nuevo cliente con su FileSearchStore."""
    console.print(f"\n[bold cyan]Creando cliente: {name}[/bold cyan]\n")

    voice_id = load_voice_id(voice)

    if not greeting:
        greeting = build_greeting(name, agent_name)

    if not system_prompt:
        system_prompt = build_system_prompt(business_type, agent_name, name, language)

    # Crear FileSearchStore en Gemini
    store_id = None
    store_name = None
    if not skip_store:
        console.print("[yellow]Creando FileSearchStore en Gemini...[/yellow]")
        store_id, store_name = create_gemini_store(slug, os.environ["GOOGLE_API_KEY"])
        console.print(f"[green]Store creado: {store_id}[/green]")

    # Insertar en Supabase
    console.print("[yellow]Insertando en base de datos...[/yellow]")
    sb = _get_supabase()
    row = create_client_in_db(
        sb,
        name=name,
        slug=slug,
        business_type=business_type,
        agent_name=agent_name,
        language=language,
        voice_id=voice_id,
        greeting=greeting,
        system_prompt=system_prompt,
        store_id=store_id,
        store_name=store_name,
        owner_email=owner_email,
    )

    console.print(
        Panel(
            f"[bold green]Cliente creado exitosamente[/bold green]\n\n"
            f"  ID:     {row['id']}\n"
            f"  Nombre: {name}\n"
            f"  Slug:   {slug}\n"
            f"  Agente: {agent_name}\n"
            f"  Voz:    {voice}\n"
            f"  Store:  {store_id or 'N/A'}\n",
            title="Resultado",
        )
    )
    console.print(
        "\n[dim]Siguiente paso: sube documentos con upload_docs.py "
        f"--client {slug} --file ./docs/archivo.pdf[/dim]\n"
    )


if __name__ == "__main__":
    app()
