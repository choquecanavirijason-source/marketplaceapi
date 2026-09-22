"""Añade source_product_id a mp_products."""
from sqlalchemy import text
from app.infrastructure.database.session import engine

def upgrade():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mp_products ADD COLUMN IF NOT EXISTS source_product_id INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mp_products_source_product_id ON mp_products(source_product_id)"))
    print("[OK] mp_products: source_product_id")
