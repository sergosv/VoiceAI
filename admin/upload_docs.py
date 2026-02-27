"""Sube documentos al FileSearchStore de un cliente en Gemini."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from supabase import create_client

load_dotenv()

from api.services.document_service import (
    save_document_record,
    upload_document_to_gemini,
)

console = Console()
app = typer.Typer()


def _get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _get_client_store(slug: str) -> tuple[str, str]:
    """Obtiene client_id y file_search_store_id por slug."""
    sb = _get_supabase()
    result = (
        sb.table("clients")
        .select("id, file_search_store_id")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )
    if not result.data:
        console.print(f"[red]Cliente '{slug}' no encontrado[/red]")
        raise typer.Exit(1)

    row = result.data[0]
    if not row["file_search_store_id"]:
        console.print(f"[red]Cliente '{slug}' no tiene FileSearchStore[/red]")
        raise typer.Exit(1)

    return row["id"], row["file_search_store_id"]


@app.command()
def upload(
    client: str = typer.Option(..., help="Slug del cliente"),
    file: Path = typer.Option(..., help="Ruta al archivo a subir"),
    description: str = typer.Option("", help="Descripción del documento"),
) -> None:
    """Sube un documento al FileSearchStore de un cliente."""
    if not file.exists():
        console.print(f"[red]Archivo no encontrado: {file}[/red]")
        raise typer.Exit(1)

    client_id, store_id = _get_client_store(client)
    file_size = file.stat().st_size
    file_type = file.suffix.lstrip(".")

    console.print(f"\n[bold cyan]Subiendo: {file.name}[/bold cyan]")
    console.print(f"  Cliente: {client}")
    console.print(f"  Store:   {store_id}")
    console.print(f"  Tamaño:  {file_size / 1024:.1f} KB\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Subiendo e indexando...", total=None)
        upload_document_to_gemini(str(file), store_id, os.environ["GOOGLE_API_KEY"])
        progress.update(task, description="[green]Indexado completamente")

    # Guardar referencia en DB
    sb = _get_supabase()
    save_document_record(
        sb,
        client_id=client_id,
        filename=file.name,
        file_type=file_type,
        file_size_bytes=file_size,
        description=description or f"Documento {file.name}",
    )

    console.print(f"\n[bold green]Documento '{file.name}' subido exitosamente.[/bold green]\n")


@app.command()
def list_docs(
    client: str = typer.Option(..., help="Slug del cliente"),
) -> None:
    """Lista documentos de un cliente."""
    sb = _get_supabase()
    result = (
        sb.table("clients")
        .select("id")
        .eq("slug", client)
        .limit(1)
        .execute()
    )
    if not result.data:
        console.print(f"[red]Cliente '{client}' no encontrado[/red]")
        raise typer.Exit(1)

    client_id = result.data[0]["id"]
    docs = (
        sb.table("documents")
        .select("*")
        .eq("client_id", client_id)
        .order("uploaded_at", desc=True)
        .execute()
    )

    if not docs.data:
        console.print(f"[yellow]No hay documentos para '{client}'[/yellow]")
        return

    console.print(f"\n[bold]Documentos de {client}:[/bold]\n")
    for doc in docs.data:
        status_color = "green" if doc["indexing_status"] == "indexed" else "yellow"
        console.print(
            f"  [{status_color}]{doc['indexing_status']:8s}[/{status_color}] "
            f"{doc['filename']:30s} "
            f"{doc.get('file_size_bytes', 0) / 1024:.1f} KB  "
            f"[dim]{doc['uploaded_at'][:10]}[/dim]"
        )
    console.print()


if __name__ == "__main__":
    app()
