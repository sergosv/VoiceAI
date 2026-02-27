"""Lista clientes activos con su estado."""

from __future__ import annotations

import os

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from supabase import create_client

load_dotenv()

console = Console()
app = typer.Typer()


@app.command()
def list_all(
    active_only: bool = typer.Option(True, help="Solo mostrar clientes activos"),
) -> None:
    """Lista todos los clientes."""
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    query = sb.table("clients").select("*").order("created_at", desc=True)
    if active_only:
        query = query.eq("is_active", True)

    result = query.execute()

    if not result.data:
        console.print("[yellow]No hay clientes registrados[/yellow]")
        return

    table = Table(title="Clientes Voice AI Platform")
    table.add_column("Slug", style="cyan")
    table.add_column("Nombre")
    table.add_column("Agente")
    table.add_column("Teléfono", style="green")
    table.add_column("Tipo")
    table.add_column("Store", style="dim")
    table.add_column("Activo")

    for row in result.data:
        table.add_row(
            row["slug"],
            row["name"],
            row["agent_name"],
            row.get("phone_number") or "-",
            row.get("business_type", "generic"),
            "Si" if row.get("file_search_store_id") else "No",
            "Si" if row.get("is_active") else "No",
        )

    console.print(table)


if __name__ == "__main__":
    app()
