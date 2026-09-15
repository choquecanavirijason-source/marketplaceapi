from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from app.infrastructure.database import Base


class ReelLike(Base):
    """Like a un reel en sí (el video), independiente de si el producto que
    aparece en él está marcado como favorito — ver mp_favorites."""
    __tablename__ = "mp_reel_likes"
    __table_args__ = (UniqueConstraint("customer_id", "reel_id", name="uq_reel_like_customer_reel"),)

    id          = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("mp_customers.id"), nullable=False, index=True)
    reel_id     = Column(Integer, ForeignKey("mp_reels.id"), nullable=False, index=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
