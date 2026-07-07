import os
import uuid

from fastapi import HTTPException, UploadFile

from app.config.settings import settings

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}
MAX_VIDEO_SIZE_BYTES = 80 * 1024 * 1024  # 80 MB


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

    return f"/media/marketplace/{subfolder}/videos/{filename}"
