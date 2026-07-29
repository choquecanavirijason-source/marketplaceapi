from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_db
from app.domain.entities.customer import Customer
from app.domain.entities.favorite import Favorite
from app.domain.entities.product import Product
from app.presentation.controllers.auth_controller import get_current_customer
from app.presentation.controllers.products_controller import _to_dict as _product_to_dict

router = APIRouter(prefix="/favorites", tags=["Favoritos"])


@router.get("")
def list_favorites(
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Productos favoritos de la cuenta autenticada (solo activos)."""
    products = (
        db.query(Product)
        .join(Favorite, Favorite.product_id == Product.id)
        .options(joinedload(Product.category))
        .filter(Favorite.customer_id == current_customer.id, Product.is_active == True)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    return [_product_to_dict(p) for p in products]


@router.post("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(
    product_id: int,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Idempotente: si ya estaba marcado como favorito, no hace nada."""
    exists = (
        db.query(Favorite)
        .filter(Favorite.customer_id == current_customer.id, Favorite.product_id == product_id)
        .first()
    )
    if not exists:
        db.add(Favorite(customer_id=current_customer.id, product_id=product_id))
        db.commit()


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    product_id: int,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Idempotente: si no estaba marcado, no hace nada."""
    db.query(Favorite).filter(
        Favorite.customer_id == current_customer.id, Favorite.product_id == product_id
    ).delete()
    db.commit()
