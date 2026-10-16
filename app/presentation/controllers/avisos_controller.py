"""
Avisos programados de citas (citas próximas + mantenimiento) para la app.
Los genera elashesbackend; este controller solo reenvía las peticiones con el
token de dispositivo que la app recibió al iniciar sesión (device_token).
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Response

from app.core.salon_internal import device_request, raise_for_salon_error

router = APIRouter(prefix="/api/v1/avisos", tags=["Avisos"])


def _require_authorization(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Falta el token de dispositivo",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization


@router.get("/programados")
def avisos_programados(authorization: Optional[str] = Header(default=None)):
    r = device_request("GET", "/avisos/programados", _require_authorization(authorization))
    raise_for_salon_error(r, "No se pudieron obtener los avisos")
    return r.json()


@router.delete("/dispositivo", status_code=204)
def revocar_dispositivo(authorization: Optional[str] = Header(default=None)):
    r = device_request("DELETE", "/dispositivos/actual", _require_authorization(authorization))
    # 401 = token ya revocado/inválido; 404 = avisos desactivados en el salón.
    # En ambos casos no queda nada que revocar: cerrar sesión no debe fallar.
    if r.status_code not in (401, 404):
        raise_for_salon_error(r, "No se pudo revocar el dispositivo")
    return Response(status_code=204)
