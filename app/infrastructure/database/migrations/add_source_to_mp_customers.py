"""Añade source a mp_customers."""
from sqlalchemy import text
from app.infrastructure.database.session import engine

def upgrade():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mp_customers ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'app'"))
    print("[OK] mp_customers: source")
