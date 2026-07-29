from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.entities.presence import Presence

router = APIRouter(prefix="/presence", tags=["Presencia"])

# Ventana de "activo ahora": sin heartbeat en este lapso, ya no cuenta.
_ACTIVE_WINDOW = timedelta(minutes=2)
# Limpieza oportunista de sesiones viejas (evita que la tabla crezca sin fin).
_STALE_AFTER = timedelta(days=1)


class PingIn(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)


@router.post("/ping")
def ping(body: PingIn, db: Session = Depends(get_db)):
    """Heartbeat: upsert de la sesión con last_seen=ahora. Sin auth — cuenta
    tanto visitantes anónimos como logueados, igual que el widget que
    reemplaza (mostraba avatares falsos sin distinguir cuentas)."""
    now = datetime.utcnow()
    row = db.query(Presence).filter(Presence.session_key == body.session_id).first()
    if row:
        row.last_seen = now
    else:
        db.add(Presence(session_key=body.session_id, last_seen=now))
    db.commit()

    # Limpieza oportunista, sin cron aparte: barata porque solo corre en
    # este endpoint de baja frecuencia por sesión (cada ~30-60s por cliente).
    cutoff = now - _STALE_AFTER
    db.query(Presence).filter(Presence.last_seen < cutoff).delete()
    db.commit()
    return {"ok": True}


@router.get("/active-count")
def active_count(db: Session = Depends(get_db)):
    cutoff = datetime.utcnow() - _ACTIVE_WINDOW
    count = db.query(Presence).filter(Presence.last_seen >= cutoff).count()
    return {"count": count}
