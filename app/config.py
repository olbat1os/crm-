from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    app_name: str = "CRM MVP"
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    session_cookie_name: str = os.getenv("SESSION_COOKIE_NAME", "crm_session")
    session_max_age: int = int(os.getenv("SESSION_MAX_AGE", "86400"))  # 24 часа для обычных пользователей
    admin_session_max_age: int = int(os.getenv("ADMIN_SESSION_MAX_AGE", "43200"))  # 12 часов для админки
    
    # Старые настройки для обратной совместимости
    single_username: str = os.getenv("APP_USERNAME", "admin")
    single_password: str = os.getenv("APP_PASSWORD", "admin123")
    
    # Email настройки
    admin_email: str = os.getenv("ADMIN_EMAIL", "lovacrmhelp@gmail.com")
    
    # Настройки для админов
    super_admin_username: str = os.getenv("SUPER_ADMIN_USERNAME", "superadmin")
    super_admin_password: str = os.getenv("SUPER_ADMIN_PASSWORD", "superadmin123")
    super_admin_email: str = os.getenv("SUPER_ADMIN_EMAIL", "superadmin@lovacrm.com")
    
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")
    admin_email: str = os.getenv("ADMIN_EMAIL", "admin@lovacrm.com")
    
    locale: str = os.getenv("LOCALE", "sr")
    timezone: str = os.getenv("TIMEZONE", "Europe/Belgrade")
    database_url: Optional[str] = os.getenv("DATABASE_URL", "sqlite:///app.db")

settings = Settings()
