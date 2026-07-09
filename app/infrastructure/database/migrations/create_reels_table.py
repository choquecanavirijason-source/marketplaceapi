from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine

_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_reels (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    video_url     VARCHAR(500) NOT NULL,
    thumbnail_url VARCHAR(500),
    caption       VARCHAR(300),
    product_id    INTEGER REFERENCES mp_products(id) ON DELETE SET NULL,
    is_active     BOOLEAN NOT NULL DEFAULT 1,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_MYSQL = """
CREATE TABLE IF NOT EXISTS mp_reels (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    video_url     VARCHAR(500) NOT NULL,
    thumbnail_url VARCHAR(500),
    caption       VARCHAR(300),
    product_id    INT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order    INT NOT NULL DEFAULT 0,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES mp_products(id) ON DELETE SET NULL
)
"""


def upgrade():
    sql = _SQLITE if settings.database_url.startswith("sqlite") else _MYSQL
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("[OK] mp_reels")
