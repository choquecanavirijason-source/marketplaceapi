"""Genera la vista previa del admin (REEL_PREVIEW_NAME, H.264 480p) para los
reels en H.265 subidos antes de que existiera. Los nuevos ya la traen.

Uso (en el servidor):
    docker exec marketplace-api python -m app.scripts.make_reel_previews
"""
import os
import subprocess
import tempfile
import urllib.request

import main  # noqa: F401  carga todos los modelos, como el servidor
from app.core import storage
from app.core.media import (
    REEL_MP4_NAME,
    REEL_PREVIEW_NAME,
    _make_admin_preview,
    _url_to_key,
)
from app.domain.entities.reel import Reel
from app.infrastructure.database.session import SessionLocal


def _codec(url: str) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", url],
        capture_output=True, text=True, timeout=60,
    ).stdout.strip()


def run() -> None:
    db = SessionLocal()
    try:
        reels = db.query(Reel).filter(Reel.video_url.like(f"%/{REEL_MP4_NAME}")).all()
        for reel in reels:
            video_key = _url_to_key(reel.video_url)
            if video_key is None:
                continue
            preview_key = video_key[: -len(REEL_MP4_NAME)] + REEL_PREVIEW_NAME
            if storage.list_keys(preview_key):
                print(f"reel {reel.id}: ya tiene vista previa")
                continue
            codec = _codec(reel.video_url)
            if codec != "hevc":
                print(f"reel {reel.id}: {codec or '?'}, no hace falta")
                continue
            with tempfile.TemporaryDirectory() as work:
                src = os.path.join(work, REEL_MP4_NAME)
                dst = os.path.join(work, REEL_PREVIEW_NAME)
                urllib.request.urlretrieve(reel.video_url, src)
                if _make_admin_preview(src, dst):
                    storage.put_file(dst, preview_key)
                    print(f"reel {reel.id}: vista previa creada")
                else:
                    print(f"reel {reel.id}: no se pudo crear la vista previa")
    finally:
        db.close()


if __name__ == "__main__":
    run()
