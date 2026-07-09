from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_db, get_admin_user
from app.core.media import save_image, save_video
from app.domain.entities.reel import Reel
from app.domain.entities.product import Product

router = APIRouter(prefix="/reels", tags=["Reels"])


def _to_dict(r: Reel) -> dict:
    product = None
    p = getattr(r, "product", None)
    if p:
        product = {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "image_url": p.image_url,
        }
    return {
        "id": r.id,
        "video_url": r.video_url,
        "thumbnail_url": r.thumbnail_url,
        "caption": r.caption,
        "product_id": r.product_id,
        "product": product,
        "is_active": r.is_active,
        "sort_order": r.sort_order,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _load(db: Session, *, active_only: bool = False):
    q = db.query(Reel).options(joinedload(Reel.product))
    if active_only:
        q = q.filter(Reel.is_active == True)
    return q.order_by(Reel.sort_order, Reel.id).all()


# ── Público (Flutter) ──────────────────────────────────────────────────────────

@router.get("")
def list_reels(db: Session = Depends(get_db)):
    """Reels activos para la pantalla de reels de la app, ya ordenados."""
    return [_to_dict(r) for r in _load(db, active_only=True)]


# ── Admin ──────────────────────────────────────────────────────────────────────

@router.get("/admin")
def admin_list_all(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    return [_to_dict(r) for r in _load(db)]


@router.post("/admin", status_code=status.HTTP_201_CREATED)
async def create_reel(
    caption: Optional[str] = Form(None),
    video_url: Optional[str] = Form(None),
    product_id: Optional[int] = Form(None),
    sort_order: int = Form(0),
    video: Optional[UploadFile] = File(None),
    thumbnail: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    final_video_url = save_video(video, "reels") if video and video.filename else (video_url or None)
    if not final_video_url:
        raise HTTPException(status_code=400, detail="Sube un video o pega un link directo (mp4, etc.)")

    if product_id and not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(status_code=400, detail="Producto no existe")

    thumbnail_url = save_image(thumbnail, "reels") if thumbnail and thumbnail.filename else None

    reel = Reel(
        video_url=final_video_url,
        thumbnail_url=thumbnail_url,
        caption=caption,
        product_id=product_id or None,
        sort_order=sort_order,
    )
    db.add(reel)
    db.commit()
    db.refresh(reel)
    return _to_dict(
        db.query(Reel).options(joinedload(Reel.product)).filter(Reel.id == reel.id).first()
    )


@router.put("/admin/{reel_id}")
async def update_reel(
    reel_id: int,
    caption: Optional[str] = Form(None),
    video_url: Optional[str] = Form(None),
    product_id: Optional[int] = Form(None),
    sort_order: Optional[int] = Form(None),
    is_active: Optional[bool] = Form(None),
    video: Optional[UploadFile] = File(None),
    thumbnail: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    reel = db.query(Reel).filter(Reel.id == reel_id).first()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel no encontrado")

    if video and video.filename:      reel.video_url = save_video(video, "reels")
    elif video_url is not None:       reel.video_url = video_url or reel.video_url
    if caption is not None:           reel.caption = caption
    if product_id is not None:        reel.product_id = None if product_id == 0 else product_id
    if sort_order is not None:        reel.sort_order = sort_order
    if is_active is not None:         reel.is_active = is_active
    if thumbnail and thumbnail.filename: reel.thumbnail_url = save_image(thumbnail, "reels")

    db.commit()
    db.refresh(reel)
    return _to_dict(
        db.query(Reel).options(joinedload(Reel.product)).filter(Reel.id == reel.id).first()
    )


@router.delete("/admin/{reel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reel(reel_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    reel = db.query(Reel).filter(Reel.id == reel_id).first()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel no encontrado")
    db.delete(reel)
    db.commit()
