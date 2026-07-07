from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine

_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_ads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       VARCHAR(150) NOT NULL,
    subtitle    VARCHAR(300),
    cta_label   VARCHAR(60) NOT NULL DEFAULT 'Ver más',
    image_url   VARCHAR(500) NOT NULL,
    link_type   VARCHAR(20) NOT NULL DEFAULT 'none',
    link_value  VARCHAR(300),
    is_active   BOOLEAN NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_MYSQL = """
CREATE TABLE IF NOT EXISTS mp_ads (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(150) NOT NULL,
    subtitle    VARCHAR(300),
    cta_label   VARCHAR(60) NOT NULL DEFAULT 'Ver más',
    image_url   VARCHAR(500) NOT NULL,
    link_type   VARCHAR(20) NOT NULL DEFAULT 'none',
    link_value  VARCHAR(300),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order  INT NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def upgrade():
    sql = _SQLITE if settings.database_url.startswith("sqlite") else _MYSQL
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("[OK] mp_ads")
