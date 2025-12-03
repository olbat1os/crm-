#!/usr/bin/env python3
"""Миграция: добавление колонки dashboard_config в таблицу business"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path("app.db")

def migrate():
    """Добавляет колонку dashboard_config в таблицу business"""
    
    if not DB_PATH.exists():
        print(f"❌ База данных {DB_PATH} не найдена!")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Проверяем, существует ли колонка
        cursor.execute("PRAGMA table_info(business)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'dashboard_config' in columns:
            print("✅ Колонка dashboard_config уже существует")
            conn.close()
            return True
        
        # Добавляем колонку
        print("🔄 Добавление колонки dashboard_config...")
        cursor.execute("""
            ALTER TABLE business 
            ADD COLUMN dashboard_config TEXT
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
    print("🚀 Запуск миграции dashboard_config...")
    success = migrate()
    if success:
        print("✅ Миграция завершена успешно!")
    else:
        print("❌ Миграция завершилась с ошибками!")
        exit(1)


"""Миграция: добавление колонки dashboard_config в таблицу business"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path("app.db")

def migrate():
    """Добавляет колонку dashboard_config в таблицу business"""
    
    if not DB_PATH.exists():
        print(f"❌ База данных {DB_PATH} не найдена!")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Проверяем, существует ли колонка
        cursor.execute("PRAGMA table_info(business)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'dashboard_config' in columns:
            print("✅ Колонка dashboard_config уже существует")
            conn.close()
            return True
        
        # Добавляем колонку
        print("🔄 Добавление колонки dashboard_config...")
        cursor.execute("""
            ALTER TABLE business 
            ADD COLUMN dashboard_config TEXT
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
    print("🚀 Запуск миграции dashboard_config...")
    success = migrate()
    if success:
        print("✅ Миграция завершена успешно!")
    else:
        print("❌ Миграция завершилась с ошибками!")
        exit(1)






