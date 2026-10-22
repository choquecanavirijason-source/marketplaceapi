from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_db, get_admin_user
from app.core.media import get_video_download_url, reel_preview_url, save_image, stage_video_upload
from app.core.media_usage import discard_media
from app.core.reel_processing import new_job_id, process_reel_in_background
from app.domain.entities.customer import Customer
from app.domain.entities.reel import Reel
from app.domain.entities.reel_like import ReelLike
from app.domain.entities.product import Product
from app.presentation.controllers.auth_controller import (
    get_current_customer,
    get_current_customer_optional,
)

router = APIRouter(prefix="/reels", tags=["Reels"])


def _to_dict(
    r: Reel,
    *,
    like_count: int = 0,
    is_liked: bool = False,
) -> dict:
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
        "video_download_url": get_video_download_url(r.video_url),
        # Para el admin (navegador de PC): ver REEL_PREVIEW_NAME en media.py.
        "video_preview_url": reel_preview_url(r.video_url),
        "thumbnail_url": r.thumbnail_url,
        "caption": r.caption,
        "product_id": r.product_id,
        "product": product,
        "is_active": r.is_active,
        # Video procesándose en segundo plano (ver reel_processing.py).
        "processing_status": r.processing_status or "ready",
        "processing_error": r.processing_error,
        "sort_order": r.sort_order,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "like_count": like_count,
        "is_liked": is_liked,
    }


def _like_counts(db: Session, reel_ids: list[int]) -> dict[int, int]:
    if not reel_ids:
        return {}
    rows = (
        db.query(ReelLike.reel_id, func.count(ReelLike.id))
        .filter(ReelLike.reel_id.in_(reel_ids))
        .group_by(ReelLike.reel_id)
        .all()
    )
    return {reel_id: count for reel_id, count in rows}


def _liked_reel_ids(db: Session, customer_id: Optional[int], reel_ids: list[int]) -> set[int]:
    if not customer_id or not reel_ids:
        return set()
    rows = (
        db.query(ReelLike.reel_id)
        .filter(ReelLike.customer_id == customer_id, ReelLike.reel_id.in_(reel_ids))
        .all()
    )
    return {reel_id for (reel_id,) in rows}


def _visible_in_app(q):
    """Lo que ve la app: activos y con video. Un reel nuevo cuyo video
    todavía se procesa (o falló) tiene video_url vacío y queda oculto; uno
    existente al que se le cambia el video sigue con el anterior."""
    return q.filter(Reel.is_active == True, Reel.video_url != "")


def _load(
    db: Session,
    *,
    active_only: bool = False,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    ids: Optional[list[int]] = None,
):
    q = db.query(Reel).options(joinedload(Reel.product))
    if active_only:
        q = _visible_in_app(q)
    if ids is not None:
        q = q.filter(Reel.id.in_(ids))
    q = q.order_by(Reel.sort_order, Reel.id)
    if offset is not None:
        q = q.offset(offset)
    if limit is not None:
        q = q.limit(limit)
    return q.all()


# ── Público (Flutter) ──────────────────────────────────────────────────────────

@router.get("")
def list_reels(
    limit: Optional[int] = None,
    offset: int = 0,
    ids: Optional[str] = None,
    db: Session = Depends(get_db),
    current_customer: Optional[Customer] = Depends(get_current_customer_optional),
):
    """Reels activos para la pantalla de reels de la app, ya ordenados.

    Soporta paginación (limit/offset) para no cargar todos los videos de golpe.
    `ids` ("3,7,9") trae solo esos reels: la app lo usa para sumar los reels
    nuevos sin recargar la lista entera.
    Incluye like_count siempre, e is_liked si hay sesión iniciada.
    """
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()] if ids else None
    reels = _load(db, active_only=True, limit=limit, offset=offset, ids=id_list)
    ids = [r.id for r in reels]
    counts = _like_counts(db, ids)
    liked = _liked_reel_ids(db, current_customer.id if current_customer else None, ids)
    return [
        _to_dict(r, like_count=counts.get(r.id, 0), is_liked=r.id in liked)
        for r in reels
    ]


@router.get("/ids")
def list_reel_ids(db: Session = Depends(get_db)):
    """Ids de los reels activos, en orden. Consulta liviana para que la app
    detecte reels nuevos o eliminados sin bajar la lista completa."""
    rows = (
        _visible_in_app(db.query(Reel.id))
        .order_by(Reel.sort_order, Reel.id)
        .all()
    )
    return [reel_id for (reel_id,) in rows]


@router.get("/liked")
def list_my_liked_reels(
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Reels a los que el cliente logueado les dio like — "Mis reels"."""
    reels = (
        db.query(Reel)
        .join(ReelLike, ReelLike.reel_id == Reel.id)
        .options(joinedload(Reel.product))
        .filter(ReelLike.customer_id == current_customer.id)
        .filter(Reel.is_active == True, Reel.video_url != "")
        .order_by(ReelLike.created_at.desc())
        .all()
    )
    ids = [r.id for r in reels]
    counts = _like_counts(db, ids)
    return [_to_dict(r, like_count=counts.get(r.id, 0), is_liked=True) for r in reels]


@router.post("/{reel_id}/like", status_code=status.HTTP_204_NO_CONTENT)
def like_reel(
    reel_id: int,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    if not db.query(Reel).filter(Reel.id == reel_id).first():
        raise HTTPException(status_code=404, detail="Reel no encontrado")
    exists = (
        db.query(ReelLike)
        .filter(ReelLike.customer_id == current_customer.id, ReelLike.reel_id == reel_id)
        .first()
    )
    if not exists:
        db.add(ReelLike(customer_id=current_customer.id, reel_id=reel_id))
        db.commit()


@router.delete("/{reel_id}/like", status_code=status.HTTP_204_NO_CONTENT)
def unlike_reel(
    reel_id: int,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    db.query(ReelLike).filter(
        ReelLike.customer_id == current_customer.id, ReelLike.reel_id == reel_id
    ).delete()
    db.commit()


# ── Admin ──────────────────────────────────────────────────────────────────────

@router.get("/admin")
def admin_list_all(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    reels = _load(db)
    counts = _like_counts(db, [r.id for r in reels])
    return [_to_dict(r, like_count=counts.get(r.id, 0)) for r in reels]


@router.get("/admin/{reel_id}/likes")
def admin_list_reel_likes(reel_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Quién le dio like a este reel — para el panel de administración."""
    if not db.query(Reel).filter(Reel.id == reel_id).first():
        raise HTTPException(status_code=404, detail="Reel no encontrado")
    rows = (
        db.query(Customer.id, Customer.name, Customer.email, ReelLike.created_at)
        .join(ReelLike, ReelLike.customer_id == Customer.id)
        .filter(ReelLike.reel_id == reel_id)
        .order_by(ReelLike.created_at.desc())
        .all()
    )
    return [
        {
            "customer_id": customer_id,
            "name": name,
            "email": email,
            "liked_at": liked_at.isoformat() if liked_at else None,
        }
        for customer_id, name, email, liked_at in rows
    ]


@router.post("/admin", status_code=status.HTTP_201_CREATED)
async def create_reel(
    caption: Optional[str] = Form(None),
    video_url: Optional[str] = Form(None),
    product_id: Optional[int] = Form(None),
    sort_order: int = Form(0),
    video: Optional[UploadFile] = File(None),
    thumbnail: Optional[UploadFile] = File(None),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    has_upload = bool(video and video.filename)
    if not has_upload and not video_url:
        raise HTTPException(status_code=400, detail="Sube un video o pega un link directo (mp4, etc.)")

    if product_id and not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(status_code=400, detail="Producto no existe")

    # Solo se guarda el archivo: el procesamiento (minutos con H.265) corre
    # después de responder. Mientras tanto el reel queda oculto en la app.
    staged = await run_in_threadpool(stage_video_upload, video) if has_upload else None
    thumbnail_url = save_image(thumbnail, "reels") if thumbnail and thumbnail.filename else None

    job = new_job_id() if staged else None
    reel = Reel(
        video_url="" if staged else video_url,
        thumbnail_url=thumbnail_url,
        caption=caption,
        product_id=product_id or None,
        sort_order=sort_order,
        processing_status="processing" if staged else "ready",
        processing_job=job,
    )
    db.add(reel)
    db.commit()
    db.refresh(reel)
    if staged:
        background_tasks.add_task(process_reel_in_background, reel.id, job, staged)
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
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    reel = db.query(Reel).filter(Reel.id == reel_id).first()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel no encontrado")
    old_media = (reel.video_url, reel.thumbnail_url)

    staged = None
    if video and video.filename:
        # El reel sigue mostrando su video actual hasta que el nuevo termine
        # de procesarse; recién ahí se cambia y se borra el anterior.
        staged = await run_in_threadpool(stage_video_upload, video)
        reel.processing_status = "processing"
        reel.processing_error = None
        reel.processing_job = new_job_id()
    elif video_url:
        # Link pegado a mano: reemplaza al instante y cancela cualquier
        # procesamiento pendiente (su resultado se descarta).
        reel.video_url = video_url
        reel.processing_status = "ready"
        reel.processing_error = None
        reel.processing_job = None
    if caption is not None:           reel.caption = caption
    if product_id is not None:        reel.product_id = None if product_id == 0 else product_id
    if sort_order is not None:        reel.sort_order = sort_order
    if is_active is not None:         reel.is_active = is_active
    if thumbnail and thumbnail.filename: reel.thumbnail_url = save_image(thumbnail, "reels")

    db.commit()
    discard_media(db, background_tasks, *old_media)
    if staged:
        background_tasks.add_task(process_reel_in_background, reel.id, reel.processing_job, staged)
    db.refresh(reel)
    return _to_dict(
        db.query(Reel).options(joinedload(Reel.product)).filter(Reel.id == reel.id).first()
    )


@router.delete("/admin/{reel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reel(
    reel_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    reel = db.query(Reel).filter(Reel.id == reel_id).first()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel no encontrado")
    old_media = (reel.video_url, reel.thumbnail_url)
    db.delete(reel)
    db.commit()
    discard_media(db, background_tasks, *old_media)
