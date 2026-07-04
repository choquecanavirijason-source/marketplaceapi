from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine

_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    image_url   VARCHAR(500),
    is_active   BOOLEAN NOT NULL DEFAULT 1,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_MYSQL = """
CREATE TABLE IF NOT EXISTS mp_categories (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    image_url   VARCHAR(500),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def upgrade():
    sql = _SQLITE if settings.database_url.startswith("sqlite") else _MYSQL
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("[OK] mp_categories")
