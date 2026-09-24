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
    media_public_base_url: str = "http://localhost:8003/media"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
