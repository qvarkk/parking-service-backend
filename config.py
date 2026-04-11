import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Арбузный API для Паркингов"
    VERSION: str = "1.0.0"

    TRIP_EXPIRATION_MINUTES: int = 60
    PARKING_THRESHOLD_PERCENT: int = 15
    SCHEDULER_INTERVAL_SECONDS: int = 60

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./parking.db")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "remove-me-please")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    AUTH_COOKIE_SECURE: bool = (
        os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
    )

    PUSH_PROVIDER: str = os.getenv("PUSH_PROVIDER", "none")
    FIREBASE_CREDENTIALS: str | None = os.getenv("FIREBASE_CREDENTIALS")
    
    SMTP_TLS: bool = True
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_HOST: str | None = os.getenv("SMTP_HOST")
    SMTP_USER: str | None = os.getenv("SMTP_USER")
    SMTP_PASSWORD: str | None = os.getenv("SMTP_PASSWORD")
    EMAILS_FROM_EMAIL: str = os.getenv("EMAILS_FROM_EMAIL", "noreply@example.com")
    EMAILS_FROM_NAME: str = os.getenv("EMAILS_FROM_NAME", "Parking Admin")

    DASHBOARD_URL: str = os.getenv("DASHBOARD_URL", "http://localhost:3000")

    # Yandex SmartCaptcha: https://yandex.cloud/ru/docs/smartcaptcha/quickstart
    SMARTCAPTCHA_SITE_KEY: str | None = None
    SMARTCAPTCHA_SERVER_KEY: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
