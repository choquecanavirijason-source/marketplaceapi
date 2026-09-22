from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mp_delivery_points (
                id            SERIAL PRIMARY KEY,
                country_code  VARCHAR(2) NOT NULL,
                country_name  VARCHAR(80) NOT NULL,
                city          VARCHAR(100),
                name          VARCHAR(150) NOT NULL,
                address       VARCHAR(300) NOT NULL,
                reference     VARCHAR(300),
                schedule      VARCHAR(150),
                phone         VARCHAR(30),
                is_active     BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order    INTEGER NOT NULL DEFAULT 0,
                created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mp_delivery_points_country ON mp_delivery_points(country_code)"))
    print("[OK] mp_delivery_points")
