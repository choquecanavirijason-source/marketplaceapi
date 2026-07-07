"""Migration: reconcilia el nombre de la columna de contraseña en mp_customers.

Versiones previas de create_mp_customers creaban la columna física 'hashed_pw',
pero la entidad Customer mapea 'password_hash' (Column("password_hash", ...)).
Ese desajuste hace que cualquier SELECT sobre mp_customers falle con
"no such column: password_hash" -> 500 en login/register.

Renombra hashed_pw -> password_hash si la BD quedó con el nombre antiguo.
Idempotente: si ya existe password_hash, no hace nada.
"""
from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.connect() as conn:
        try:
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(mp_customers)"))]
            if not cols:
                return  # la tabla aún no existe; create_mp_customers ya la crea correcta
            if "password_hash" not in cols and "hashed_pw" in cols:
                conn.execute(text(
                    "ALTER TABLE mp_customers RENAME COLUMN hashed_pw TO password_hash"
                ))
                conn.commit()
                print("[OK] mp_customers: columna hashed_pw renombrada a password_hash")
        except Exception as e:
            print(f"[WARN] fix_mp_customers_password_col: {e}")
