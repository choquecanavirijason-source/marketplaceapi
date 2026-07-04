"""Migration: agrega columna source a mp_customers ('app' | 'salon')."""
from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(mp_customers)"))
            cols = [row[1] for row in result]
            if "source" not in cols:
                conn.execute(text(
                    "ALTER TABLE mp_customers ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'app'"
                ))
                conn.commit()
                print("[OK] mp_customers: columna source agregada")
        except Exception as e:
            print(f"[WARN] add_source_to_mp_customers: {e}")
