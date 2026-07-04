from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine

_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_collections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    image_url   VARCHAR(500),
    is_active   BOOLEAN NOT NULL DEFAULT 1,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_SQLITE_JUNCTION = """
CREATE TABLE IF NOT EXISTS mp_collection_products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL REFERENCES mp_collections(id) ON DELETE CASCADE,
    product_id    INTEGER NOT NULL REFERENCES mp_products(id) ON DELETE CASCADE,
    UNIQUE(collection_id, product_id)
)
"""

_MYSQL = """
CREATE TABLE IF NOT EXISTS mp_collections (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    image_url   VARCHAR(500),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_MYSQL_JUNCTION = """
CREATE TABLE IF NOT EXISTS mp_collection_products (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    collection_id INT NOT NULL,
    product_id    INT NOT NULL,
    UNIQUE KEY uq_col_prod (collection_id, product_id),
    FOREIGN KEY (collection_id) REFERENCES mp_collections(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id)    REFERENCES mp_products(id)    ON DELETE CASCADE
)
"""


def upgrade():
    sqlite = settings.database_url.startswith("sqlite")
    main_sql = _SQLITE if sqlite else _MYSQL
    junc_sql = _SQLITE_JUNCTION if sqlite else _MYSQL_JUNCTION
    with engine.connect() as conn:
        conn.execute(text(main_sql))
        conn.execute(text(junc_sql))
        conn.commit()
    print("[OK] mp_collections + mp_collection_products")
