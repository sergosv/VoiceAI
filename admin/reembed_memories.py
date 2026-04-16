"""Re-genera embeddings de memories y contacts usando el modelo actual.

Uso:
    python -m admin.reembed_memories
    python -m admin.reembed_memories --batch 50 --only memories
    python -m admin.reembed_memories --dry-run

Se ejecuta después de la migración 057_wipe_legacy_embeddings.sql, que deja
los embeddings en NULL. Este script los rellena leyendo el texto original
(memories.summary y contacts.summary) con generate_embeddings_batch.
"""

from __future__ import annotations

import asyncio
import os

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from supabase import create_client

load_dotenv()

from agent.embeddings import generate_embeddings_batch  # noqa: E402

console = Console()
app = typer.Typer()


def _get_supabase():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


async def _reembed_memories(batch: int, dry_run: bool) -> int:
    sb = _get_supabase()
    total_updated = 0
    page = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed} procesadas"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("[cyan]memories[/cyan]", total=None)

        while True:
            result = (
                sb.table("memories")
                .select("id, summary")
                .is_("embedding", "null")
                .range(page * batch, page * batch + batch - 1)
                .execute()
            )
            rows = result.data or []
            if not rows:
                break

            texts = [r.get("summary", "") or "" for r in rows]
            # Evitar textos vacíos (no tiene sentido embedirlos)
            valid = [(r, t) for r, t in zip(rows, texts) if t.strip()]
            if not valid:
                page += 1
                continue

            valid_texts = [t for _, t in valid]
            embeddings = await generate_embeddings_batch(valid_texts)

            if dry_run:
                console.print(
                    f"[yellow]dry-run[/yellow] página {page}: "
                    f"{len(valid)} memories con embedding de {len(embeddings[0])} dims"
                )
            else:
                for (row, _text), emb in zip(valid, embeddings):
                    sb.table("memories").update({"embedding": emb}).eq(
                        "id", row["id"]
                    ).execute()
                total_updated += len(valid)

            progress.update(task_id, advance=len(rows))
            page += 1

    return total_updated


async def _reembed_contacts(batch: int, dry_run: bool) -> int:
    sb = _get_supabase()
    total_updated = 0
    page = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed} procesados"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("[cyan]contacts[/cyan]", total=None)

        while True:
            result = (
                sb.table("contacts")
                .select("id, summary")
                .is_("summary_embedding", "null")
                .not_.is_("summary", "null")
                .range(page * batch, page * batch + batch - 1)
                .execute()
            )
            rows = result.data or []
            if not rows:
                break

            valid = [r for r in rows if (r.get("summary") or "").strip()]
            if not valid:
                page += 1
                continue

            texts = [r["summary"] for r in valid]
            embeddings = await generate_embeddings_batch(texts)

            if dry_run:
                console.print(
                    f"[yellow]dry-run[/yellow] página {page}: "
                    f"{len(valid)} contacts con embedding de {len(embeddings[0])} dims"
                )
            else:
                for row, emb in zip(valid, embeddings):
                    sb.table("contacts").update({"summary_embedding": emb}).eq(
                        "id", row["id"]
                    ).execute()
                total_updated += len(valid)

            progress.update(task_id, advance=len(rows))
            page += 1

    return total_updated


@app.command()
def main(
    batch: int = typer.Option(50, help="Tamaño de lote para embeddings"),
    only: str = typer.Option(
        "all",
        help="Qué re-embedir: 'memories', 'contacts', o 'all'",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Solo reporta, no escribe",
    ),
) -> None:
    """Re-genera embeddings con el modelo actual para filas con embedding=NULL."""
    if only not in ("all", "memories", "contacts"):
        console.print(f"[red]--only inválido: {only}[/red]")
        raise typer.Exit(1)

    async def _run() -> None:
        mem_count = 0
        ctc_count = 0
        if only in ("all", "memories"):
            console.print("[bold cyan]→ Re-embedir memories[/bold cyan]")
            mem_count = await _reembed_memories(batch, dry_run)
        if only in ("all", "contacts"):
            console.print("[bold cyan]→ Re-embedir contacts[/bold cyan]")
            ctc_count = await _reembed_contacts(batch, dry_run)

        console.print(
            f"\n[green]Listo.[/green] memories actualizadas: {mem_count}, "
            f"contacts actualizados: {ctc_count}"
        )
        if dry_run:
            console.print("[yellow]Modo dry-run — no se escribió nada[/yellow]")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
