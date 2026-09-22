"""Añade customer_id a mp_orders y hace backfill por email cuando es posible."""
from sqlalchemy import text
from app.infrastructure.database.session import engine

def upgrade():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mp_orders ADD COLUMN IF NOT EXISTS customer_id INTEGER"))
        conn.execute(text("""
            UPDATE mp_orders AS o
            SET customer_id = c.id
            FROM mp_customers AS c
            WHERE o.customer_id IS NULL
              AND o.customer_email IS NOT NULL
              AND LOWER(o.customer_email) = LOWER(c.email)
        """))
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_mp_orders_customer_id'
                ) THEN
                    ALTER TABLE mp_orders
                    ADD CONSTRAINT fk_mp_orders_customer_id
                    FOREIGN KEY (customer_id)
                    REFERENCES mp_customers(id)
                    ON DELETE SET NULL;
                END IF;
            END $$;
        """))
    print("[OK] mp_orders: customer_id + backfill + FK")
