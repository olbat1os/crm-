from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    app_name: str = "CRM MVP"
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    session_cookie_name: str = os.getenv("SESSION_COOKIE_NAME", "crm_session")
    single_username: str = os.getenv("APP_USERNAME", "admin")
    single_password: str = os.getenv("APP_PASSWORD", "admin123")
    locale: str = os.getenv("LOCALE", "sr")
    timezone: str = os.getenv("TIMEZONE", "Europe/Belgrade")
    database_url: Optional[str] = os.getenv("DATABASE_URL", "sqlite:///app.db")

settings = Settings()
