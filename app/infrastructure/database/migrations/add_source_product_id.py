"""Migration: añade source_product_id a mp_products.

Vincula un producto importado del inventario del salón (elashesbackend) con
su Product.id original, para poder sincronizar el stock más adelante sin
depender de coincidencia de nombres.
"""
from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine


def upgrade():
    is_sqlite = settings.database_url.startswith("sqlite")
    with engine.connect() as conn:
        try:
            if is_sqlite:
                conn.execute(text(
                    "ALTER TABLE mp_products ADD COLUMN source_product_id INTEGER"
                ))
            else:
                conn.execute(text(
                    "ALTER TABLE mp_products ADD COLUMN source_product_id INT"
                ))
        except Exception:
            pass  # columna ya existe
        conn.commit()
    print("[OK] mp_products: source_product_id añadido")
