from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_categories (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                image_url   VARCHAR(500),
                is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    print("[OK] mp_categories")
