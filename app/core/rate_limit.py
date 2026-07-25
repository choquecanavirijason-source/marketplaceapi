"""Limitador de intentos en memoria del proceso — sin dependencias nuevas
(Redis, slowapi, etc.), pensado para frenar fuerza bruta scripted contra
login/registro. No es un rate-limiter distribuido (si se corre con varios
workers, cada uno lleva su propio conteo), pero es infinitamente mejor que
no tener ningún límite, que era el estado anterior."""
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_attempts: dict[str, list[float]] = defaultdict(list)


def rate_limit(
    request: Request,
    key_prefix: str,
    max_attempts: int = 5,
    window_seconds: int = 60,
) -> None:
    """Levanta 429 si la IP ya hizo `max_attempts` intentos en los últimos
    `window_seconds` segundos para esta acción (`key_prefix`)."""
    ip = request.client.host if request.client else "unknown"
    key = f"{key_prefix}:{ip}"
    now = time.time()
    attempts = _attempts[key]
    attempts[:] = [t for t in attempts if now - t < window_seconds]
    if len(attempts) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Espera un minuto e intenta de nuevo.",
        )
    attempts.append(now)
