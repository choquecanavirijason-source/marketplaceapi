"""Migration: añade is_featured a mp_products (destacado manual desde el admin)."""
from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine


def upgrade():
    is_sqlite = settings.database_url.startswith("sqlite")
    with engine.connect() as conn:
        try:
            if is_sqlite:
                conn.execute(text(
                    "ALTER TABLE mp_products ADD COLUMN is_featured BOOLEAN NOT NULL DEFAULT 0"
                ))
            else:
                conn.execute(text(
                    "ALTER TABLE mp_products ADD COLUMN is_featured BOOLEAN NOT NULL DEFAULT FALSE"
                ))
        except Exception:
            pass  # columna ya existe
        conn.commit()
    print("[OK] mp_products: is_featured añadido")
