"""Añade avatar_url a mp_customers (foto de perfil guardada en MinIO)."""
from sqlalchemy import text
from app.infrastructure.database.session import engine

def upgrade():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mp_customers ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)"))
    print("[OK] mp_customers: avatar_url")
