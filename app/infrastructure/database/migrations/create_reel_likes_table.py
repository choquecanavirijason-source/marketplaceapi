from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine

_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_reel_likes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES mp_customers(id) ON DELETE CASCADE,
    reel_id     INTEGER NOT NULL REFERENCES mp_reels(id) ON DELETE CASCADE,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (customer_id, reel_id)
)
"""

_MYSQL = """
CREATE TABLE IF NOT EXISTS mp_reel_likes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    reel_id     INT NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_reel_like_customer_reel (customer_id, reel_id),
    FOREIGN KEY (customer_id) REFERENCES mp_customers(id) ON DELETE CASCADE,
    FOREIGN KEY (reel_id) REFERENCES mp_reels(id) ON DELETE CASCADE
)
"""


def upgrade():
    sql = _SQLITE if settings.database_url.startswith("sqlite") else _MYSQL
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("[OK] mp_reel_likes")
