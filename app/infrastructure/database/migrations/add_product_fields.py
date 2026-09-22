"""Añade video_url y low_stock_threshold a mp_products."""
from sqlalchemy import text
from app.infrastructure.database.session import engine

def upgrade():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mp_products ADD COLUMN IF NOT EXISTS video_url VARCHAR(500)"))
        conn.execute(text("ALTER TABLE mp_products ADD COLUMN IF NOT EXISTS low_stock_threshold INTEGER NOT NULL DEFAULT 5"))
    print("[OK] mp_products: video_url, low_stock_threshold")
