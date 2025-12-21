#!/usr/bin/env python3
"""
Миграция для добавления полей deposit и lead_source в таблицу booking
"""

import sqlite3
import os
import sys

def migrate_deposit_lead_source():
    """Добавляет колонки deposit и lead_source в таблицу booking"""
    
    # Путь к базе данных
    db_path = "app.db"
    
    if not os.path.exists(db_path):
        print(f"Ошибка: База данных {db_path} не найдена")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем, существуют ли уже колонки
        cursor.execute("PRAGMA table_info(booking)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Добавляем колонку deposit, если её нет
        if 'deposit' not in columns:
            print("Добавление колонки deposit...")
            cursor.execute("ALTER TABLE booking ADD COLUMN deposit REAL")
            print("Колонка deposit успешно добавлена")
        else:
            print("Колонка deposit уже существует")
        
        # Добавляем колонку lead_source, если её нет
        if 'lead_source' not in columns:
            print("Добавление колонки lead_source...")
            cursor.execute("ALTER TABLE booking ADD COLUMN lead_source TEXT")
            print("Колонка lead_source успешно добавлена")
        else:
            print("Колонка lead_source уже существует")
        
        conn.commit()
        conn.close()
        
        print("Миграция успешно завершена!")
        return True
        
    except Exception as e:
        print(f"Ошибка при выполнении миграции: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    success = migrate_deposit_lead_source()
    sys.exit(0 if success else 1)

