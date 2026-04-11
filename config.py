import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Арбузный API для Паркингов"
    VERSION: str = "1.0.0"

    TRIP_EXPIRATION_MINUTES: int = 60

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./parking.db")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "remove-me-please")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    AUTH_COOKIE_SECURE: bool = (
        os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
    )

    PUSH_PROVIDER: str = os.getenv("PUSH_PROVIDER", "none")
    FIREBASE_CREDENTIALS: str | None = os.getenv("FIREBASE_CREDENTIALS")

    # Yandex SmartCaptcha: https://yandex.cloud/ru/docs/smartcaptcha/quickstart
    SMARTCAPTCHA_SITE_KEY: str | None = None
    SMARTCAPTCHA_SERVER_KEY: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
