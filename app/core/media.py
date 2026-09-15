import os
import shutil
import subprocess
import tempfile
import uuid

from fastapi import HTTPException, UploadFile

from app.config.settings import settings

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}
MAX_VIDEO_SIZE_BYTES = 80 * 1024 * 1024  # 80 MB


def _remux_faststart(filepath: str) -> None:
    """Remuxea el video a MP4 progresivo con el moov al inicio (faststart).

    Videos "descargados de YouTube" con ciertas herramientas vienen
    fragmentados (moof/mdat repetidos, moov chico al inicio sin duración
    real) — reproducen bien en un reproductor de escritorio, pero en
    ExoPlayer/AVPlayer (apps móviles) la duración queda en 0 y el seek no
    funciona. Sin recodificar (-c copy), solo reordena/desfragmenta.
    No-op si ffmpeg no está instalado (ej. dev local sin ffmpeg) — el video
    queda como se subió, igual que antes de este fix."""
    if not shutil.which("ffmpeg"):
        return
    fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(filepath)[1], dir=os.path.dirname(filepath))
    os.close(fd)
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", filepath, "-c", "copy", "-movflags", "+faststart", tmp_path],
            capture_output=True,
            timeout=120,
        )
        if result.returncode == 0 and os.path.getsize(tmp_path) > 0:
            os.replace(tmp_path, filepath)
        else:
            os.remove(tmp_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def save_image(file: UploadFile, subfolder: str = "products") -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Formato no permitido. Usa: {', '.join(ALLOWED_EXT)}")

    folder = os.path.join(settings.media_base_path, "marketplace", subfolder)
    os.makedirs(folder, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(folder, filename)

    with open(filepath, "wb") as f:
        f.write(file.file.read())

    return f"/media/marketplace/{subfolder}/{filename}"


def save_video(file: UploadFile, subfolder: str = "products") -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_VIDEO_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de video no permitido. Usa: {', '.join(ALLOWED_VIDEO_EXT)}",
        )

    folder = os.path.join(settings.media_base_path, "marketplace", subfolder, "videos")
    os.makedirs(folder, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(folder, filename)

    size = 0
    with open(filepath, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_VIDEO_SIZE_BYTES:
                f.close()
                os.remove(filepath)
                raise HTTPException(
                    status_code=400,
                    detail=f"El video supera el límite de {MAX_VIDEO_SIZE_BYTES // (1024*1024)} MB",
                )
            f.write(chunk)

    _remux_faststart(filepath)

    return f"/media/marketplace/{subfolder}/videos/{filename}"
