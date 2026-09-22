from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_reel_likes (
                id          SERIAL PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES mp_customers(id) ON DELETE CASCADE,
                reel_id     INTEGER NOT NULL REFERENCES mp_reels(id) ON DELETE CASCADE,
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_reel_like_customer_reel UNIQUE (customer_id, reel_id)
            )
        """))
    print("[OK] mp_reel_likes")
