from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_db, get_admin_user
from app.core.media import save_image
from app.domain.entities.collection import Collection, CollectionProduct
from app.domain.entities.product import Product

router = APIRouter(prefix="/collections", tags=["Colecciones"])


# ── helpers ────────────────────────────────────────────────────────────────────

def _preview(cp_list) -> list:
    result = []
    for cp in cp_list[:4]:
        p = getattr(cp, "product", None)
        if not p:
            continue
        result.append({
            "id": p.id,
            "name": p.name,
            "image_url": p.image_url,
            "price": p.price,
            "category_name": p.category.name if p.category else None,
        })
    return result


def _to_dict(c: Collection) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "image_url": c.image_url,
        "is_active": c.is_active,
        "product_count": len(c.products),
        "preview_products": _preview(c.products),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _load(db: Session, col_id: int) -> Collection:
    """Carga una colección con todos los productos y categorías en una query."""
    col = (
        db.query(Collection)
        .options(
            joinedload(Collection.products)
            .joinedload(CollectionProduct.product)
            .joinedload(Product.category)
        )
        .filter(Collection.id == col_id)
        .first()
    )
    if not col:
        raise HTTPException(status_code=404, detail="Colección no encontrada")
    return col


def _load_all(db: Session, *, active_only: bool = False):
    q = db.query(Collection).options(
        joinedload(Collection.products)
        .joinedload(CollectionProduct.product)
        .joinedload(Product.category)
    )
    if active_only:
        q = q.filter(Collection.is_active == True)
    return q.order_by(Collection.name).all()


# ── Público (Flutter) ──────────────────────────────────────────────────────────

@router.get("")
def list_collections(db: Session = Depends(get_db)):
    """Colecciones activas para la app Flutter."""
    cols = _load_all(db, active_only=True)
    return [_to_dict(c) for c in cols]


@router.get("/{col_id}/products")
def get_collection_products(col_id: int, db: Session = Depends(get_db)):
    col = _load(db, col_id)
    if not col.is_active:
        raise HTTPException(status_code=404, detail="Colección no encontrada")
    product_ids = [cp.product_id for cp in col.products]
    products = (
        db.query(Product)
        .options(joinedload(Product.category))
        .filter(Product.id.in_(product_ids), Product.is_active == True)
        .all()
    )
    from app.presentation.controllers.products_controller import _to_dict as _prod_dict
    return [_prod_dict(p) for p in products]


# ── Admin ──────────────────────────────────────────────────────────────────────

@router.get("/admin")
def admin_list_all(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    cols = _load_all(db)
    return [_to_dict(c) for c in cols]


@router.get("/admin/{col_id}/products")
def admin_get_collection_products(
    col_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)
):
    """Admin: productos de una colección aunque esté inactiva."""
    col = _load(db, col_id)
    product_ids = [cp.product_id for cp in col.products]
    products = (
        db.query(Product)
        .options(joinedload(Product.category))
        .filter(Product.id.in_(product_ids))
        .all()
    )
    from app.presentation.controllers.products_controller import _to_dict as _prod_dict
    return [_prod_dict(p) for p in products]


@router.post("/admin", status_code=status.HTTP_201_CREATED)
async def create_collection(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    if db.query(Collection).filter(Collection.name == name).first():
        raise HTTPException(status_code=400, detail="Ya existe una colección con ese nombre")

    image_url = save_image(image, "collections") if image and image.filename else None
    col = Collection(name=name, description=description, image_url=image_url)
    db.add(col)
    db.commit()
    return _to_dict(_load(db, col.id))


@router.put("/admin/{col_id}")
async def update_collection(
    col_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    col = db.query(Collection).filter(Collection.id == col_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Colección no encontrada")

    if name is not None:        col.name = name
    if description is not None: col.description = description
    if is_active is not None:   col.is_active = is_active
    if image and image.filename: col.image_url = save_image(image, "collections")

    db.commit()
    return _to_dict(_load(db, col_id))


@router.delete("/admin/{col_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(col_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    col = db.query(Collection).filter(Collection.id == col_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Colección no encontrada")
    db.delete(col)
    db.commit()


@router.post("/admin/{col_id}/products/{product_id}", status_code=status.HTTP_201_CREATED)
def add_product_to_collection(
    col_id: int, product_id: int,
    db: Session = Depends(get_db), _=Depends(get_admin_user),
):
    col = db.query(Collection).filter(Collection.id == col_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Colección no encontrada")
    if not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if not db.query(CollectionProduct).filter_by(collection_id=col_id, product_id=product_id).first():
        db.add(CollectionProduct(collection_id=col_id, product_id=product_id))
        db.commit()
    return _to_dict(_load(db, col_id))


@router.delete("/admin/{col_id}/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_product_from_collection(
    col_id: int, product_id: int,
    db: Session = Depends(get_db), _=Depends(get_admin_user),
):
    cp = db.query(CollectionProduct).filter_by(collection_id=col_id, product_id=product_id).first()
    if cp:
        db.delete(cp)
        db.commit()
