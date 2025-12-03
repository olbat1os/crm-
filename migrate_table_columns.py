#!/usr/bin/env python3
"""Миграция: добавление колонки table_columns в таблицу business"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path("app.db")

def migrate():
    """Добавляет колонку table_columns в таблицу business"""
    
    if not DB_PATH.exists():
        print(f"❌ База данных {DB_PATH} не найдена!")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Проверяем, существует ли колонка
        cursor.execute("PRAGMA table_info(business)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'table_columns' in columns:
            print("✅ Колонка table_columns уже существует")
            conn.close()
            return True
        
        # Добавляем колонку
        print("🔄 Добавление колонки table_columns...")
        cursor.execute("""
            ALTER TABLE business 
            ADD COLUMN table_columns TEXT
        """)
        
        conn.commit()
        conn.close()
        
        print("✅ Миграция успешно выполнена!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при миграции: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    print("🔄 Запуск миграции для добавления колонки table_columns...")
    success = migrate()
    if success:
        print("✅ Миграция завершена успешно!")
    else:
        print("❌ Миграция завершилась с ошибками!")
        exit(1)

