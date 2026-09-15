from sqlalchemy import text
from app.config.settings import settings
from app.infrastructure.database.session import engine

_SQLITE = """
CREATE TABLE IF NOT EXISTS mp_presence (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_key VARCHAR(64) NOT NULL UNIQUE,
    last_seen   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_MYSQL = """
CREATE TABLE IF NOT EXISTS mp_presence (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    session_key VARCHAR(64) NOT NULL UNIQUE,
    last_seen   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def upgrade():
    sql = _SQLITE if settings.database_url.startswith("sqlite") else _MYSQL
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("[OK] mp_presence")
