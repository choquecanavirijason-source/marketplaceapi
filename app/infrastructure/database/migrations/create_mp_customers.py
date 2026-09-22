"""Crea la tabla de clientes del marketplace."""
from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_customers (
                id            SERIAL PRIMARY KEY,
                name          VARCHAR(150) NOT NULL,
                phone         VARCHAR(20) NOT NULL DEFAULT '',
                email         VARCHAR(150) NOT NULL UNIQUE,
                password_hash VARCHAR(255),
                is_active     BOOLEAN NOT NULL DEFAULT TRUE,
                created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                source        VARCHAR(20) NOT NULL DEFAULT 'app',
                country_code  VARCHAR(2)
            )
        """))
    print("[OK] mp_customers")
