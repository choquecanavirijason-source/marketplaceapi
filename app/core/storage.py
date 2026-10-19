"""Destino final de los archivos subidos: disco local, bucket MinIO, o AWS S3.

Las claves son rutas relativas tipo "marketplace/reels/videos/abc/master.m3u8".

Para todo lo que NO sea reel (productos, categorías, anuncios, colecciones),
la URL pública siempre es "/media/<clave>" y el backend es storage_backend
("local" o "minio") — sin cambios respecto a antes.

Los REELS (claves bajo "marketplace/reels/") pueden ir aparte a AWS S3, vía
reels_storage_backend="s3": en ese caso la URL pública es la URL directa del
bucket (no "/media/..."), porque el archivo no vive en el servidor ni en
MinIO. Con reels_storage_backend vacío, los reels siguen storage_backend
igual que el resto, así que activar AWS es un cambio de configuración, no
de código.
"""
import mimetypes
import os
import posixpath
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterator, List, Tuple

from app.config.settings import settings

_CONTENT_TYPES = {
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts": "video/mp2t",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".webp": "image/webp",
}

REELS_KEY_PREFIX = "marketplace/reels/"


def _is_reel_key(key: str) -> bool:
    return key.startswith(REELS_KEY_PREFIX)


def _backend_for(key: str) -> str:
    """"local" | "minio" | "s3" — la que de verdad aplica para esta clave."""
    if _is_reel_key(key) and settings.reels_storage_backend.lower() == "s3":
        return "s3"
    return "minio" if settings.storage_backend.lower() == "minio" else "local"


def use_minio() -> bool:
    """Compatibilidad: True si el storage GENERAL (no-reels) es MinIO."""
    return settings.storage_backend.lower() == "minio"


def aws_base_url() -> str:
    if settings.aws_public_base_url:
        return settings.aws_public_base_url.rstrip("/")
    return f"https://{settings.aws_bucket}.s3.{settings.aws_region}.amazonaws.com"


def public_url(key: str) -> str:
    if _backend_for(key) == "s3":
        return f"{aws_base_url()}/{key}"
    return f"/media/{key}"


def _content_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _CONTENT_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


@lru_cache(maxsize=1)
def _minio_client():
    from minio import Minio

    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


@lru_cache(maxsize=1)
def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def put_file(local_path: str, key: str) -> None:
    """Mueve un archivo local a su destino final bajo `key`."""
    backend = _backend_for(key)
    if backend == "s3":
        _s3_client().upload_file(
            local_path, settings.aws_bucket, key,
            ExtraArgs={"ContentType": _content_type(local_path)},
        )
        os.remove(local_path)
        return
    if backend == "minio":
        _minio_client().fput_object(
            settings.minio_bucket, key, local_path, content_type=_content_type(local_path)
        )
        os.remove(local_path)
        return
    dest = os.path.join(settings.media_base_path, *key.split("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(local_path, dest)
    # 644: nginx (que no corre como root) necesita poder leerlo.
    os.chmod(dest, 0o644)


def put_dir(local_dir: str, key_prefix: str, last: str = "") -> None:
    """Sube todos los archivos de `local_dir` bajo `key_prefix/`.

    `last` se sube al final: para HLS es el master.m3u8, así nunca queda
    publicado apuntando a segmentos que todavía no se subieron."""
    names = sorted(os.listdir(local_dir), key=lambda n: n == last)
    for name in names:
        put_file(os.path.join(local_dir, name), posixpath.join(key_prefix, name))


def list_keys(prefix: str) -> List[str]:
    """Claves de archivos (no carpetas) cuyo nombre empieza con `prefix`,
    dentro de la misma "carpeta" (no recursivo)."""
    backend = _backend_for(prefix)
    if backend == "s3":
        parent_key, name_prefix = posixpath.split(prefix)
        resp = _s3_client().list_objects_v2(
            Bucket=settings.aws_bucket, Prefix=f"{parent_key}/" if parent_key else "", Delimiter="/"
        )
        return [
            obj["Key"]
            for obj in resp.get("Contents", [])
            if posixpath.basename(obj["Key"]).startswith(name_prefix)
        ]
    if backend == "minio":
        return [
            obj.object_name
            for obj in _minio_client().list_objects(settings.minio_bucket, prefix=prefix)
            if not obj.is_dir
        ]
    parent_key, name_prefix = posixpath.split(prefix)
    parent_fs = os.path.join(settings.media_base_path, *parent_key.split("/"))
    if not os.path.isdir(parent_fs):
        return []
    return [
        posixpath.join(parent_key, name)
        for name in os.listdir(parent_fs)
        if name.startswith(name_prefix) and os.path.isfile(os.path.join(parent_fs, name))
    ]


def delete_key(key: str) -> None:
    backend = _backend_for(key)
    if backend == "s3":
        _s3_client().delete_object(Bucket=settings.aws_bucket, Key=key)
        return
    if backend == "minio":
        _minio_client().remove_object(settings.minio_bucket, key)
        return
    path = os.path.join(settings.media_base_path, *key.split("/"))
    if os.path.isfile(path):
        os.remove(path)


def delete_prefix(prefix: str) -> None:
    """Borra todo lo que cuelga de una "carpeta" (prefix terminado en "/")."""
    backend = _backend_for(prefix)
    if backend == "s3":
        client = _s3_client()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.aws_bucket, Prefix=prefix):
            keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if keys:
                client.delete_objects(Bucket=settings.aws_bucket, Delete={"Objects": keys})
        return
    if backend == "minio":
        client = _minio_client()
        for obj in client.list_objects(settings.minio_bucket, prefix=prefix, recursive=True):
            client.remove_object(settings.minio_bucket, obj.object_name)
        return
    shutil.rmtree(os.path.join(settings.media_base_path, *prefix.strip("/").split("/")), ignore_errors=True)


def iter_objects(prefix: str) -> Iterator[Tuple[str, int, datetime]]:
    """(clave, tamaño en bytes, última modificación UTC) de todo lo que hay
    bajo `prefix`, recursivo.

    Nota: con reels en S3 y el resto en local/MinIO, un `prefix` amplio como
    "marketplace/" NO cubre los dos a la vez — el llamador (ej. el comando de
    limpieza) debe recorrer "marketplace/reels/" y el resto por separado si
    usa backends distintos. Ver [app/scripts/cleanup_media.py]."""
    backend = _backend_for(prefix)
    if backend == "s3":
        client = _s3_client()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.aws_bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                yield obj["Key"], obj["Size"], obj["LastModified"]
        return
    if backend == "minio":
        for obj in _minio_client().list_objects(settings.minio_bucket, prefix=prefix, recursive=True):
            yield obj.object_name, obj.size, obj.last_modified
        return
    root = os.path.join(settings.media_base_path, *prefix.strip("/").split("/"))
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            key = os.path.relpath(full, settings.media_base_path).replace(os.sep, "/")
            stat = os.stat(full)
            yield key, stat.st_size, datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
