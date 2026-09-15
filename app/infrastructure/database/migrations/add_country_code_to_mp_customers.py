"""Migracion: agrega columna country_code a mp_customers (codigo ISO de pais,
pre-llenado automaticamente en el registro segun el idioma/region del
dispositivo, editable por el cliente antes de crear la cuenta)."""
from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine


def _column_exists(conn, table_name: str, column_name: str, is_sqlite: bool) -> bool:
    if is_sqlite:
        result = conn.execute(text(f"PRAGMA table_info({table_name})"))
        return any(row[1] == column_name for row in result)
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.scalar() > 0


def upgrade():
    is_sqlite = settings.database_url.startswith("sqlite")
    with engine.connect() as conn:
        if _column_exists(conn, "mp_customers", "country_code", is_sqlite):
            print("[OK] mp_customers: country_code ya existe")
            return
        conn.execute(text("ALTER TABLE mp_customers ADD COLUMN country_code VARCHAR(2) NULL"))
        conn.commit()
        print("[OK] mp_customers: columna country_code agregada")
