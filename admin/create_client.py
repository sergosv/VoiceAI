"""Crea un nuevo cliente en DB y su FileSearchStore en Gemini."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from google import genai
from rich.console import Console
from rich.panel import Panel
from supabase import create_client

load_dotenv()

console = Console()
app = typer.Typer()

CONFIG_DIR = Path(__file__).parent.parent / "config"


def _get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _get_gemini():
    return genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


def _load_voice_id(voice_key: str) -> str:
    """Obtiene voice_id del catálogo de voces."""
    voices_file = CONFIG_DIR / "voices.json"
    with open(voices_file) as f:
        voices = json.load(f)
    voice = voices["voices"].get(voice_key)
    if not voice:
        available = ", ".join(voices["voices"].keys())
        console.print(f"[red]Voz '{voice_key}' no encontrada. Disponibles: {available}[/red]")
        raise typer.Exit(1)
    return voice["id"]


def _load_prompt_template(business_type: str) -> str:
    """Carga template de prompt por tipo de negocio."""
    prompt_file = CONFIG_DIR / "prompts" / f"{business_type}.md"
    if not prompt_file.exists():
        prompt_file = CONFIG_DIR / "prompts" / "generic.md"
    return prompt_file.read_text(encoding="utf-8")


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

    voice_id = _load_voice_id(voice)

    # Generar greeting si no se proporcionó
    if not greeting:
        greeting = (
            f"Hola, bienvenido a {name}. Soy {agent_name}, su asistente virtual. "
            f"¿En qué puedo ayudarle?"
        )

    # Cargar system prompt de template si no se proporcionó
    if not system_prompt:
        template = _load_prompt_template(business_type)
        system_prompt = template.format(
            agent_name=agent_name,
            business_name=name,
            business_type=business_type,
            language="español" if language == "es" else "English" if language == "en" else "español e inglés",
            tone="cálido" if business_type == "dental" else "amable",
        )

    # Crear FileSearchStore en Gemini
    store_id = None
    store_name = None
    if not skip_store:
        console.print("[yellow]Creando FileSearchStore en Gemini...[/yellow]")
        gemini = _get_gemini()
        store = gemini.file_search_stores.create(
            config={"display_name": f"store-{slug}"}
        )
        store_id = store.name
        store_name = f"store-{slug}"
        console.print(f"[green]Store creado: {store_id}[/green]")

    # Insertar en Supabase
    console.print("[yellow]Insertando en base de datos...[/yellow]")
    sb = _get_supabase()
    data = {
        "name": name,
        "slug": slug,
        "business_type": business_type,
        "agent_name": agent_name,
        "language": language,
        "voice_id": voice_id,
        "greeting": greeting,
        "system_prompt": system_prompt,
        "file_search_store_id": store_id,
        "file_search_store_name": store_name,
        "owner_email": owner_email,
    }
    result = sb.table("clients").insert(data).execute()
    client_id = result.data[0]["id"]

    console.print(
        Panel(
            f"[bold green]Cliente creado exitosamente[/bold green]\n\n"
            f"  ID:     {client_id}\n"
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
