"""Retry helper con exponential backoff para tools del agente.

Uso:
    result = await retry_async(my_async_func, args=(x, y), max_retries=2)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# Errores que vale la pena reintentar
_RETRYABLE_EXCEPTIONS = (
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
)


async def retry_async(
    func: Callable[..., Coroutine],
    args: tuple = (),
    kwargs: dict | None = None,
    max_retries: int = 2,
    base_delay: float = 1.0,
    max_delay: float = 5.0,
    retryable_exceptions: tuple = _RETRYABLE_EXCEPTIONS,
) -> Any:
    """Ejecuta una función async con retry y exponential backoff.

    Args:
        func: Función async a ejecutar.
        args: Argumentos posicionales.
        kwargs: Argumentos keyword.
        max_retries: Máximo de reintentos (0 = sin retry).
        base_delay: Delay base en segundos (se duplica cada retry).
        max_delay: Delay máximo en segundos.
        retryable_exceptions: Tupla de excepciones que ameritan retry.

    Returns:
        El resultado de func() si tiene éxito.

    Raises:
        La última excepción si se agotan los reintentos.
    """
    kwargs = kwargs or {}
    last_exception: Exception | None = None

    for attempt in range(1 + max_retries):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(
                    "Retry %d/%d para %s tras %s — esperando %.1fs",
                    attempt + 1, max_retries, func.__name__,
                    type(e).__name__, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Agotados %d reintentos para %s: %s",
                    max_retries, func.__name__, e,
                )

    raise last_exception  # type: ignore[misc]
