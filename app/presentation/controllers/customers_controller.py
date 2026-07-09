import os
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
import httpx

from app.core.dependencies import get_db, get_admin_user
from app.domain.entities.order import Order
from app.domain.entities.customer import Customer

router = APIRouter(prefix="/customers", tags=["Clientes"])

# URL interna del backend del salón (elashesbackend). Configurable vía env.
_SALON_BACKEND_URL = os.getenv("SALON_BACKEND_URL", "http://127.0.0.1:8000")


@router.get("/lookup")
def lookup_customer(phone: str = Query(..., min_length=6), db: Session = Depends(get_db)):
    """
    Búsqueda pública de cliente por teléfono.
    1. Revisa pedidos anteriores en el marketplace.
    2. Si no hay, consulta el backend del salón (elashesbackend).
    Devuelve nombre y email para pre-rellenar el checkout.
    """
    phone = phone.strip()

    # 1. Buscar en pedidos del marketplace
    row = (
        db.query(Order.customer_name, Order.customer_email, func.count(Order.id).label("cnt"))
        .filter(Order.customer_phone == phone)
        .group_by(Order.customer_name, Order.customer_email)
        .order_by(func.count(Order.id).desc())
        .first()
    )
    if row:
        return {
            "found": True,
            "name": row.customer_name,
            "email": row.customer_email,
            "orders_count": row.cnt,
            "source": "marketplace",
        }

    # 2. Buscar en el backend del salón (elashesbackend)
    try:
        r = httpx.get(
            f"{_SALON_BACKEND_URL}/api/v1/clients/lookup",
            params={"phone": phone},
            timeout=3.0,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("found"):
                return {**data, "orders_count": 0, "source": "salon"}
    except Exception:
        pass  # elashesbackend no disponible; no bloqueamos el checkout

    return {"found": False}


@router.get("")
def list_customers(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Clientes del marketplace: cuentas registradas (mp_customers) enriquecidas
    con sus pedidos si los tienen, más pedidos de invitados sin cuenta.
    Incluye cuentas con 0 pedidos (ej. clientas del salón que ya iniciaron
    sesión con su CI pero todavía no compraron nada)."""
    order_rows = (
        db.query(
            Order.customer_name,
            Order.customer_phone,
            Order.customer_email,
            func.count(Order.id).label("order_count"),
            func.sum(Order.total).label("total_spent"),
            func.max(Order.created_at).label("last_order_at"),
        )
        .group_by(Order.customer_phone)
        .all()
    )

    all_customers = db.query(Customer).all()
    source_by_email = {c.email: c.source for c in all_customers}
    source_by_phone = {c.phone: c.source for c in all_customers if c.phone}

    def _source(phone: Optional[str], email: Optional[str]) -> str:
        if email and email in source_by_email:
            return source_by_email[email]
        if phone and phone in source_by_phone:
            return source_by_phone[phone]
        return "salon"  # pedido de invitado sin cuenta → vino del salón

    result = []
    seen_phones = set()
    for r in order_rows:
        result.append({
            "customer_name": r.customer_name,
            "customer_phone": r.customer_phone,
            "customer_email": r.customer_email,
            "order_count": r.order_count,
            "total_spent": float(r.total_spent or 0),
            "last_order_at": r.last_order_at.isoformat() if r.last_order_at else None,
            "source": _source(r.customer_phone, r.customer_email),
        })
        if r.customer_phone:
            seen_phones.add(r.customer_phone)

    # Cuentas registradas sin ningún pedido todavía (no aparecerían arriba)
    for c in all_customers:
        if c.phone and c.phone in seen_phones:
            continue
        result.append({
            "customer_name": c.name,
            "customer_phone": c.phone,
            "customer_email": c.email,
            "order_count": 0,
            "total_spent": 0.0,
            "last_order_at": None,
            "source": c.source,
        })

    result.sort(key=lambda x: x["total_spent"], reverse=True)
    return result
