from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_products (
                id                  SERIAL PRIMARY KEY,
                name                VARCHAR(150) NOT NULL,
                brand               VARCHAR(100),
                description         TEXT,
                price               DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                original_price      DOUBLE PRECISION,
                image_url           VARCHAR(500),
                category_id         INTEGER REFERENCES mp_categories(id) ON DELETE SET NULL,
                stock               INTEGER NOT NULL DEFAULT 0,
                rating              DOUBLE PRECISION DEFAULT 0.0,
                review_count        INTEGER DEFAULT 0,
                is_active           BOOLEAN NOT NULL DEFAULT TRUE,
                created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    print("[OK] mp_products")
