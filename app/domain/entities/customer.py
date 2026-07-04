from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.infrastructure.database import Base


class Customer(Base):
    __tablename__ = "mp_customers"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(150), nullable=False)
    phone         = Column(String(20), nullable=False, default="", index=True)
    email         = Column(String(150), nullable=False, unique=True, index=True)
    # La columna física se llama password_hash (esquema original de la tabla)
    hashed_pw     = Column("password_hash", String(255), nullable=True)
    is_active     = Column(Boolean, default=True, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    # 'app' = se registró directamente en la app | 'salon' = vino del salón vía CI
    source        = Column(String(20), nullable=False, default="app")
