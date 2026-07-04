from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import relationship
from app.infrastructure.database import Base


class Order(Base):
    __tablename__ = "mp_orders"

    id             = Column(Integer, primary_key=True, index=True)
    order_code     = Column(String(20), unique=True, index=True, nullable=False)
    customer_name  = Column(String(150), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_email = Column(String(150), nullable=True)
    total          = Column(Float, nullable=False)
    status         = Column(String(30), default="pending", nullable=False)
    notes                = Column(Text, nullable=True)
    delivery_address     = Column(Text, nullable=True)
    delivery_district    = Column(String(100), nullable=True)
    delivery_references  = Column(Text, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
