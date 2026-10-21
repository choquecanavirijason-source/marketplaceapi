"""Almacenamiento de objetos en MinIO (fotos de perfil)."""
import io
import json
import time
from functools import lru_cache

from minio import Minio

from app.config.settings import settings


@lru_cache(maxsize=1)
def _client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _ensure_bucket(client: Minio, bucket: str) -> None:
    if client.bucket_exists(bucket):
        return
    client.make_bucket(bucket)
    # Lectura pública de objetos: la app carga el avatar con una URL directa.
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{bucket}/*"],
        }],
    }
    client.set_bucket_policy(bucket, json.dumps(policy))


def upload_avatar(data: bytes, ext: str, content_type: str, user_id: int) -> str:
    """Sube el avatar y devuelve su URL pública. Nombre: user_<id>_<timestamp>.<ext>."""
    client = _client()
    bucket = settings.minio_avatars_bucket
    _ensure_bucket(client, bucket)
    object_name = f"user_{user_id}_{int(time.time() * 1000)}.{ext}"
    client.put_object(
        bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return f"{settings.minio_public_url.rstrip('/')}/{bucket}/{object_name}"


def delete_avatar_by_url(url: str | None) -> None:
    """Borra el avatar anterior (best-effort, no debe romper la subida nueva)."""
    if not url:
        return
    prefix = f"{settings.minio_public_url.rstrip('/')}/{settings.minio_avatars_bucket}/"
    if not url.startswith(prefix):
        return
    try:
        _client().remove_object(settings.minio_avatars_bucket, url[len(prefix):])
    except Exception:
        pass
