"""
Llamadas server-to-server a elashesbackend para los avisos de citas.
Los datos del salón (citas, clientes, seguimientos) viven solo allá: aquí no
se duplica ninguna tabla, todo va por HTTP.

- X-Internal-Key: secreto compartido (settings.internal_api_key). Solo se
  envía donde elashesbackend lo exige; nunca se devuelve a la app.
- Token de dispositivo: lo emite elashesbackend en POST /dispositivos y la app
  lo manda luego como "Authorization: Bearer <token>", que se reenvía tal cual.
- Vínculo cuenta ↔ ficha del salón: mp_customers.salon_client_id, resuelto
  con POST /clients/link-marketplace (por email, sin verificar todavía).
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


def link_marketplace(email: Optional[str], phone: Optional[str]) -> tuple[str, Optional[int]]:
    """Busca en elashesbackend la ficha que corresponde a una cuenta del
    marketplace (POST /clients/link-marketplace). Devuelve (status, id):
    "found" con id; "not_found"/"ambiguous" sin id; "unavailable" si no hay
    clave o el salón no respondió. Nunca lanza."""
    if not settings.internal_api_key:
        return "unavailable", None
    try:
        r = httpx.post(
            f"{_SALON_BACKEND_URL}/clients/link-marketplace",
            json={"email": email or None, "phone": phone or None},
            headers=internal_headers(),
            timeout=3.0,
        )
        if r.status_code == 200:
            data = r.json()
            link_status = data.get("status")
            if link_status == "found" and data.get("id"):
                return "found", data["id"]
            if link_status in ("not_found", "ambiguous"):
                return link_status, None
    except Exception:
        pass
    return "unavailable", None


def ensure_salon_link(db, customer) -> str:
    """Si la cuenta aún no tiene salon_client_id, lo busca en el salón y lo
    guarda solo si hay una única coincidencia. Devuelve el status del vínculo
    ("found" si ya estaba vinculada)."""
    if customer.salon_client_id:
        return "found"
    link_status, client_id = link_marketplace(customer.email, customer.phone)
    if client_id:
        customer.salon_client_id = client_id
        db.commit()
    return link_status


def device_request(
    method: str, path: str, authorization: str, json: Optional[dict] = None
) -> httpx.Response:
    """Reenvía una petición autenticada con el token de dispositivo (y su
    cuerpo JSON, si lo tiene). No guarda ni registra nada de lo reenviado."""
    try:
        return httpx.request(
            method,
            f"{_SALON_BACKEND_URL}{path}",
            headers={"Authorization": authorization},
            json=json,
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
