from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine

_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_products (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           VARCHAR(150) NOT NULL,
    brand          VARCHAR(100),
    description    TEXT,
    price          FLOAT NOT NULL DEFAULT 0.0,
    original_price FLOAT,
    image_url      VARCHAR(500),
    category_id    INTEGER REFERENCES mp_categories(id) ON DELETE SET NULL,
    stock          INTEGER NOT NULL DEFAULT 0,
    rating         FLOAT DEFAULT 0.0,
    review_count   INTEGER DEFAULT 0,
    is_active      BOOLEAN NOT NULL DEFAULT 1,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_MYSQL = """
CREATE TABLE IF NOT EXISTS mp_products (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(150) NOT NULL,
    brand          VARCHAR(100),
    description    TEXT,
    price          FLOAT NOT NULL DEFAULT 0.0,
    original_price FLOAT,
    image_url      VARCHAR(500),
    category_id    INT,
    stock          INT NOT NULL DEFAULT 0,
    rating         FLOAT DEFAULT 0.0,
    review_count   INT DEFAULT 0,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES mp_categories(id) ON DELETE SET NULL
)
"""


def upgrade():
    sql = _SQLITE if settings.database_url.startswith("sqlite") else _MYSQL
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("[OK] mp_products")
