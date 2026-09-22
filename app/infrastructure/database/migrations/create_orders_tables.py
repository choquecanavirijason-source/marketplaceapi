from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_orders (
                id             SERIAL PRIMARY KEY,
                order_code     VARCHAR(20) NOT NULL UNIQUE,
                customer_name  VARCHAR(150) NOT NULL,
                customer_phone VARCHAR(20) NOT NULL,
                customer_email VARCHAR(150),
                total          DOUBLE PRECISION NOT NULL,
                status         VARCHAR(30) NOT NULL DEFAULT 'pending',
                notes          TEXT,
                created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_order_items (
                id            SERIAL PRIMARY KEY,
                order_id      INTEGER NOT NULL REFERENCES mp_orders(id) ON DELETE CASCADE,
                product_id    INTEGER,
                product_name  VARCHAR(150) NOT NULL,
                product_image VARCHAR(500),
                quantity      INTEGER NOT NULL DEFAULT 1,
                unit_price    DOUBLE PRECISION NOT NULL,
                subtotal      DOUBLE PRECISION NOT NULL
            )
        """))
    print("[OK] mp_orders + mp_order_items")
