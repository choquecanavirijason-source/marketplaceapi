from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.infrastructure.database import Base


class Ad(Base):
    """Banner publicitario mostrado en el carrusel de la app (home)."""
    __tablename__ = "mp_ads"

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String(150), nullable=False)
    subtitle    = Column(String(300), nullable=True)
    cta_label   = Column(String(60), nullable=False, default="Ver más")
    image_url   = Column(String(500), nullable=False)
    # Destino al tocar el banner:
    # 'none' | 'product' | 'collection' | 'category' | 'url' | 'booking' | 'pickup' | 'catalog'
    link_type   = Column(String(20), nullable=False, default="none")
    link_value  = Column(String(300), nullable=True)
    is_active   = Column(Boolean, default=True, nullable=False)
    sort_order  = Column(Integer, default=0, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
