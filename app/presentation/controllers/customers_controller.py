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
def lookup_customer(
    phone: str = Query(..., min_length=6),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    """
    Búsqueda de cliente por teléfono — SOLO ADMIN (ej. atención al cliente).
    1. Revisa pedidos anteriores en el marketplace.
    2. Si no hay, consulta el backend del salón (elashesbackend).
    Ya no la usa el checkout de la app (ahora exige cuenta); antes era
    pública y cualquiera podía ver nombre/email de otro cliente con solo
    su teléfono.
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
    all_customers = db.query(Customer).all()
    customers_by_id = {c.id: c for c in all_customers}
    source_by_email = {c.email: c.source for c in all_customers}
    source_by_phone = {c.phone: c.source for c in all_customers if c.phone}

    def _source(phone: Optional[str], email: Optional[str]) -> str:
        if email and email in source_by_email:
            return source_by_email[email]
        if phone and phone in source_by_phone:
            return source_by_phone[phone]
        return "salon"  # pedido de invitado sin cuenta → vino del salón

    result = []
    seen_customer_ids = set()
    seen_phones = set()
    seen_emails = set()

    # Pedidos ligados a una cuenta (customer_id): agrupar por la cuenta real,
    # no por el teléfono que haya puesto en ese checkout puntual — si no, un
    # mismo cliente que cambia de teléfono entre pedidos aparecía duplicado.
    acct_rows = (
        db.query(
            Order.customer_id,
            func.count(Order.id).label("order_count"),
            func.sum(Order.total).label("total_spent"),
            func.max(Order.created_at).label("last_order_at"),
        )
        .filter(Order.customer_id.isnot(None))
        .group_by(Order.customer_id)
        .all()
    )
    for r in acct_rows:
        c = customers_by_id.get(r.customer_id)
        if not c:
            continue  # cuenta eliminada; ignorar pedidos huérfanos
        result.append({
            "customer_name": c.name,
            "customer_phone": c.phone,
            "customer_email": c.email,
            "order_count": r.order_count,
            "total_spent": float(r.total_spent or 0),
            "last_order_at": r.last_order_at.isoformat() if r.last_order_at else None,
            "source": c.source,
        })
        seen_customer_ids.add(c.id)
        if c.phone:
            seen_phones.add(c.phone)
        seen_emails.add(c.email.lower())

    # Pedidos de invitados sin cuenta (customer_id nulo, incluye pedidos
    # anteriores a que existiera esta columna): sigue agrupando por teléfono.
    guest_rows = (
        db.query(
            Order.customer_name,
            Order.customer_phone,
            Order.customer_email,
            func.count(Order.id).label("order_count"),
            func.sum(Order.total).label("total_spent"),
            func.max(Order.created_at).label("last_order_at"),
        )
        .filter(Order.customer_id.is_(None))
        .group_by(Order.customer_phone)
        .all()
    )
    for r in guest_rows:
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
        if r.customer_email:
            seen_emails.add(r.customer_email.lower())

    # Cuentas registradas sin ningún pedido todavía (no aparecerían arriba).
    # Se compara también por email (no solo teléfono) porque el registro por
    # app no pide teléfono — sin este chequeo, esas cuentas aparecían
    # duplicadas: una vez por su pedido (agrupado por teléfono) y otra vez
    # acá como si no tuvieran ningún pedido.
    for c in all_customers:
        if c.id in seen_customer_ids:
            continue
        if c.phone and c.phone in seen_phones:
            continue
        if c.email and c.email.lower() in seen_emails:
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
