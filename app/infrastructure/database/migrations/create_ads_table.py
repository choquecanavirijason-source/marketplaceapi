from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_ads (
                id          SERIAL PRIMARY KEY,
                title       VARCHAR(150) NOT NULL,
                subtitle    VARCHAR(300),
                cta_label   VARCHAR(60) NOT NULL DEFAULT 'Ver más',
                image_url   VARCHAR(500) NOT NULL,
                link_type   VARCHAR(20) NOT NULL DEFAULT 'none',
                link_value  VARCHAR(300),
                is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    print("[OK] mp_ads")
