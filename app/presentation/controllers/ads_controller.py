from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_admin_user
from app.core.media import save_image
from app.domain.entities.ad import Ad

router = APIRouter(prefix="/ads", tags=["Publicidad"])

LINK_TYPES = {"none", "product", "collection", "category", "url", "booking", "pickup", "catalog"}


def _to_dict(a: Ad) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "subtitle": a.subtitle,
        "cta_label": a.cta_label,
        "image_url": a.image_url,
        "link_type": a.link_type,
        "link_value": a.link_value,
        "is_active": a.is_active,
        "sort_order": a.sort_order,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _validate_link_type(link_type: str):
    if link_type not in LINK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"link_type inválido. Usa: {', '.join(sorted(LINK_TYPES))}",
        )


# ── Público (Flutter) ──────────────────────────────────────────────────────────

@router.get("")
def list_ads(db: Session = Depends(get_db)):
    """Banners publicitarios activos para el carrusel de la app, ordenados."""
    ads = (
        db.query(Ad)
        .filter(Ad.is_active == True)
        .order_by(Ad.sort_order, Ad.id)
        .all()
    )
    return [_to_dict(a) for a in ads]


# ── Admin ──────────────────────────────────────────────────────────────────────

@router.get("/admin")
def admin_list_all(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    ads = db.query(Ad).order_by(Ad.sort_order, Ad.id).all()
    return [_to_dict(a) for a in ads]


@router.post("/admin", status_code=status.HTTP_201_CREATED)
async def create_ad(
    title: str = Form(...),
    subtitle: Optional[str] = Form(None),
    cta_label: str = Form("Ver más"),
    link_type: str = Form("none"),
    link_value: Optional[str] = Form(None),
    sort_order: int = Form(0),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    _validate_link_type(link_type)
    if not image or not image.filename:
        raise HTTPException(status_code=400, detail="La imagen del banner es obligatoria")

    image_url = save_image(image, "ads")
    ad = Ad(
        title=title,
        subtitle=subtitle,
        cta_label=cta_label or "Ver más",
        image_url=image_url,
        link_type=link_type,
        link_value=link_value,
        sort_order=sort_order,
    )
    db.add(ad)
    db.commit()
    db.refresh(ad)
    return _to_dict(ad)


@router.put("/admin/{ad_id}")
async def update_ad(
    ad_id: int,
    title: Optional[str] = Form(None),
    subtitle: Optional[str] = Form(None),
    cta_label: Optional[str] = Form(None),
    link_type: Optional[str] = Form(None),
    link_value: Optional[str] = Form(None),
    sort_order: Optional[int] = Form(None),
    is_active: Optional[bool] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Banner no encontrado")

    if link_type is not None:
        _validate_link_type(link_type)
        ad.link_type = link_type
    if title is not None:       ad.title = title
    if subtitle is not None:    ad.subtitle = subtitle
    if cta_label is not None:   ad.cta_label = cta_label
    if link_value is not None:  ad.link_value = link_value
    if sort_order is not None:  ad.sort_order = sort_order
    if is_active is not None:   ad.is_active = is_active
    if image and image.filename: ad.image_url = save_image(image, "ads")

    db.commit()
    db.refresh(ad)
    return _to_dict(ad)


@router.delete("/admin/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ad(ad_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    db.delete(ad)
    db.commit()
