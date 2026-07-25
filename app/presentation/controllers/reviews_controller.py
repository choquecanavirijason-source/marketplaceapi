from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.entities.customer import Customer
from app.domain.entities.order import Order
from app.domain.entities.order_item import OrderItem
from app.domain.entities.product import Product
from app.domain.entities.review import Review
from app.presentation.controllers.auth_controller import get_current_customer

router = APIRouter(prefix="/products/{product_id}/reviews", tags=["Reseñas"])

# Estados de pedido que cuentan como "compra válida" para poder reseñar.
_ELIGIBLE_STATUSES = ("confirmed", "processing", "shipped", "delivered")


def _to_dict(r: Review) -> dict:
    return {
        "id": r.id,
        "product_id": r.product_id,
        "customer_name": r.customer_name,
        "rating": r.rating,
        "comment": r.comment,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "is_mine": False,
    }


def _has_qualifying_purchase(db: Session, customer: Customer, product_id: int) -> bool:
    # Se verifica por customer_id (dueño real del pedido, vía cuenta
    # autenticada) y no por teléfono — el teléfono de perfil se puede
    # cambiar libremente, así que compararlo permitía "heredar" pedidos
    # ajenos con solo copiar su número.
    return (
        db.query(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(
            Order.customer_id == customer.id,
            Order.status.in_(_ELIGIBLE_STATUSES),
            OrderItem.product_id == product_id,
        )
        .first()
        is not None
    )


def _recompute_product_rating(db: Session, product_id: int) -> None:
    agg = (
        db.query(func.avg(Review.rating), func.count(Review.id))
        .filter(Review.product_id == product_id)
        .first()
    )
    avg_rating, count = agg[0] or 0.0, agg[1] or 0
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.rating = round(float(avg_rating), 2)
        product.review_count = count
        db.commit()


@router.get("")
def list_reviews(product_id: int, db: Session = Depends(get_db)):
    """Reseñas públicas de un producto, más recientes primero."""
    reviews = (
        db.query(Review)
        .filter(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
        .all()
    )
    return [_to_dict(r) for r in reviews]


@router.get("/eligibility")
def check_review_eligibility(
    product_id: int,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    """Indica si el cliente logueado puede dejar una reseña de este producto
    (compró el producto y todavía no lo reseñó) y, si ya lo hizo, cuál fue."""
    existing = (
        db.query(Review)
        .filter(Review.product_id == product_id, Review.customer_id == customer.id)
        .first()
    )
    if existing:
        return {"can_review": False, "already_reviewed": True, "my_review": _to_dict(existing)}

    can_review = _has_qualifying_purchase(db, customer, product_id)
    if not can_review:
        return {
            "can_review": False,
            "already_reviewed": False,
            "reason": "no_purchase",
        }
    return {"can_review": True, "already_reviewed": False}


class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_review(
    product_id: int,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    if not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    existing = (
        db.query(Review)
        .filter(Review.product_id == product_id, Review.customer_id == customer.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ya dejaste una reseña para este producto")

    if not _has_qualifying_purchase(db, customer, product_id):
        raise HTTPException(
            status_code=403,
            detail="Solo puedes reseñar productos que hayas comprado y recibido",
        )

    review = Review(
        product_id=product_id,
        customer_id=customer.id,
        customer_name=customer.name,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    _recompute_product_rating(db, product_id)

    result = _to_dict(review)
    result["is_mine"] = True
    return result


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    product_id: int,
    review_id: int,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    review = (
        db.query(Review)
        .filter(Review.id == review_id, Review.product_id == product_id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    if review.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="No puedes eliminar la reseña de otro cliente")

    db.delete(review)
    db.commit()
    _recompute_product_rating(db, product_id)
