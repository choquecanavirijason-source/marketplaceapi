from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.infrastructure.database import Base


class Collection(Base):
    __tablename__ = "mp_collections"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    image_url   = Column(String(500), nullable=True)
    is_active   = Column(Boolean, default=True, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)

    products = relationship("CollectionProduct", back_populates="collection", cascade="all, delete-orphan")


class CollectionProduct(Base):
    __tablename__ = "mp_collection_products"

    id            = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("mp_collections.id", ondelete="CASCADE"), nullable=False)
    product_id    = Column(Integer, ForeignKey("mp_products.id", ondelete="CASCADE"), nullable=False)

    collection = relationship("Collection", back_populates="products")
    product    = relationship("Product", lazy="joined")
