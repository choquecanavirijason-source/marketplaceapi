"""Migration: crea la tabla mp_customers para auth propio del marketplace."""
from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.connect() as conn:
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS mp_customers (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    name          VARCHAR(150) NOT NULL,
                    phone         VARCHAR(20),
                    email         VARCHAR(150) NOT NULL UNIQUE,
                    -- Nombre físico que mapea la entidad Customer: Column("password_hash", ...)
                    password_hash VARCHAR(255),
                    is_active     INTEGER NOT NULL DEFAULT 1,
                    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception as e:
            print(f"[WARN] mp_customers: {e}")
    print("[OK] mp_customers creada")
