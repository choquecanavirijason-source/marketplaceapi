"""Añade country_code a mp_customers."""
from sqlalchemy import text
from app.infrastructure.database.session import engine

def upgrade():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mp_customers ADD COLUMN IF NOT EXISTS country_code VARCHAR(2)"))
    print("[OK] mp_customers: country_code")
