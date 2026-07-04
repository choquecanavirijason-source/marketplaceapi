from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from app.infrastructure.database import Base


class Category(Base):
    __tablename__ = "mp_categories"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    image_url   = Column(String(500), nullable=True)
    is_active   = Column(Boolean, default=True, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
