from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_reels (
                id            SERIAL PRIMARY KEY,
                video_url     VARCHAR(500) NOT NULL,
                thumbnail_url VARCHAR(500),
                caption       VARCHAR(300),
                product_id    INTEGER REFERENCES mp_products(id) ON DELETE SET NULL,
                is_active     BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order    INTEGER NOT NULL DEFAULT 0,
                created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    print("[OK] mp_reels")
