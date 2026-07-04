from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine

_ORDERS_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    order_code     VARCHAR(20) NOT NULL UNIQUE,
    customer_name  VARCHAR(150) NOT NULL,
    customer_phone VARCHAR(20)  NOT NULL,
    customer_email VARCHAR(150),
    total          FLOAT NOT NULL,
    status         VARCHAR(30) NOT NULL DEFAULT 'pending',
    notes          TEXT,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_ITEMS_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_order_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES mp_orders(id) ON DELETE CASCADE,
    product_id    INTEGER,
    product_name  VARCHAR(150) NOT NULL,
    product_image VARCHAR(500),
    quantity      INTEGER NOT NULL DEFAULT 1,
    unit_price    FLOAT NOT NULL,
    subtotal      FLOAT NOT NULL
)
"""

# Migración: elimina NOT NULL de product_id si ya existe la tabla con esa restricción
_ALTER_ITEMS_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_order_items_new (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES mp_orders(id) ON DELETE CASCADE,
    product_id    INTEGER,
    product_name  VARCHAR(150) NOT NULL,
    product_image VARCHAR(500),
    quantity      INTEGER NOT NULL DEFAULT 1,
    unit_price    FLOAT NOT NULL,
    subtotal      FLOAT NOT NULL
);
INSERT OR IGNORE INTO mp_order_items_new
    SELECT id, order_id, product_id, product_name, product_image, quantity, unit_price, subtotal
    FROM mp_order_items;
DROP TABLE mp_order_items;
ALTER TABLE mp_order_items_new RENAME TO mp_order_items;
"""

_ORDERS_MYSQL = """
CREATE TABLE IF NOT EXISTS mp_orders (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    order_code     VARCHAR(20) NOT NULL UNIQUE,
    customer_name  VARCHAR(150) NOT NULL,
    customer_phone VARCHAR(20)  NOT NULL,
    customer_email VARCHAR(150),
    total          FLOAT NOT NULL,
    status         VARCHAR(30) NOT NULL DEFAULT 'pending',
    notes          TEXT,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
"""

_ITEMS_MYSQL = """
CREATE TABLE IF NOT EXISTS mp_order_items (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    order_id      INT NOT NULL,
    product_id    INT NOT NULL,
    product_name  VARCHAR(150) NOT NULL,
    product_image VARCHAR(500),
    quantity      INT NOT NULL DEFAULT 1,
    unit_price    FLOAT NOT NULL,
    subtotal      FLOAT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES mp_orders(id) ON DELETE CASCADE
)
"""


def _needs_product_id_migration(conn) -> bool:
    """Detecta si product_id en mp_order_items todavía tiene NOT NULL."""
    try:
        rows = conn.execute(text("PRAGMA table_info(mp_order_items)")).fetchall()
        for row in rows:
            col_name = row[1]
            notnull  = row[3]
            if col_name == "product_id" and notnull == 1:
                return True
    except Exception:
        pass
    return False


def upgrade():
    is_sqlite = settings.database_url.startswith("sqlite")
    with engine.connect() as conn:
        conn.execute(text(_ORDERS_SQLITE if is_sqlite else _ORDERS_MYSQL))
        conn.execute(text(_ITEMS_SQLITE if is_sqlite else _ITEMS_MYSQL))

        # Si la tabla ya existía con NOT NULL en product_id, migrarla
        if is_sqlite and _needs_product_id_migration(conn):
            for stmt in _ALTER_ITEMS_SQLITE.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(text(stmt))
            print("[migration] mp_order_items.product_id → nullable")

        conn.commit()
    print("[OK] mp_orders + mp_order_items")
