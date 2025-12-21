#!/usr/bin/env python3
"""
Миграция для добавления поля default_booking_time в таблицу business
"""

import sqlite3
import sys
from pathlib import Path

def migrate():
    """Добавляет колонку default_booking_time в таблицу business"""
    
    # Путь к базе данных
    db_path = Path("app.db")
    
    if not db_path.exists():
        print(f"❌ База данных {db_path} не найдена!")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Проверяем, существует ли колонка
        cursor.execute("PRAGMA table_info(business)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'default_booking_time' in columns:
            print("[OK] Column default_booking_time already exists")
            conn.close()
            return True
        
        # Добавляем колонку
        print("[INFO] Adding column default_booking_time...")
        cursor.execute("""
            ALTER TABLE business 
            ADD COLUMN default_booking_time TIME
        """)
        
        conn.commit()
        conn.close()
        
        print("[OK] Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Migration error: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    print("[INFO] Starting migration for default_booking_time...")
    success = migrate()
    if success:
        print("[OK] Migration completed successfully!")
    else:
        print("[ERROR] Migration failed!")
        sys.exit(1)

