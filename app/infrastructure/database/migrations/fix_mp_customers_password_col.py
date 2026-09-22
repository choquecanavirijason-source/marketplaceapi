"""Reconciliación histórica del nombre password_hash en PostgreSQL."""
from sqlalchemy import text
from app.infrastructure.database.session import engine

def upgrade():
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'mp_customers'
        """))
        cols = {row[0] for row in result}
        if "hashed_pw" in cols and "password_hash" not in cols:
            conn.execute(text(
                "ALTER TABLE mp_customers RENAME COLUMN hashed_pw TO password_hash"
            ))
            print("[OK] mp_customers: hashed_pw -> password_hash")
