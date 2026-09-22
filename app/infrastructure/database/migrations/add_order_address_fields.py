"""Añade campos de dirección de entrega a mp_orders."""
from sqlalchemy import text
from app.infrastructure.database.session import engine

def upgrade():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mp_orders ADD COLUMN IF NOT EXISTS delivery_address TEXT"))
        conn.execute(text("ALTER TABLE mp_orders ADD COLUMN IF NOT EXISTS delivery_district VARCHAR(100)"))
        conn.execute(text("ALTER TABLE mp_orders ADD COLUMN IF NOT EXISTS delivery_references TEXT"))
    print("[OK] mp_orders: delivery_address, delivery_district, delivery_references")
