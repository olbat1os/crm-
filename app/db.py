from __future__ import annotations

from typing import Optional

from sqlmodel import SQLModel, create_engine, Session
from app.config import settings


def get_engine_url() -> str:
    # По умолчанию локальная SQLite для разработки; можно задать PostgreSQL через env
    return settings.database_url or "sqlite:///./app.db"


engine = create_engine(get_engine_url(), echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    
    # Создаем дефолтных админов после создания таблиц
    from app.auth import create_default_admins
    with Session(engine) as session:
        create_default_admins(session)


def get_session():
    with Session(engine) as session:
        yield session


