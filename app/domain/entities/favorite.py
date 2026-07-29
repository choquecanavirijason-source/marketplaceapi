from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from app.infrastructure.database import Base


class Favorite(Base):
    __tablename__ = "mp_favorites"
    __table_args__ = (UniqueConstraint("customer_id", "product_id", name="uq_favorite_customer_product"),)

    id          = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("mp_customers.id"), nullable=False, index=True)
    product_id  = Column(Integer, ForeignKey("mp_products.id"), nullable=False, index=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
