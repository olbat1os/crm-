#!/usr/bin/env python3
"""
Миграция для добавления полей email и role в таблицу promoter
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path("app.db")

def migrate():
    """Добавляет колонки email и role в таблицу promoter"""
    
    if not DB_PATH.exists():
        print(f"❌ База данных {DB_PATH} не найдена!")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Проверяем, существуют ли колонки
        cursor.execute("PRAGMA table_info(promoter)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Добавляем email, если его нет
        if 'email' not in columns:
            print("🔄 Добавление колонки email...")
            cursor.execute("ALTER TABLE promoter ADD COLUMN email TEXT")
            print("✅ Колонка email добавлена")
        else:
            print("ℹ️ Колонка email уже существует")
        
        # Добавляем role, если его нет
        if 'role' not in columns:
            print("🔄 Добавление колонки role...")
            cursor.execute("ALTER TABLE promoter ADD COLUMN role TEXT DEFAULT 'Employee'")
            print("✅ Колонка role добавлена")
        else:
            print("ℹ️ Колонка role уже существует")
        
        conn.commit()
        conn.close()
        
        print("✅ Миграция успешно выполнена!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при миграции: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    migrate()


