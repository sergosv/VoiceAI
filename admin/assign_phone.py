"""Asigna un número Twilio a un cliente y configura SIP trunk en LiveKit."""

from __future__ import annotations

import asyncio
import os

import typer
from dotenv import load_dotenv
from livekit import api
from rich.console import Console
from rich.panel import Panel
from supabase import create_client
from twilio.rest import Client as TwilioClient

load_dotenv()

console = Console()
app = typer.Typer()


def _get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _get_twilio():
    return TwilioClient(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])


async def _setup_livekit_sip(phone_number: str) -> tuple[str, str]:
    """Crea SIP trunk y dispatch rule en LiveKit."""
    lk = api.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )

    # Crear SIP inbound trunk
    trunk = await lk.sip.create_sip_inbound_trunk(
        api.CreateSIPInboundTrunkRequest(
            trunk=api.SIPInboundTrunkInfo(
                name=f"twilio-{phone_number}",
                numbers=[phone_number],
                allowed_addresses=[
                    "54.172.60.0/23",   # Twilio North America
                    "54.244.51.0/24",   # Twilio US West
                    "34.203.250.0/23",  # Twilio US East
                ],
            )
        )
    )
    trunk_id = trunk.sip_trunk_id

    # Crear dispatch rule
    rule = await lk.sip.create_sip_dispatch_rule(
        api.CreateSIPDispatchRuleRequest(
            name=f"route-{phone_number}",
            rule=api.SIPDispatchRule(
                dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                    room_prefix="call-",
                )
            ),
            trunk_ids=[trunk_id],
        )
    )

    await lk.aclose()
    return trunk_id, rule.sip_dispatch_rule_id


@app.command()
def assign(
    client: str = typer.Option(..., help="Slug del cliente"),
    number: str = typer.Option(..., help="Número Twilio (ej: +5219991112233)"),
    skip_livekit: bool = typer.Option(False, help="No configurar SIP en LiveKit"),
) -> None:
    """Asigna un número de teléfono Twilio a un cliente."""
    sb = _get_supabase()

    # Verificar que el cliente existe
    result = sb.table("clients").select("id, name").eq("slug", client).limit(1).execute()
    if not result.data:
        console.print(f"[red]Cliente '{client}' no encontrado[/red]")
        raise typer.Exit(1)

    client_id = result.data[0]["id"]
    client_name = result.data[0]["name"]

    console.print(f"\n[bold cyan]Asignando {number} a {client_name}[/bold cyan]\n")

    # Verificar número en Twilio
    twilio = _get_twilio()
    try:
        incoming_numbers = twilio.incoming_phone_numbers.list(phone_number=number)
        if not incoming_numbers:
            console.print(f"[red]Número {number} no encontrado en tu cuenta Twilio[/red]")
            raise typer.Exit(1)
        phone_sid = incoming_numbers[0].sid
        console.print(f"[green]Número verificado en Twilio: {phone_sid}[/green]")
    except Exception as e:
        console.print(f"[red]Error verificando número en Twilio: {e}[/red]")
        raise typer.Exit(1)

    # Configurar SIP en LiveKit
    trunk_id = None
    if not skip_livekit:
        console.print("[yellow]Configurando SIP trunk en LiveKit...[/yellow]")
        try:
            trunk_id, rule_id = asyncio.run(_setup_livekit_sip(number))
            console.print(f"[green]Trunk: {trunk_id}[/green]")
            console.print(f"[green]Dispatch Rule: {rule_id}[/green]")
        except Exception as e:
            console.print(f"[red]Error configurando LiveKit SIP: {e}[/red]")
            console.print("[yellow]Continuando sin SIP. Configúralo manualmente.[/yellow]")

    # Actualizar DB
    update_data = {
        "phone_number": number,
        "twilio_phone_sid": phone_sid,
    }
    if trunk_id:
        update_data["sip_trunk_id"] = trunk_id

    sb.table("clients").update(update_data).eq("id", client_id).execute()

    console.print(
        Panel(
            f"[bold green]Número asignado exitosamente[/bold green]\n\n"
            f"  Cliente:  {client_name}\n"
            f"  Número:   {number}\n"
            f"  Twilio:   {phone_sid}\n"
            f"  SIP Trunk: {trunk_id or 'No configurado'}\n",
            title="Resultado",
        )
    )

    if not skip_livekit:
        console.print(
            "\n[dim]Siguiente paso: Configura Origination URI en Twilio Console:\n"
            f"  sip:{os.environ.get('LIVEKIT_URL', '').replace('wss://', '')}[/dim]\n"
        )


if __name__ == "__main__":
    app()
