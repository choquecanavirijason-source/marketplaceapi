"""Añade is_featured a mp_products."""
from sqlalchemy import text
from app.infrastructure.database.session import engine

def upgrade():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mp_products ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT FALSE"))
    print("[OK] mp_products: is_featured")
