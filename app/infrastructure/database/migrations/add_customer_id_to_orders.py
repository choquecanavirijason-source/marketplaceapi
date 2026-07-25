"""Migracion: agrega customer_id a mp_orders (dueno real del pedido, ligado
a la cuenta autenticada en vez de un telefono de texto libre). Hace un
backfill best-effort para pedidos viejos: si el email del pedido matchea
(sin distinguir mayusculas) el email de una cuenta, se vincula; si no
matchea nada, se deja NULL — nunca se inventa un vinculo."""
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
        if _column_exists(conn, "mp_orders", "customer_id", is_sqlite):
            print("[OK] mp_orders: customer_id ya existe")
            return

        col_type = "INTEGER" if is_sqlite else "INT"
        conn.execute(text(f"ALTER TABLE mp_orders ADD COLUMN customer_id {col_type} NULL"))
        conn.commit()

        rows = conn.execute(
            text(
                "SELECT o.id, c.id FROM mp_orders o "
                "JOIN mp_customers c ON LOWER(o.customer_email) = LOWER(c.email) "
                "WHERE o.customer_email IS NOT NULL"
            )
        ).fetchall()
        for order_id, customer_id in rows:
            conn.execute(
                text("UPDATE mp_orders SET customer_id = :cid WHERE id = :oid"),
                {"cid": customer_id, "oid": order_id},
            )
        conn.commit()
        print(f"[OK] mp_orders: customer_id agregado. Backfill por email: {len(rows)} pedidos vinculados.")
