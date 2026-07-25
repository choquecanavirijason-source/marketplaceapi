from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.infrastructure.database import Base


class DeliveryPoint(Base):
    """Punto fijo de recojo/entrega del marketplace, agrupado por país.
    Permite que el admin habilite distintos países (Perú, otros) con sus
    propios locales de recojo/entrega, y que el cliente vea solo los que
    corresponden al país que seleccionó."""
    __tablename__ = "mp_delivery_points"

    id           = Column(Integer, primary_key=True, index=True)
    country_code = Column(String(2), nullable=False, index=True)
    country_name = Column(String(80), nullable=False)
    city         = Column(String(100), nullable=True)
    name         = Column(String(150), nullable=False)
    address      = Column(String(300), nullable=False)
    reference    = Column(String(300), nullable=True)
    schedule     = Column(String(150), nullable=True)
    phone        = Column(String(30), nullable=True)
    is_active    = Column(Boolean, default=True, nullable=False)
    sort_order   = Column(Integer, default=0, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
