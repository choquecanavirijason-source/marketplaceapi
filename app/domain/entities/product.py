from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.infrastructure.database import Base


class Product(Base):
    __tablename__ = "mp_products"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(150), nullable=False)
    brand          = Column(String(100), nullable=True)
    description    = Column(Text, nullable=True)
    price          = Column(Float, nullable=False, default=0.0)
    original_price = Column(Float, nullable=True)
    image_url      = Column(String(500), nullable=True)
    category_id    = Column(Integer, ForeignKey("mp_categories.id"), nullable=True)
    stock               = Column(Integer, default=0, nullable=False)
    low_stock_threshold = Column(Integer, default=5, nullable=False)
    video_url           = Column(String(500), nullable=True)
    rating              = Column(Float, default=0.0, nullable=True)
    review_count        = Column(Integer, default=0, nullable=True)
    is_active           = Column(Boolean, default=True, nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    category = relationship("Category", backref="products")
