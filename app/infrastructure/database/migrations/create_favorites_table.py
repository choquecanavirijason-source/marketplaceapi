from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_favorites (
                id          SERIAL PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES mp_customers(id) ON DELETE CASCADE,
                product_id  INTEGER NOT NULL REFERENCES mp_products(id) ON DELETE CASCADE,
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_favorite_customer_product UNIQUE (customer_id, product_id)
            )
        """))
    print("[OK] mp_favorites")
