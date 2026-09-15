from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.infrastructure.database import Base


class Review(Base):
    """Reseña de un cliente sobre un producto, solo permitida tras una compra
    confirmada (no cancelada) de ese producto."""
    __tablename__ = "mp_reviews"

    id            = Column(Integer, primary_key=True, index=True)
    product_id    = Column(Integer, ForeignKey("mp_products.id", ondelete="CASCADE"), nullable=False)
    customer_id   = Column(Integer, ForeignKey("mp_customers.id", ondelete="SET NULL"), nullable=True)
    customer_name = Column(String(150), nullable=False)
    rating        = Column(Integer, nullable=False)  # 1 a 5
    comment       = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", backref="reviews")
