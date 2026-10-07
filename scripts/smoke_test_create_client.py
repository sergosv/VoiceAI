"""Smoke test end-to-end del flujo de creación de cliente.

Crea un cliente de prueba con infra real (Supabase + Gemini),
verifica todos los artefactos y limpia al final.

Uso:
    python scripts/smoke_test_create_client.py [--email TU_EMAIL]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from api.services.client_service import (
    build_greeting,
    build_system_prompt,
    create_client_in_db,
    create_gemini_store,
    create_owner_user,
    delete_gemini_store,
    delete_owner_user,
    generate_temp_password,
    load_voice_id,
)
from api.deps import get_supabase


async def run_smoke_test(test_email: str | None) -> int:
    sb = get_supabase()
    timestamp = int(time.time())
    slug = f"smoke-test-{timestamp}"
    name = f"Smoke Test {timestamp}"
    agent_name = "TestBot"

    artifacts: dict = {
        "store_id": None,
        "client_id": None,
        "owner_email": None,
    }

    print(f"Iniciando smoke test con slug={slug}")

    try:
        # 1. Pre-check
        existing = sb.table("clients").select("id").eq("slug", slug).limit(1).execute()
        assert not existing.data, "slug ya existe (muy improbable)"
        print("  [ok] slug libre")

        # 2. Crear Gemini store
        store_id, store_name = await asyncio.to_thread(
            create_gemini_store, slug, os.environ["GOOGLE_API_KEY"]
        )
        artifacts["store_id"] = store_id
        print(f"  [ok] Gemini store creado: {store_id}")

        # 3. Insertar cliente
        voice_id = load_voice_id("es_female_warm")
        greeting = build_greeting(name, agent_name)
        system_prompt = build_system_prompt("generic", agent_name, name, "es")
        row = create_client_in_db(
            sb,
            name=name, slug=slug, business_type="generic",
            agent_name=agent_name, language="es", voice_id=voice_id,
            greeting=greeting, system_prompt=system_prompt,
            store_id=store_id, store_name=store_name,
            owner_email=test_email,
        )
        artifacts["client_id"] = row["id"]
        print(f"  [ok] Cliente insertado: {row['id']}")

        # 4. Agent default
        sb.table("agents").insert({
            "client_id": row["id"],
            "name": agent_name,
            "slug": "default",
            "system_prompt": system_prompt,
            "greeting": greeting,
            "voice_config": {"provider": "cartesia", "voice_id": voice_id},
            "llm_config": {"provider": "google"},
            "stt_config": {"provider": "deepgram"},
        }).execute()
        print("  [ok] Agent default creado")

        # 5. User Auth (solo si hay email)
        if test_email:
            temp_pwd = generate_temp_password()
            await asyncio.to_thread(
                create_owner_user, sb,
                email=test_email, password=temp_pwd, client_id=row["id"],
            )
            artifacts["owner_email"] = test_email
            print(f"  [ok] User Auth creado para {test_email} (pwd: {temp_pwd})")

        # 6. Verificaciones
        credit = sb.table("credit_transactions").select("*").eq(
            "client_id", row["id"]
        ).execute()
        assert credit.data, "No se creó transacción de créditos bienvenida"
        print(f"  [ok] Créditos bienvenida: {credit.data[0]['credits']} ({credit.data[0]['type']})")

        agent = sb.table("agents").select("id").eq(
            "client_id", row["id"]
        ).execute()
        assert agent.data, "Agent default no existe"
        print(f"  [ok] Agent default verificado: {agent.data[0]['id']}")

        if test_email:
            user = sb.table("users").select("*").eq(
                "client_id", row["id"]
            ).execute()
            assert user.data, "User no existe en tabla users"
            assert user.data[0]["role"] == "client"
            print(f"  [ok] User verificado en tabla users: {user.data[0]['email']}")

        print("\nRESULTADO: OK — todo creado correctamente")
        return 0

    except Exception as e:
        print(f"\nRESULTADO: FAIL — {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        print("\nLimpiando artefactos de prueba...")
        if artifacts["owner_email"]:
            await asyncio.to_thread(delete_owner_user, artifacts["owner_email"])
            print(f"  - auth user {artifacts['owner_email']} borrado")
        if artifacts["client_id"]:
            sb.table("users").delete().eq("client_id", artifacts["client_id"]).execute()
            sb.table("agents").delete().eq("client_id", artifacts["client_id"]).execute()
            sb.table("credit_transactions").delete().eq("client_id", artifacts["client_id"]).execute()
            sb.table("credit_balances").delete().eq("client_id", artifacts["client_id"]).execute()
            sb.table("clients").delete().eq("id", artifacts["client_id"]).execute()
            print(f"  - client {artifacts['client_id']} borrado (cascade)")
        if artifacts["store_id"]:
            await asyncio.to_thread(
                delete_gemini_store, artifacts["store_id"], os.environ["GOOGLE_API_KEY"]
            )
            print(f"  - Gemini store {artifacts['store_id']} borrado")
        print("Limpieza completada")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=None, help="Email para probar creación de user Auth")
    args = parser.parse_args()
    return asyncio.run(run_smoke_test(args.email))


if __name__ == "__main__":
    sys.exit(main())
