from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_admin_user
from app.core.media import save_image
from app.domain.entities.category import Category

router = APIRouter(prefix="/categories", tags=["Categorías"])


def _to_dict(c: Category) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "image_url": c.image_url,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ── Público (Flutter) ──────────────────────────────────────────

@router.get("")
def list_categories(db: Session = Depends(get_db)):
    """Categorías activas visibles en la app."""
    cats = db.query(Category).filter(Category.is_active == True).order_by(Category.name).all()
    return [_to_dict(c) for c in cats]


# ── Admin ──────────────────────────────────────────────────────

@router.get("/admin")
async def admin_list_all(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    cats = db.query(Category).order_by(Category.name).all()
    return [_to_dict(c) for c in cats]


@router.post("/admin", status_code=status.HTTP_201_CREATED)
async def create_category(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    if db.query(Category).filter(Category.name == name).first():
        raise HTTPException(status_code=400, detail="Ya existe una categoría con ese nombre")

    image_url = save_image(image, "categories") if image and image.filename else None
    cat = Category(name=name, description=description, image_url=image_url)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return _to_dict(cat)


@router.put("/admin/{cat_id}")
async def update_category(
    cat_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    if name is not None:
        cat.name = name
    if description is not None:
        cat.description = description
    if is_active is not None:
        cat.is_active = is_active
    if image and image.filename:
        cat.image_url = save_image(image, "categories")

    db.commit()
    db.refresh(cat)
    return _to_dict(cat)


@router.delete("/admin/{cat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(cat_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    db.delete(cat)
    db.commit()
