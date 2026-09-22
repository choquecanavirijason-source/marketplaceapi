from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_presence (
                id          SERIAL PRIMARY KEY,
                session_key VARCHAR(64) NOT NULL UNIQUE,
                last_seen   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    print("[OK] mp_presence")
