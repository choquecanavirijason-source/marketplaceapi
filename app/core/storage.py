"""Destino final de los archivos subidos: disco local o bucket MinIO.

Las claves son rutas relativas tipo "marketplace/reels/videos/abc/master.m3u8"
y la URL pública siempre es "/media/<clave>", en los dos modos. Así la base de
datos, la app y el admin no cambian al pasar de disco a MinIO.
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


def use_minio() -> bool:
    return settings.storage_backend.lower() == "minio"


def public_url(key: str) -> str:
    return f"/media/{key}"


def _content_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _CONTENT_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


@lru_cache(maxsize=1)
def _client():
    from minio import Minio

    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def put_file(local_path: str, key: str) -> None:
    """Mueve un archivo local a su destino final bajo `key`."""
    if use_minio():
        _client().fput_object(
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
    if use_minio():
        return [
            obj.object_name
            for obj in _client().list_objects(settings.minio_bucket, prefix=prefix)
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
    if use_minio():
        _client().remove_object(settings.minio_bucket, key)
        return
    path = os.path.join(settings.media_base_path, *key.split("/"))
    if os.path.isfile(path):
        os.remove(path)


def delete_prefix(prefix: str) -> None:
    """Borra todo lo que cuelga de una "carpeta" (prefix terminado en "/")."""
    if use_minio():
        for obj in _client().list_objects(settings.minio_bucket, prefix=prefix, recursive=True):
            _client().remove_object(settings.minio_bucket, obj.object_name)
        return
    shutil.rmtree(os.path.join(settings.media_base_path, *prefix.strip("/").split("/")), ignore_errors=True)


def iter_objects(prefix: str) -> Iterator[Tuple[str, int, datetime]]:
    """(clave, tamaño en bytes, última modificación UTC) de todo lo que hay
    bajo `prefix`, recursivo."""
    if use_minio():
        for obj in _client().list_objects(settings.minio_bucket, prefix=prefix, recursive=True):
            yield obj.object_name, obj.size, obj.last_modified
        return
    root = os.path.join(settings.media_base_path, *prefix.strip("/").split("/"))
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            key = os.path.relpath(full, settings.media_base_path).replace(os.sep, "/")
            stat = os.stat(full)
            yield key, stat.st_size, datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
