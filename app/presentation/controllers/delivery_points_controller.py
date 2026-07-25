import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_admin_user
from app.domain.entities.delivery_point import DeliveryPoint

router = APIRouter(prefix="/delivery-points", tags=["Puntos de entrega"])

# Mismo patrón ya usado en auth_controller.py/booking_controller.py/
# customers_controller.py de este backend para hablar con el salón.
_SALON_BACKEND_URL = os.getenv("SALON_BACKEND_URL", "http://127.0.0.1:8000")


# ── Schemas ──────────────────────────────────────────────────────────────────

class DeliveryPointIn(BaseModel):
    country_code: str
    country_name: str
    city: Optional[str] = None
    name: str
    address: str
    reference: Optional[str] = None
    schedule: Optional[str] = None
    phone: Optional[str] = None
    sort_order: int = 0


class DeliveryPointUpdate(BaseModel):
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    reference: Optional[str] = None
    schedule: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_dict(p: DeliveryPoint) -> dict:
    return {
        "id": p.id,
        "country_code": p.country_code,
        "country_name": p.country_name,
        "city": p.city,
        "name": p.name,
        "address": p.address,
        "reference": p.reference,
        "schedule": p.schedule,
        "phone": p.phone,
        "is_active": p.is_active,
        "sort_order": p.sort_order,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _fetch_branches_as_points(country_code: Optional[str] = None) -> list[dict]:
    """Sucursales del salón (con país conocido) traducidas al mismo formato
    que un punto de entrega manual, para que aparezcan juntas en la app.
    Si el backend del salón no responde, se devuelve una lista vacía — nunca
    debe romper la pantalla de Puntos de Entrega."""
    try:
        params = {"country_code": country_code} if country_code else {}
        # Reutiliza el endpoint público que ya existe para "Punto de recojo"
        # (booking-public/branches), en vez de duplicar uno nuevo.
        resp = httpx.get(f"{_SALON_BACKEND_URL}/booking-public/branches", params=params, timeout=3.0)
        resp.raise_for_status()
        branches = resp.json()
    except Exception:
        return []

    return [
        {
            "id": -b["id"],  # negativo: nunca choca con un id real de mp_delivery_points
            "country_code": b.get("country_code"),
            "country_name": b.get("country_name") or b.get("country_code"),
            "city": b.get("city"),
            "name": b.get("name"),
            "address": b.get("address"),
            "reference": None,
            "schedule": None,
            "phone": None,
            "is_active": True,
            "sort_order": 0,
            "created_at": None,
        }
        for b in branches
        if b.get("country_code")
    ]


# ── Público (Flutter) ─────────────────────────────────────────────────────────

@router.get("/countries")
def list_countries(db: Session = Depends(get_db)):
    """Países que tienen al menos un punto de entrega activo, o al menos una
    sucursal del salón con país conocido, para que el cliente elija solo
    entre los que realmente tienen cobertura."""
    rows = (
        db.query(DeliveryPoint.country_code, DeliveryPoint.country_name)
        .filter(DeliveryPoint.is_active == True)
        .distinct()
        .order_by(DeliveryPoint.country_name)
        .all()
    )
    countries = {r[0]: r[1] for r in rows}
    for b in _fetch_branches_as_points():
        countries.setdefault(b["country_code"], b["country_name"])
    return [
        {"country_code": code, "country_name": name}
        for code, name in sorted(countries.items(), key=lambda kv: kv[1])
    ]


@router.get("")
def list_delivery_points(
    country_code: str = Query(..., min_length=2, max_length=2),
    db: Session = Depends(get_db),
):
    """Puntos de entrega activos de un país (creados a mano + sucursales del
    salón con ese país), ya ordenados por nombre."""
    points = (
        db.query(DeliveryPoint)
        .filter(
            DeliveryPoint.is_active == True,
            DeliveryPoint.country_code == country_code.upper(),
        )
        .all()
    )
    combined = [_to_dict(p) for p in points] + _fetch_branches_as_points(country_code.upper())
    combined.sort(key=lambda p: (p["sort_order"], p["name"] or ""))
    return combined


# ── Admin ──────────────────────────────────────────────────────────────────────

@router.get("/admin")
def admin_list_all(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    points = db.query(DeliveryPoint).order_by(
        DeliveryPoint.country_name, DeliveryPoint.sort_order, DeliveryPoint.id
    ).all()
    return [_to_dict(p) for p in points]


@router.post("/admin", status_code=status.HTTP_201_CREATED)
def create_delivery_point(
    payload: DeliveryPointIn,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    point = DeliveryPoint(
        country_code=payload.country_code.upper(),
        country_name=payload.country_name,
        city=payload.city,
        name=payload.name,
        address=payload.address,
        reference=payload.reference,
        schedule=payload.schedule,
        phone=payload.phone,
        sort_order=payload.sort_order,
    )
    db.add(point)
    db.commit()
    db.refresh(point)
    return _to_dict(point)


@router.put("/admin/{point_id}")
def update_delivery_point(
    point_id: int,
    payload: DeliveryPointUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    point = db.query(DeliveryPoint).filter(DeliveryPoint.id == point_id).first()
    if not point:
        raise HTTPException(status_code=404, detail="Punto de entrega no encontrado")

    data = payload.model_dump(exclude_unset=True)
    if "country_code" in data and data["country_code"] is not None:
        data["country_code"] = data["country_code"].upper()
    for field, value in data.items():
        setattr(point, field, value)

    db.commit()
    db.refresh(point)
    return _to_dict(point)


@router.delete("/admin/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_delivery_point(point_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    point = db.query(DeliveryPoint).filter(DeliveryPoint.id == point_id).first()
    if not point:
        raise HTTPException(status_code=404, detail="Punto de entrega no encontrado")
    db.delete(point)
    db.commit()
