"""Borra del storage (disco, MinIO o AWS S3) los archivos que ningún
registro usa.

    python -m app.scripts.cleanup_media           # solo muestra qué borraría
    python -m app.scripts.cleanup_media --apply   # borra de verdad

Ignora lo subido en la última hora: un video en proceso ya está en el storage
pero todavía no tiene su registro en la base. Con --now no hay margen: usarlo
solo si nadie está subiendo archivos en ese momento (ej. justo después de
migrar, cuando todo tiene fecha reciente).

Barre "marketplace/reels/" y el resto por separado — ver storage.py: con
reels_storage_backend="s3" viven en un bucket distinto al del resto de media.
"""
import importlib
import pkgutil
import sys
from datetime import datetime, timedelta, timezone

import app.domain.entities as entities
from app.core import storage
from app.core.media import media_storage_keys
from app.core.media_usage import referenced_media
from app.core.storage import REELS_KEY_PREFIX
from app.infrastructure.database.session import SessionLocal

GRACE_PERIOD = timedelta(hours=1)
SWEEP_PREFIXES = [REELS_KEY_PREFIX, "marketplace/"]

# Fuera de la app nadie importa todos los modelos, y SQLAlchemy los necesita
# para resolver relaciones (OrderItem -> Order, etc.).
for module in pkgutil.iter_modules(entities.__path__):
    importlib.import_module(f"{entities.__name__}.{module.name}")


def _backend_label(prefix: str) -> str:
    backend = storage._backend_for(prefix)
    return {"s3": "AWS S3", "minio": "MinIO", "local": "disco"}[backend]


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
    total_orphans = []
    seen_keys = set()
    for sweep_prefix in SWEEP_PREFIXES:
        # "marketplace/" ya incluye "marketplace/reels/" si están en el
        # mismo backend — sin esto se listaría doble. Solo se separan si de
        # verdad quedan en backends distintos.
        if sweep_prefix != REELS_KEY_PREFIX and storage._backend_for(sweep_prefix) == storage._backend_for(REELS_KEY_PREFIX):
            continue
        orphans = [
            (key, size)
            for key, size, modified in storage.iter_objects(sweep_prefix)
            if modified < cutoff
            and key not in keep_keys
            and not any(key.startswith(p) for p in keep_prefixes)
            and key not in seen_keys
        ]
        seen_keys.update(key for key, _ in orphans)
        total = sum(size for _, size in orphans)
        print(f"Storage: {_backend_label(sweep_prefix)} ({sweep_prefix}) | "
              f"huérfanos: {len(orphans)} ({total / 1024 / 1024:.1f} MB)")
        total_orphans.extend(orphans)

    print(f"Total | archivos en uso: {len(referenced)} | "
          f"huérfanos: {len(total_orphans)} "
          f"({sum(s for _, s in total_orphans) / 1024 / 1024:.1f} MB)")
    if not apply:
        for key, size in total_orphans[:20]:
            print(f"  {key} ({size / 1024 / 1024:.1f} MB)")
        if len(total_orphans) > 20:
            print(f"  ... y {len(total_orphans) - 20} más")
        print("Nada borrado. Correr con --apply para borrar.")
        return

    for key, _ in total_orphans:
        storage.delete_key(key)
    freed = sum(size for _, size in total_orphans) / 1024 / 1024
    print(f"Borrados {len(total_orphans)} archivos, liberados {freed:.1f} MB.")


if __name__ == "__main__":
    main(
        apply="--apply" in sys.argv,
        grace=timedelta(0) if "--now" in sys.argv else GRACE_PERIOD,
    )
