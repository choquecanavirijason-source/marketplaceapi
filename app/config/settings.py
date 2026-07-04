from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./marketplace.db"
    salon_backend_url: str = "http://localhost:8000"
    media_base_path: str = "./media"
    allowed_origins: str = "http://localhost:3000,http://localhost:8080,http://34.55.150.142,https://34.55.150.142"
    secret_key: str = "marketplace-secret-key-change-in-production"
    token_expire_minutes: int = 10080  # 7 días

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
