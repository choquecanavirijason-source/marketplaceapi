"""
Proxy de reserva de citas del salón para clientes del marketplace.
Requiere sesión iniciada (JWT de mp_customers). Reenvía las peticiones
a elashesbackend (/booking-public/*) inyectando la identidad del cliente.
"""
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.config.settings import settings
from app.core.dependencies import get_db
from app.domain.entities.customer import Customer

_SALON_BACKEND_URL = os.getenv("SALON_BACKEND_URL", "http://127.0.0.1:8000")

router = APIRouter(prefix="/api/v1/booking", tags=["Reservas"])

_bearer = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _current_customer(
    db: Session = Depends(get_db), token: str = Depends(_bearer)
) -> Customer:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        customer_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Sesión inválida. Inicia sesión de nuevo.")
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer or not customer.is_active:
        raise HTTPException(status_code=401, detail="Cuenta no disponible")
    return customer


def _salon_get(path: str, params: dict | None = None):
    try:
        r = httpx.get(f"{_SALON_BACKEND_URL}{path}", params=params, timeout=8.0)
    except Exception:
        raise HTTPException(status_code=503, detail="El salón no está disponible en este momento")
    if r.status_code >= 400:
        detail = "Error del salón"
        try:
            detail = r.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    return r.json()


class BookingRequest(BaseModel):
    service_id: Optional[int] = None          # compat: un solo servicio
    service_ids: Optional[list[int]] = None   # varios servicios
    branch_id: int
    start_iso: str
    notes: Optional[str] = None


@router.get("/services")
def booking_services(_: Customer = Depends(_current_customer)):
    return _salon_get("/booking-public/services")


@router.get("/branches")
def booking_branches(_: Customer = Depends(_current_customer)):
    return _salon_get("/booking-public/branches")


@router.get("/availability")
def booking_availability(
    day: str = Query(...),
    service_ids: str = Query(..., description="IDs separados por coma"),
    branch_id: int = Query(...),
    _: Customer = Depends(_current_customer),
):
    return _salon_get(
        "/booking-public/availability",
        {"day": day, "service_ids": service_ids, "branch_id": branch_id},
    )


@router.post("/appointments", status_code=201)
def create_booking(
    body: BookingRequest,
    customer: Customer = Depends(_current_customer),
):
    try:
        r = httpx.post(
            f"{_SALON_BACKEND_URL}/booking-public/appointments",
            json={
                "email": customer.email,
                "name": customer.name,
                "phone": customer.phone,
                "service_id": body.service_id,
                "service_ids": body.service_ids,
                "branch_id": body.branch_id,
                "start_iso": body.start_iso,
                "notes": body.notes,
            },
            timeout=8.0,
        )
    except Exception:
        raise HTTPException(status_code=503, detail="El salón no está disponible en este momento")
    if r.status_code >= 400:
        detail = "No se pudo crear la reserva"
        try:
            detail = r.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    return r.json()


@router.get("/my-appointments")
def my_bookings(customer: Customer = Depends(_current_customer)):
    return _salon_get("/booking-public/my-appointments", {"email": customer.email})
