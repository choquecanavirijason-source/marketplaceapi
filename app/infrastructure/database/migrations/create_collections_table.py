from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_collections (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                image_url   VARCHAR(500),
                is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_collection_products (
                id            SERIAL PRIMARY KEY,
                collection_id INTEGER NOT NULL REFERENCES mp_collections(id) ON DELETE CASCADE,
                product_id    INTEGER NOT NULL REFERENCES mp_products(id) ON DELETE CASCADE,
                CONSTRAINT uq_collection_product UNIQUE (collection_id, product_id)
            )
        """))
    print("[OK] mp_collections + mp_collection_products")
