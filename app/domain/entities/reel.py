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
    # Procesamiento del video en segundo plano (ver app/core/reel_processing.py):
    # "ready" | "processing" | "failed". Mientras procesa, video_url es el
    # video anterior (al reemplazarlo) o "" (reel nuevo, oculto en la app).
    processing_status = Column(String(20), default="ready", nullable=False)
    processing_error  = Column(String(300), nullable=True)
    # Id del procesamiento vigente: si el admin sube otro video antes de que
    # termine el anterior, el resultado del viejo se descarta.
    processing_job    = Column(String(40), nullable=True)
    # Versión liviana del video para datos móviles (media.REEL_SD_NAME). None
    # en reels viejos o links externos: la app usa video_url.
    video_sd_url      = Column(String(500), nullable=True)

    product = relationship("Product", lazy="joined")
