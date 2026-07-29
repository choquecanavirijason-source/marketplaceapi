from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.infrastructure.database import Base


class Presence(Base):
    """Heartbeat de sesiones activas en la app (con o sin cuenta) — usado para
    mostrar 'X explorando ahora' en Home con un dato real, no decorativo."""
    __tablename__ = "mp_presence"

    id          = Column(Integer, primary_key=True, index=True)
    session_key = Column(String(64), unique=True, nullable=False, index=True)
    last_seen   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
