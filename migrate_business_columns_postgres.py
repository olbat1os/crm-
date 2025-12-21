#!/usr/bin/env python3
"""
Миграция: добавление недостающих колонок в таблицу business для PostgreSQL
Добавляет: lead_sources, table_types, working_schedule, dashboard_config, table_columns, google_maps_url, google_rating, google_rating_history
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# Получаем параметры подключения из переменных окружения
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "crm_db")
DB_USER = os.getenv("DB_USER", "crm_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "crm_password")

# Формируем строку подключения
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def check_column_exists(conn, table_name, column_name):
    """Проверяет существование колонки в таблице"""
    try:
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = :table_name AND column_name = :column_name
        """), {"table_name": table_name, "column_name": column_name})
        return result.fetchone() is not None
    except Exception as e:
        print(f"⚠️ Ошибка при проверке колонки {column_name}: {e}")
        return False

def add_column_if_not_exists(conn, table_name, column_name, column_type, default_value=None):
    """Добавляет колонку, если она не существует"""
    if check_column_exists(conn, table_name, column_name):
        print(f"ℹ️ Колонка {column_name} уже существует")
        return True
    
    try:
        if default_value is not None:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
        else:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        
        conn.execute(text(sql))
        conn.commit()
        print(f"✅ Добавлена колонка {column_name}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при добавлении колонки {column_name}: {e}")
        conn.rollback()
        return False

def migrate():
    """Выполняет миграцию"""
    try:
        print("🔄 Подключение к базе данных...")
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Начинаем транзакцию
            trans = conn.begin()
            
            try:
                # JSON колонки (TEXT в PostgreSQL, но SQLAlchemy будет работать с JSON)
                add_column_if_not_exists(conn, "business", "lead_sources", "TEXT")
                add_column_if_not_exists(conn, "business", "table_types", "TEXT")
                add_column_if_not_exists(conn, "business", "working_schedule", "TEXT")
                add_column_if_not_exists(conn, "business", "dashboard_config", "TEXT")
                add_column_if_not_exists(conn, "business", "table_columns", "TEXT")
                add_column_if_not_exists(conn, "business", "google_rating_history", "TEXT")
                
                # Обычные колонки
                add_column_if_not_exists(conn, "business", "google_maps_url", "TEXT")
                add_column_if_not_exists(conn, "business", "google_rating", "REAL")
                
                # Коммитим транзакцию
                trans.commit()
                print("✅ Миграция успешно выполнена!")
                return True
                
            except Exception as e:
                trans.rollback()
                raise e
                
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔄 Запуск миграции для добавления колонок в таблицу business...")
    print(f"📊 База данных: {DB_NAME} на {DB_HOST}:{DB_PORT}")
    success = migrate()
    if success:
        print("✅ Миграция завершена успешно!")
        sys.exit(0)
    else:
        print("❌ Миграция завершилась с ошибками!")
        sys.exit(1)











