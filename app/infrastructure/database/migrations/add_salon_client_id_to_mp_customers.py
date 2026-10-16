"""Añade salon_client_id a mp_customers."""
from sqlalchemy import text
from app.infrastructure.database.session import engine

def upgrade():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mp_customers ADD COLUMN IF NOT EXISTS salon_client_id INTEGER"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_mp_customers_salon_client_id "
            "ON mp_customers (salon_client_id)"
        ))
    print("[OK] mp_customers: salon_client_id")
