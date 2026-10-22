"""Completa los reels en MP4 subidos antes de que existieran:
  - la vista previa del admin (REEL_PREVIEW_NAME, H.264 480p), si el reel
    está en H.265;
  - la versión liviana para datos móviles (REEL_SD_NAME), si no la tiene.
Los nuevos ya traen las dos. Se puede correr las veces que haga falta: lo
que ya existe se saltea.

Uso (en el servidor):
    docker exec marketplace-api python -m app.scripts.make_reel_previews
"""
import os
import subprocess
import tempfile
import urllib.request

import importlib
import pkgutil

import app.domain.entities as _entities
from app.core import storage
from app.core.media import (
    REEL_MP4_NAME,
    REEL_PREVIEW_NAME,
    REEL_SD_NAME,
    _compress_single_video,
    _make_admin_preview,
    _url_to_key,
    get_video_download_url,
    reel_rendition,
)
from app.domain.entities.reel import Reel
from app.infrastructure.database.session import SessionLocal


# Carga todos los modelos (las relaciones entre ellos se resuelven por
# nombre). NO se importa main: eso vuelve a correr las migraciones, y una de
# ellas marca como fallido cualquier reel que se esté procesando en ese
# momento en el servidor.
for _mod in pkgutil.iter_modules(_entities.__path__):
    importlib.import_module(f"{_entities.__name__}.{_mod.name}")


def _codec(url: str) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", url],
        capture_output=True, text=True, timeout=60,
    ).stdout.strip()


def _ensure_preview(reel: Reel, folder_key: str, work: str) -> None:
    preview_key = folder_key + REEL_PREVIEW_NAME
    if storage.list_keys(preview_key):
        return
    if _codec(reel.video_url) != "hevc":
        return
    src = os.path.join(work, REEL_MP4_NAME)
    if not os.path.exists(src):
        urllib.request.urlretrieve(reel.video_url, src)
    dst = os.path.join(work, REEL_PREVIEW_NAME)
    if _make_admin_preview(src, dst):
        storage.put_file(dst, preview_key)
        print(f"reel {reel.id}: vista previa creada")
    else:
        print(f"reel {reel.id}: no se pudo crear la vista previa")


def _ensure_sd(db, reel: Reel, folder_key: str, work: str) -> None:
    if reel.video_sd_url:
        return
    sd_key = folder_key + REEL_SD_NAME
    if not storage.list_keys(sd_key):
        # Mejor desde el original (una sola recompresión); si no está, desde
        # el MP4 ya procesado.
        source_url = get_video_download_url(reel.video_url) or reel.video_url
        src = os.path.join(work, "source" + os.path.splitext(source_url)[1])
        urllib.request.urlretrieve(source_url, src)
        dst = os.path.join(work, REEL_SD_NAME)
        if not _compress_single_video(src, dst, reel_rendition(sd=True)):
            print(f"reel {reel.id}: no se pudo crear la versión liviana")
            return
        storage.put_file(dst, sd_key)
    reel.video_sd_url = storage.public_url(sd_key)
    db.commit()
    print(f"reel {reel.id}: versión liviana lista")


def run() -> None:
    db = SessionLocal()
    try:
        reels = db.query(Reel).filter(Reel.video_url.like(f"%/{REEL_MP4_NAME}")).all()
        for reel in reels:
            video_key = _url_to_key(reel.video_url)
            if video_key is None:
                continue
            folder_key = video_key[: -len(REEL_MP4_NAME)]
            with tempfile.TemporaryDirectory() as work:
                _ensure_preview(reel, folder_key, work)
                _ensure_sd(db, reel, folder_key, work)
    finally:
        db.close()


if __name__ == "__main__":
    run()
