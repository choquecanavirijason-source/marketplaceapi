from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./marketplace.db"
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

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
