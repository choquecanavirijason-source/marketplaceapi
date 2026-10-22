"""Procesamiento en segundo plano del video de los reels.

Con H.265 (ver REEL_RENDITIONS en media.py) un reel tarda minutos en
procesarse en el VPS, más que el timeout del proxy: si se hiciera dentro de
la petición, el admin vería un error aunque el reel se terminara creando.
Ahora la petición solo guarda el archivo subido y responde al instante; el
procesamiento corre después (BackgroundTasks) y actualiza el reel:

  - reel nuevo:        video_url = "" y processing_status = "processing"
                       (oculto en la app) -> al terminar, su video y "ready".
  - reel existente:    sigue mostrando su video anterior mientras procesa ->
                       al terminar se cambia y el anterior se borra.
  - falla:             processing_status = "failed" + processing_error; el
                       reel conserva lo que tenía (nada, si era nuevo).

processing_job identifica el procesamiento vigente: si el admin sube otro
video al mismo reel antes de que termine, o borra el reel, el resultado del
procesamiento viejo se descarta y sus archivos se borran.
"""
import threading
import uuid

from app.core.media import delete_media, discard_staged_upload, process_reel_video
from app.core.media_usage import discard_media_now
from app.domain.entities.reel import Reel
from app.infrastructure.database.session import SessionLocal

# De a un video a la vez: ffmpeg/x265 ya usa todos los núcleos, dos en
# paralelo solo se estorbarían (y le quitarían CPU a la API).
_encode_lock = threading.Lock()


def new_job_id() -> str:
    return uuid.uuid4().hex


def process_reel_in_background(reel_id: int, job_id: str, staged_path: str) -> None:
    """Corre en el threadpool después de responder (BackgroundTasks).
    Nunca lanza: cualquier fallo queda registrado en el reel."""
    db = SessionLocal()
    try:
        with _encode_lock:
            # Pudo cambiar mientras esperaba su turno (otro video, o borrado).
            if not _is_current(db, reel_id, job_id):
                discard_staged_upload(staged_path)
                return
            try:
                url = process_reel_video(staged_path)
            except Exception as exc:
                print(f"[reel_processing] reel {reel_id}: {exc!r}")
                _mark_failed(db, reel_id, job_id, str(exc) or type(exc).__name__)
                return

        reel = db.query(Reel).filter(Reel.id == reel_id).first()
        if reel is None or reel.processing_job != job_id:
            # Se borró el reel o llegó otro video mientras procesaba.
            delete_media(url)
            return
        old_url = reel.video_url
        reel.video_url = url
        reel.processing_status = "ready"
        reel.processing_error = None
        reel.processing_job = None
        db.commit()
        if old_url:
            discard_media_now(db, old_url)
    except Exception as exc:
        print(f"[reel_processing] reel {reel_id}: error inesperado {exc!r}")
        discard_staged_upload(staged_path)
    finally:
        db.close()


def _is_current(db, reel_id: int, job_id: str) -> bool:
    db.expire_all()
    reel = db.query(Reel).filter(Reel.id == reel_id).first()
    return reel is not None and reel.processing_job == job_id


def _mark_failed(db, reel_id: int, job_id: str, error: str) -> None:
    db.expire_all()
    reel = db.query(Reel).filter(Reel.id == reel_id).first()
    if reel is None or reel.processing_job != job_id:
        return
    reel.processing_status = "failed"
    reel.processing_error = error[:300]
    reel.processing_job = None
    db.commit()
