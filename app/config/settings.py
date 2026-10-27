from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://marketplace:marketplace@postgres:5432/marketplace"
    salon_backend_url: str = "http://host.docker.internal:8000"
    media_base_path: str = "./media"
    allowed_origins: str = "*"
    secret_key: str = "marketplace-secret-key-change-in-production"
    token_expire_minutes: int = 10080  # 7 días
    # Secreto server-to-server compartido con elashesbackend (mismo valor que
    # su INTERNAL_API_KEY). Se envía en X-Internal-Key al verificar logins con
    # CI y al registrar dispositivos. Vacío = no se registran dispositivos.
    internal_api_key: str = ""
    # Interruptor temporal para probar en producción qué tanto pesa realmente
    # la recompresión vs. la red/latencia — con esto en true, los reels se
    # suben tal cual (solo faststart, sin recodificar). Se activa/desactiva
    # con la variable de entorno del mismo nombre, sin tocar código.
    skip_reel_compression: bool = False

    # "local" = archivos en disco (media_base_path), "minio" = bucket S3
    # compatible. Por defecto "local" para que un servidor sin MinIO siga
    # funcionando igual hasta que se configure.
    storage_backend: str = "local"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "marketplace-media"
    minio_secure: bool = False
    # URL pública (la que ve el navegador/celular) que sirve el bucket en
    # lugar de "/media". Solo se usa con storage_backend="minio".
    media_public_base_url: str = "http://37.60.247.213:8003/media"

    # Storage específico para REELS (video + portada), aparte de
    # storage_backend: productos/categorías/anuncios/colecciones siguen
    # usando storage_backend sin cambios. "local"/"minio" (igual que
    # storage_backend) o "s3" (AWS). Vacío = los reels siguen storage_backend
    # como hasta ahora, para no romper nada hasta que se configure AWS acá.
    reels_storage_backend: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "sa-east-1"
    aws_bucket: str = ""
    # Lectura pública directa del bucket (sin CDN todavía). Si más adelante
    # se pone CloudFront delante, este valor pasa a ser la URL de esa
    # distribución y no hay que tocar nada más.
    aws_public_base_url: str = ""

    # Códec del MP4 de reels (ver REEL_RENDITIONS en app/core/media.py):
    # "hevc" = H.265 en 1080 con el peso del 720 en H.264; "h264" = 720,
    # máxima compatibilidad. Interruptor para volver a h264 sin tocar código
    # si algún celular no reproduce H.265. Solo afecta a reels subidos después.
    reels_video_codec: str = "hevc"
    # Filtro de nitidez suave después de escalar (casi sin costo de peso).
    reels_sharpen: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
