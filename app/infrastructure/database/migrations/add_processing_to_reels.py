"""Añade el estado de procesamiento del video a mp_reels.

El video de un reel se procesa en segundo plano (H.265 tarda minutos): el
reel se crea con processing_status="processing" y pasa a "ready" (o
"failed") al terminar. Los reels existentes quedan "ready".
"""
from sqlalchemy import text
from app.infrastructure.database.session import engine


def upgrade():
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE mp_reels ADD COLUMN IF NOT EXISTS processing_status VARCHAR(20) NOT NULL DEFAULT 'ready'"
        ))
        conn.execute(text("ALTER TABLE mp_reels ADD COLUMN IF NOT EXISTS processing_error VARCHAR(300)"))
        conn.execute(text("ALTER TABLE mp_reels ADD COLUMN IF NOT EXISTS processing_job VARCHAR(40)"))
        # Versión liviana del video para datos móviles (ver media.REEL_SD_NAME).
        conn.execute(text("ALTER TABLE mp_reels ADD COLUMN IF NOT EXISTS video_sd_url VARCHAR(500)"))
        # Un procesamiento en curso no sobrevive a un reinicio del servidor
        # (el archivo subido vivía en una carpeta temporal del contenedor):
        # se marca como fallido para que el admin vuelva a subir el video,
        # en vez de quedar "procesando" para siempre.
        conn.execute(text(
            "UPDATE mp_reels SET processing_status = 'failed', processing_job = NULL, "
            "processing_error = 'Se reinició el servidor mientras se procesaba: vuelve a subir el video.' "
            "WHERE processing_status = 'processing'"
        ))
    print("[OK] mp_reels: processing_status/processing_error/processing_job/video_sd_url")
