from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_db, get_admin_user
from app.core.media import save_image
from app.domain.entities.product import Product
from app.domain.entities.category import Category
from app.domain.entities.order import Order
from app.domain.entities.order_item import OrderItem

router = APIRouter(prefix="/products", tags=["Productos"])


def _to_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "brand": p.brand,
        "description": p.description,
        "price": p.price,
        "original_price": p.original_price,
        "image_url": p.image_url,
        "video_url": p.video_url,
        "category_id": p.category_id,
        "category_name": p.category.name if p.category else None,
        "stock": p.stock,
        "low_stock_threshold": p.low_stock_threshold,
        "is_low_stock": p.stock <= p.low_stock_threshold,
        "rating": p.rating,
        "review_count": p.review_count,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ── Público (Flutter) ──────────────────────────────────────────

@router.get("")
def list_products(
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Product)
        .options(joinedload(Product.category))
        .filter(Product.is_active == True)
    )
    if category_id:
        q = q.filter(Product.category_id == category_id)
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(Product.name.ilike(term) | Product.brand.ilike(term))
    return [_to_dict(p) for p in q.order_by(Product.created_at.desc()).all()]


@router.get("/featured")
def get_featured_products(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Productos más comprados. Si no hay ventas, retorna los mejor calificados."""
    sales_subq = (
        db.query(
            OrderItem.product_id,
            func.sum(OrderItem.quantity).label("total_sold"),
        )
        .filter(OrderItem.product_id.isnot(None))
        .group_by(OrderItem.product_id)
        .subquery()
    )

    rows = (
        db.query(Product, func.coalesce(sales_subq.c.total_sold, 0).label("sold"))
        .options(joinedload(Product.category))
        .outerjoin(sales_subq, Product.id == sales_subq.c.product_id)
        .filter(Product.is_active == True)
        .order_by(
            func.coalesce(sales_subq.c.total_sold, 0).desc(),
            Product.rating.desc(),
            Product.created_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return [_to_dict(p) for p, _ in rows]


@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(Product).options(joinedload(Product.category)).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return _to_dict(p)


# ── Admin ──────────────────────────────────────────────────────

@router.get("/admin/all")
async def admin_list_products(
    include_inactive: bool = Query(False),
    category_id: Optional[int] = Query(None),
    low_stock_only: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    q = db.query(Product).options(joinedload(Product.category))
    if not include_inactive:
        q = q.filter(Product.is_active == True)
    if category_id:
        q = q.filter(Product.category_id == category_id)
    if low_stock_only:
        q = q.filter(Product.stock <= Product.low_stock_threshold)
    return [_to_dict(p) for p in q.order_by(Product.created_at.desc()).all()]


@router.get("/admin/stats")
async def admin_stats(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    """Stats consolidadas: productos, órdenes y revenue para el dashboard."""
    total_products = db.query(Product).count()
    active_products = db.query(Product).filter(Product.is_active == True).count()
    low_stock_count = db.query(Product).filter(
        Product.is_active == True,
        Product.stock <= Product.low_stock_threshold,
    ).count()
    out_of_stock = db.query(Product).filter(Product.is_active == True, Product.stock == 0).count()

    total_orders = db.query(Order).count()
    pending_orders = db.query(Order).filter(Order.status == "pending").count()
    confirmed_orders = db.query(Order).filter(Order.status == "confirmed").count()
    delivered_orders = db.query(Order).filter(Order.status == "delivered").count()

    revenue_row = db.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.status.in_(["confirmed", "delivered"])
    ).scalar()

    return {
        "products": {
            "total": total_products,
            "active": active_products,
            "inactive": total_products - active_products,
            "low_stock": low_stock_count,
            "out_of_stock": out_of_stock,
        },
        "orders": {
            "total": total_orders,
            "pending": pending_orders,
            "confirmed": confirmed_orders,
            "delivered": delivered_orders,
        },
        "revenue": float(revenue_row),
    }


@router.get("/admin/low-stock")
async def admin_low_stock(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    """Productos activos con stock <= low_stock_threshold."""
    products = (
        db.query(Product)
        .options(joinedload(Product.category))
        .filter(Product.is_active == True, Product.stock <= Product.low_stock_threshold)
        .order_by(Product.stock.asc())
        .all()
    )
    return [_to_dict(p) for p in products]


@router.post("/admin", status_code=status.HTTP_201_CREATED)
async def create_product(
    name: str = Form(...),
    price: float = Form(...),
    brand: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    original_price: Optional[float] = Form(None),
    category_id: Optional[int] = Form(None),
    stock: int = Form(0),
    low_stock_threshold: int = Form(5),
    video_url: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    if category_id and not db.query(Category).filter(Category.id == category_id).first():
        raise HTTPException(status_code=400, detail="Categoría no existe")

    image_url = save_image(image, "products") if image and image.filename else None
    product = Product(
        name=name, brand=brand, description=description,
        price=price, original_price=original_price,
        image_url=image_url, video_url=video_url or None,
        category_id=category_id,
        stock=stock, low_stock_threshold=low_stock_threshold,
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return _to_dict(db.query(Product).options(joinedload(Product.category)).filter(Product.id == product.id).first())


class ImportProductBody(BaseModel):
    name: str
    price: float
    brand: Optional[str] = None
    description: Optional[str] = None
    original_price: Optional[float] = None
    category_id: Optional[int] = None
    stock: int = 0
    low_stock_threshold: int = 5
    video_url: Optional[str] = None
    image_url: Optional[str] = None


@router.post("/admin/import", status_code=status.HTTP_201_CREATED)
async def import_product(
    body: ImportProductBody,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    """Importa un producto desde el inventario de elashesbackend."""
    if body.category_id and not db.query(Category).filter(Category.id == body.category_id).first():
        body.category_id = None

    product = Product(
        name=body.name, brand=body.brand, description=body.description,
        price=body.price, original_price=body.original_price,
        image_url=body.image_url, video_url=body.video_url,
        category_id=body.category_id,
        stock=body.stock, low_stock_threshold=body.low_stock_threshold,
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return _to_dict(db.query(Product).options(joinedload(Product.category)).filter(Product.id == product.id).first())


@router.put("/admin/{product_id}")
async def update_product(
    product_id: int,
    name: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    brand: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    original_price: Optional[float] = Form(None),
    category_id: Optional[int] = Form(None),
    stock: Optional[int] = Form(None),
    low_stock_threshold: Optional[int] = Form(None),
    video_url: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if name is not None:                p.name = name
    if price is not None:               p.price = price
    if brand is not None:               p.brand = brand
    if description is not None:         p.description = description
    if original_price is not None:      p.original_price = original_price
    if category_id is not None:         p.category_id = None if category_id == 0 else category_id
    if stock is not None:               p.stock = stock
    if low_stock_threshold is not None: p.low_stock_threshold = low_stock_threshold
    if video_url is not None:           p.video_url = video_url or None
    if is_active is not None:           p.is_active = is_active
    if image and image.filename:        p.image_url = save_image(image, "products")

    db.commit()
    db.refresh(p)
    return _to_dict(db.query(Product).options(joinedload(Product.category)).filter(Product.id == p.id).first())


class StockAdjust(BaseModel):
    stock: int


@router.patch("/admin/{product_id}/stock")
async def adjust_stock(
    product_id: int,
    body: StockAdjust,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    p = db.query(Product).options(joinedload(Product.category)).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    p.stock = max(0, body.stock)
    db.commit()
    db.refresh(p)
    return _to_dict(db.query(Product).options(joinedload(Product.category)).filter(Product.id == p.id).first())


@router.delete("/admin/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    db.delete(p)
    db.commit()
