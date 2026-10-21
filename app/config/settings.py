from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://marketplace:marketplace@postgres:5432/marketplace"
    salon_backend_url: str = "http://localhost:8000"
    media_base_path: str = "./media"
    allowed_origins: str = "*"
    secret_key: str = "marketplace-secret-key-change-in-production"
    token_expire_minutes: int = 10080  # 7 días
    # Interruptor temporal para probar en producción qué tanto pesa realmente
    # la recompresión vs. la red/latencia — con esto en true, los reels se
    # suben tal cual (solo faststart, sin recodificar). Se activa/desactiva
    # con la variable de entorno del mismo nombre, sin tocar código.
    skip_reel_compression: bool = False
    # MinIO (fotos de perfil). minio_public_url es la URL que el teléfono usa
    # para descargar los objetos (host/IP alcanzable desde fuera de Docker).
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_avatars_bucket: str = "avatars"
    minio_public_url: str = "http://localhost:9000"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
