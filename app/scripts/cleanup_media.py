"""Borra del storage (disco o MinIO) los archivos que ningún registro usa.

    python -m app.scripts.cleanup_media           # solo muestra qué borraría
    python -m app.scripts.cleanup_media --apply   # borra de verdad

Ignora lo subido en la última hora: un video en proceso ya está en el storage
pero todavía no tiene su registro en la base. Con --now no hay margen: usarlo
solo si nadie está subiendo archivos en ese momento (ej. justo después de
migrar, cuando todo tiene fecha reciente).
"""
import importlib
import pkgutil
import sys
from datetime import datetime, timedelta, timezone

import app.domain.entities as entities
from app.core import storage
from app.core.media import media_storage_keys
from app.core.media_usage import referenced_media
from app.infrastructure.database.session import SessionLocal

GRACE_PERIOD = timedelta(hours=1)

# Fuera de la app nadie importa todos los modelos, y SQLAlchemy los necesita
# para resolver relaciones (OrderItem -> Order, etc.).
for module in pkgutil.iter_modules(entities.__path__):
    importlib.import_module(f"{entities.__name__}.{module.name}")


def main(apply: bool, grace: timedelta) -> None:
    db = SessionLocal()
    try:
        referenced = referenced_media(db)
    finally:
        db.close()

    keep_keys, keep_prefixes = set(), set()
    for url in referenced:
        keys, prefixes = media_storage_keys(url)
        keep_keys |= keys
        keep_prefixes |= prefixes

    cutoff = datetime.now(timezone.utc) - grace
    orphans = [
        (key, size)
        for key, size, modified in storage.iter_objects("marketplace/")
        if modified < cutoff
        and key not in keep_keys
        and not any(key.startswith(p) for p in keep_prefixes)
    ]

    total = sum(size for _, size in orphans)
    backend = "MinIO" if storage.use_minio() else "disco"
    print(f"Storage: {backend} | archivos en uso: {len(referenced)} | "
          f"huérfanos: {len(orphans)} ({total / 1024 / 1024:.1f} MB)")
    if not apply:
        for key, size in orphans[:20]:
            print(f"  {key} ({size / 1024 / 1024:.1f} MB)")
        if len(orphans) > 20:
            print(f"  ... y {len(orphans) - 20} más")
        print("Nada borrado. Correr con --apply para borrar.")
        return

    for key, _ in orphans:
        storage.delete_key(key)
    print(f"Borrados {len(orphans)} archivos, liberados {total / 1024 / 1024:.1f} MB.")


if __name__ == "__main__":
    main(
        apply="--apply" in sys.argv,
        grace=timedelta(0) if "--now" in sys.argv else GRACE_PERIOD,
    )
