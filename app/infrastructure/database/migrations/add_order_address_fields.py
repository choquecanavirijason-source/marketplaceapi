"""Migration: añade delivery_address, delivery_district, delivery_references a mp_orders."""
from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine


def upgrade():
    with engine.connect() as conn:
        for col, definition in [
            ("delivery_address",    "TEXT"),
            ("delivery_district",   "VARCHAR(100)"),
            ("delivery_references", "TEXT"),
        ]:
            try:
                conn.execute(text(
                    f"ALTER TABLE mp_orders ADD COLUMN {col} {definition}"
                ))
            except Exception:
                pass  # columna ya existe
        conn.commit()
    print("[OK] mp_orders: delivery_address, delivery_district, delivery_references añadidos")
