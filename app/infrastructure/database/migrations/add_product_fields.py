"""Migration: añade video_url y low_stock_threshold a mp_products."""
from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine


def upgrade():
    is_sqlite = settings.database_url.startswith("sqlite")
    with engine.connect() as conn:
        try:
            if is_sqlite:
                conn.execute(text(
                    "ALTER TABLE mp_products ADD COLUMN video_url VARCHAR(500)"
                ))
        except Exception:
            pass  # columna ya existe
        try:
            if is_sqlite:
                conn.execute(text(
                    "ALTER TABLE mp_products ADD COLUMN low_stock_threshold INTEGER NOT NULL DEFAULT 5"
                ))
        except Exception:
            pass
        if not is_sqlite:
            try:
                conn.execute(text(
                    "ALTER TABLE mp_products ADD COLUMN video_url VARCHAR(500)"
                ))
            except Exception:
                pass
            try:
                conn.execute(text(
                    "ALTER TABLE mp_products ADD COLUMN low_stock_threshold INT NOT NULL DEFAULT 5"
                ))
            except Exception:
                pass
        conn.commit()
    print("[OK] mp_products: video_url, low_stock_threshold añadidos")
