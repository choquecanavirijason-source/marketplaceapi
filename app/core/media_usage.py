"""Qué archivos de /media siguen referenciados en la base de datos.

Un mismo archivo puede estar en más de un registro: un producto importado
reutiliza la imagen de otro, y cada item de pedido guarda la imagen que tenía
el producto al comprarlo. Por eso nunca se borra un archivo solo porque su
registro se eliminó o se editó: primero se confirma que nadie más lo usa.
"""
from typing import Set

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.media import delete_media, is_managed_media
from app.domain.entities.ad import Ad
from app.domain.entities.category import Category
from app.domain.entities.collection import Collection
from app.domain.entities.order_item import OrderItem
from app.domain.entities.product import Product
from app.domain.entities.reel import Reel

MEDIA_COLUMNS = [
    Product.image_url,
    Product.video_url,
    Reel.video_url,
    Reel.thumbnail_url,
    Ad.image_url,
    Category.image_url,
    Collection.image_url,
    OrderItem.product_image,
]


def _is_referenced(db: Session, url: str) -> bool:
    return any(
        db.query(column).filter(column == url).limit(1).first() is not None
        for column in MEDIA_COLUMNS
    )


def referenced_media(db: Session) -> Set[str]:
    urls: Set[str] = set()
    for column in MEDIA_COLUMNS:
        urls.update(value for (value,) in db.query(column).filter(column.isnot(None)).distinct())
    return {u for u in urls if is_managed_media(u)}


def discard_media(db: Session, background_tasks: BackgroundTasks, *urls) -> None:
    """Borra del storage las URLs que ya no usa ningún registro. Se llama
    después del commit con los valores viejos: si una URL no cambió, sigue
    referenciada y no se toca. El borrado corre después de responder."""
    unused = [
        url for url in dict.fromkeys(urls)
        if is_managed_media(url) and not _is_referenced(db, url)
    ]
    if unused:
        background_tasks.add_task(delete_media, *unused)
