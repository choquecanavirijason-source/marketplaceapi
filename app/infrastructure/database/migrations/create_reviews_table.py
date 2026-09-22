"""Crea la tabla mp_reviews."""
from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_reviews (
                id            SERIAL PRIMARY KEY,
                product_id    INTEGER NOT NULL REFERENCES mp_products(id) ON DELETE CASCADE,
                customer_id   INTEGER REFERENCES mp_customers(id) ON DELETE SET NULL,
                customer_name VARCHAR(150) NOT NULL,
                rating        INTEGER NOT NULL,
                comment       TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
    print("[OK] mp_reviews")
