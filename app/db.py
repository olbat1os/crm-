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
    
    # Миграция: добавляем новые колонки в таблицу reactivationlist, если их нет
    with Session(engine) as session:
        try:
            # Проверяем и добавляем новые колонки для ReactivationList
            from sqlalchemy import text, inspect
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('reactivationlist')]
            
            new_columns = [
                ('status', 'TEXT'),
                ('filter_last_visit_date', 'DATE'),
                ('filter_visits_count_min', 'INTEGER'),
                ('filter_visits_count_max', 'INTEGER'),
                ('filter_max_spend_min', 'REAL'),
                ('filter_max_spend_max', 'REAL'),
                ('filter_last_offer_from_days', 'INTEGER'),
                ('filter_last_offer_to_days', 'INTEGER'),
                ('filter_guests_count', 'INTEGER'),
            ]
            
            for col_name, col_type in new_columns:
                if col_name not in columns:
                    try:
                        session.execute(text(f'ALTER TABLE reactivationlist ADD COLUMN {col_name} {col_type}'))
                        session.commit()
                        print(f"✅ Added column {col_name} to reactivationlist")
                    except Exception as e:
                        print(f"⚠️ Error adding column {col_name}: {e}")
                        session.rollback()
            
            # Проверяем и добавляем колонку status в таблицу reactivationoffer
            try:
                offer_columns = [col['name'] for col in inspector.get_columns('reactivationoffer')]
                if 'status' not in offer_columns:
                    session.execute(text('ALTER TABLE reactivationoffer ADD COLUMN status TEXT'))
                    session.commit()
                    print(f"✅ Added column status to reactivationoffer")
                if 'comment' not in offer_columns:
                    session.execute(text('ALTER TABLE reactivationoffer ADD COLUMN comment TEXT'))
                    session.commit()
                    print(f"✅ Added column comment to reactivationoffer")
            except Exception as e:
                print(f"⚠️ Error adding status column to reactivationoffer: {e}")
                session.rollback()
        except Exception as e:
            print(f"⚠️ Migration check failed: {e}")
            session.rollback()
    
    # Создаем дефолтных админов после создания таблиц
    from app.auth import create_default_admins
    with Session(engine) as session:
        create_default_admins(session)


def get_session():
    with Session(engine) as session:
        yield session


