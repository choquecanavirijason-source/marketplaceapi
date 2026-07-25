from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine

_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_delivery_points (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code  VARCHAR(2) NOT NULL,
    country_name  VARCHAR(80) NOT NULL,
    city          VARCHAR(100),
    name          VARCHAR(150) NOT NULL,
    address       VARCHAR(300) NOT NULL,
    reference     VARCHAR(300),
    schedule      VARCHAR(150),
    phone         VARCHAR(30),
    is_active     BOOLEAN NOT NULL DEFAULT 1,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_MYSQL = """
CREATE TABLE IF NOT EXISTS mp_delivery_points (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    country_code  VARCHAR(2) NOT NULL,
    country_name  VARCHAR(80) NOT NULL,
    city          VARCHAR(100),
    name          VARCHAR(150) NOT NULL,
    address       VARCHAR(300) NOT NULL,
    reference     VARCHAR(300),
    schedule      VARCHAR(150),
    phone         VARCHAR(30),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order    INT NOT NULL DEFAULT 0,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_mp_delivery_points_country (country_code)
)
"""


def upgrade():
    sql = _SQLITE if settings.database_url.startswith("sqlite") else _MYSQL
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("[OK] mp_delivery_points")
