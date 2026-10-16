"""
Llamadas server-to-server a elashesbackend para los avisos de citas.
Los datos del salón (citas, clientes, seguimientos) viven solo allá: aquí no
se duplica ninguna tabla, todo va por HTTP.

- X-Internal-Key: secreto compartido (settings.internal_api_key). Solo se
  envía donde elashesbackend lo exige; nunca se devuelve a la app.
- Token de dispositivo: lo emite elashesbackend en POST /dispositivos y la app
  lo manda luego como "Authorization: Bearer <token>", que se reenvía tal cual.
"""
import os
from typing import Optional

import httpx
from fastapi import HTTPException

from app.config.settings import settings

_SALON_BACKEND_URL = os.getenv("SALON_BACKEND_URL", "http://127.0.0.1:8000")


def internal_headers() -> dict:
    return {"X-Internal-Key": settings.internal_api_key} if settings.internal_api_key else {}


def register_device(salon_client_id: int, installation_id: str, platform: str) -> Optional[str]:
    """Registra la instalación en elashesbackend y devuelve el token del
    dispositivo, o None si no se pudo. Nunca lanza: el login no debe fallar
    porque los avisos no estén disponibles."""
    if not settings.internal_api_key:
        return None
    try:
        r = httpx.post(
            f"{_SALON_BACKEND_URL}/dispositivos",
            json={
                "client_id": salon_client_id,
                "installation_id": installation_id,
                "platform": platform,
            },
            headers=internal_headers(),
            timeout=5.0,
        )
        if r.status_code == 201:
            return r.json().get("token")
    except Exception:
        pass
    return None


def device_request(method: str, path: str, authorization: str) -> httpx.Response:
    """Reenvía una petición autenticada con el token de dispositivo."""
    try:
        return httpx.request(
            method,
            f"{_SALON_BACKEND_URL}{path}",
            headers={"Authorization": authorization},
            timeout=8.0,
        )
    except Exception:
        raise HTTPException(status_code=503, detail="El salón no está disponible en este momento")


def raise_for_salon_error(r: httpx.Response, default_detail: str) -> None:
    if r.status_code >= 400:
        detail = default_detail
        try:
            detail = r.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)
