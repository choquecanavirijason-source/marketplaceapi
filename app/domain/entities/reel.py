from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.infrastructure.database import Base


class Reel(Base):
    """Video corto (estilo reels) mostrado en la pantalla de reels de la app.
    Puede o no estar ligado a un producto del catálogo."""
    __tablename__ = "mp_reels"

    id            = Column(Integer, primary_key=True, index=True)
    video_url     = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    caption       = Column(String(300), nullable=True)
    product_id    = Column(Integer, ForeignKey("mp_products.id", ondelete="SET NULL"), nullable=True)
    is_active     = Column(Boolean, default=True, nullable=False)
    sort_order    = Column(Integer, default=0, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", lazy="joined")
