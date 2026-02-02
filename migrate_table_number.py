#!/usr/bin/env python3
"""
Миграция для добавления поля table_number в таблицу booking
"""

import sqlite3
import os
from pathlib import Path

def migrate_table_number():
    """Добавляет поле table_number в таблицу booking"""
    
    # Путь к базе данных - проверяем оба возможных пути
    db_paths = [Path("app.db"), Path("crm.db")]
    db_path = None
    
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        print("Ошибка: База данных не найдена (проверены app.db и crm.db)")
        return False
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже поле table_number
        cursor.execute("PRAGMA table_info(booking)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'table_number' in columns:
            print("Поле table_number уже существует в таблице booking")
            conn.close()
            return True
        
        # Добавляем поле table_number
        print("Добавляем поле table_number в таблицу booking...")
        cursor.execute("ALTER TABLE booking ADD COLUMN table_number TEXT")
        
        conn.commit()
        conn.close()
        
        print("Миграция успешно завершена")
        return True
        
    except Exception as e:
        print(f"Ошибка миграции: {e}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    print("Запуск миграции table_number...")
    success = migrate_table_number()
    if success:
        print("Миграция завершена успешно!")
    else:
        print("Миграция завершилась с ошибками!")
        exit(1)
