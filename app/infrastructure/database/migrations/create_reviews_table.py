"""Migration: crea la tabla mp_reviews (reseñas de productos)."""
from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.connect() as conn:
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS mp_reviews (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id    INTEGER NOT NULL,
                    customer_id   INTEGER,
                    customer_name VARCHAR(150) NOT NULL,
                    rating        INTEGER NOT NULL,
                    comment       TEXT,
                    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES mp_products(id) ON DELETE CASCADE,
                    FOREIGN KEY (customer_id) REFERENCES mp_customers(id) ON DELETE SET NULL
                )
            """))
            conn.commit()
        except Exception as e:
            print(f"[WARN] mp_reviews: {e}")
    print("[OK] mp_reviews creada")
