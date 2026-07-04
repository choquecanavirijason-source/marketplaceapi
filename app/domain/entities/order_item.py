from sqlalchemy import Column, Integer, Float, ForeignKey, String
from sqlalchemy.orm import relationship
from app.infrastructure.database import Base


class OrderItem(Base):
    __tablename__ = "mp_order_items"

    id            = Column(Integer, primary_key=True, index=True)
    order_id      = Column(Integer, ForeignKey("mp_orders.id", ondelete="CASCADE"), nullable=False)
    product_id    = Column(Integer, nullable=True)   # NULL para productos del inventario del salón
    product_name  = Column(String(150), nullable=False)   # snapshot al momento del pedido
    product_image = Column(String(500), nullable=True)
    quantity      = Column(Integer, nullable=False, default=1)
    unit_price    = Column(Float, nullable=False)
    subtotal      = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
