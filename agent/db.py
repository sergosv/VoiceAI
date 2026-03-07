"""Supabase client singleton para el agente de voz.

Evita crear una conexión nueva por cada operación,
reutilizando un único cliente en todo el proceso.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from supabase import Client, create_client

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Retorna un cliente Supabase singleton (service_role).

    Raises:
        RuntimeError: Si faltan las variables de entorno requeridas.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Faltan variables de entorno SUPABASE_URL y/o SUPABASE_SERVICE_KEY. "
            "El agente no puede funcionar sin conexión a la base de datos."
        )
    return create_client(url, key)
