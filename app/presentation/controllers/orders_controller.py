import random
import string
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_db, get_admin_user
from app.domain.entities.order import Order
from app.domain.entities.order_item import OrderItem
from app.domain.entities.product import Product

router = APIRouter(prefix="/orders", tags=["Pedidos"])

ORDER_STATUSES = {"pending", "confirmed", "processing", "shipped", "delivered", "cancelled"}

STATUS_ES = {
    "pending":    "Pendiente",
    "confirmed":  "Confirmado",
    "processing": "En proceso",
    "shipped":    "Enviado",
    "delivered":  "Entregado",
    "cancelled":  "Cancelado",
}


# ── Schemas ────────────────────────────────────────────────────

class OrderItemIn(BaseModel):
    product_id: Optional[int] = None    # None o 0 para productos del inventario
    product_name: Optional[str] = None  # requerido cuando product_id es None/0
    unit_price: Optional[float] = None  # requerido cuando product_id es None/0
    quantity: int = 1


class OrderIn(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    notes: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_district: Optional[str] = None
    delivery_references: Optional[str] = None
    items: List[OrderItemIn]


class StatusUpdate(BaseModel):
    status: str


# ── Helpers ────────────────────────────────────────────────────

def _generate_code() -> str:
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def _item_dict(i: OrderItem) -> dict:
    return {
        "id": i.id,
        "product_id": i.product_id,
        "product_name": i.product_name,
        "product_image": i.product_image,
        "quantity": i.quantity,
        "unit_price": i.unit_price,
        "subtotal": i.subtotal,
    }


def _order_dict(o: Order) -> dict:
    return {
        "id": o.id,
        "order_code": o.order_code,
        "customer_name": o.customer_name,
        "customer_phone": o.customer_phone,
        "customer_email": o.customer_email,
        "total": o.total,
        "status": o.status,
        "status_label": STATUS_ES.get(o.status, o.status),
        "notes": o.notes,
        "delivery_address": o.delivery_address,
        "delivery_district": o.delivery_district,
        "delivery_references": o.delivery_references,
        "items": [_item_dict(i) for i in o.items],
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


# ── Público (Flutter) — crear pedido ──────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(body: OrderIn, db: Session = Depends(get_db)):
    if not body.items:
        raise HTTPException(status_code=400, detail="El pedido debe tener al menos un producto")

    total = 0.0
    order_items = []

    for item_in in body.items:
        is_inventory = not item_in.product_id  # None o 0 = producto del inventario

        if is_inventory:
            # Producto del inventario del salón: usar nombre/precio directamente
            if not item_in.product_name or item_in.unit_price is None:
                raise HTTPException(
                    status_code=400,
                    detail="product_name y unit_price son requeridos para productos de inventario",
                )
            subtotal = item_in.unit_price * item_in.quantity
            total += subtotal
            order_items.append(OrderItem(
                product_id=None,
                product_name=item_in.product_name,
                product_image=None,
                quantity=item_in.quantity,
                unit_price=item_in.unit_price,
                subtotal=subtotal,
            ))
        else:
            product = db.query(Product).filter(
                Product.id == item_in.product_id, Product.is_active == True
            ).first()
            if not product:
                raise HTTPException(status_code=400, detail=f"Producto {item_in.product_id} no disponible")
            if product.stock < item_in.quantity:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para '{product.name}'")

            subtotal = product.price * item_in.quantity
            total += subtotal
            order_items.append(OrderItem(
                product_id=product.id,
                product_name=product.name,
                product_image=product.image_url,
                quantity=item_in.quantity,
                unit_price=product.price,
                subtotal=subtotal,
            ))
            product.stock -= item_in.quantity

    code = _generate_code()
    while db.query(Order).filter(Order.order_code == code).first():
        code = _generate_code()

    order = Order(
        order_code=code,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        customer_email=body.customer_email,
        total=round(total, 2),
        notes=body.notes,
        delivery_address=body.delivery_address,
        delivery_district=body.delivery_district,
        delivery_references=body.delivery_references,
        status="pending",
    )
    db.add(order)
    db.flush()

    for oi in order_items:
        oi.order_id = order.id
        db.add(oi)

    db.commit()
    db.refresh(order)
    return _order_dict(db.query(Order).options(joinedload(Order.items)).filter(Order.id == order.id).first())


# ── Público (Flutter) — pedidos por teléfono ─────────────────

@router.get("/my")
def get_my_orders(
    phone: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(Order.customer_phone == phone)
        .order_by(Order.created_at.desc())
        .all()
    )
    return [_order_dict(o) for o in orders]


# ── Admin ─────────────────────────────────────────────────────

@router.get("/admin")
async def admin_list_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    q = db.query(Order).options(joinedload(Order.items))
    if status_filter and status_filter in ORDER_STATUSES:
        q = q.filter(Order.status == status_filter)
    if search:
        term = f"%{search}%"
        q = q.filter(
            Order.customer_name.ilike(term) |
            Order.customer_phone.ilike(term) |
            Order.order_code.ilike(term)
        )
    total_count = q.count()
    orders = q.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "items": [_order_dict(o) for o in orders],
    }


@router.get("/admin/{order_id}")
async def admin_get_order(order_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    o = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return _order_dict(o)


@router.patch("/admin/{order_id}/status")
async def update_order_status(
    order_id: int,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    if body.status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Opciones: {', '.join(ORDER_STATUSES)}")

    o = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Al cancelar un pedido activo, devolver el stock reservado
    if body.status == "cancelled" and o.status != "cancelled":
        for item in o.items:
            if item.product_id:
                product = db.query(Product).filter(Product.id == item.product_id).first()
                if product:
                    product.stock += item.quantity
    # Si se reactiva un pedido cancelado, volver a descontar
    elif o.status == "cancelled" and body.status != "cancelled":
        for item in o.items:
            if item.product_id:
                product = db.query(Product).filter(Product.id == item.product_id).first()
                if product:
                    if product.stock < item.quantity:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Stock insuficiente para reactivar: '{item.product_name}'",
                        )
                    product.stock -= item.quantity

    o.status = body.status
    o.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(o)
    return _order_dict(db.query(Order).options(joinedload(Order.items)).filter(Order.id == o.id).first())


@router.delete("/admin/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(order_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    o = db.query(Order).filter(Order.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    db.delete(o)
    db.commit()
