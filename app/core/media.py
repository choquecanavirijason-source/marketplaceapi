import os
import uuid

from fastapi import HTTPException, UploadFile

from app.config.settings import settings

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


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
