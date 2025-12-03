"""
Миграция для добавления полей Google Maps в таблицу business
"""
import sqlite3
import sys

def migrate():
    db_path = "app.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем существование колонок
        cursor.execute("PRAGMA table_info(business)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Добавляем google_maps_url, если его нет
        if 'google_maps_url' not in columns:
            cursor.execute("ALTER TABLE business ADD COLUMN google_maps_url TEXT")
            print("✅ Добавлена колонка google_maps_url")
        else:
            print("ℹ️ Колонка google_maps_url уже существует")
        
        # Добавляем google_rating, если его нет
        if 'google_rating' not in columns:
            cursor.execute("ALTER TABLE business ADD COLUMN google_rating REAL")
            print("✅ Добавлена колонка google_rating")
        else:
            print("ℹ️ Колонка google_rating уже существует")
        
        # Добавляем google_rating_history, если его нет
        if 'google_rating_history' not in columns:
            cursor.execute("ALTER TABLE business ADD COLUMN google_rating_history TEXT")
            print("✅ Добавлена колонка google_rating_history")
        else:
            print("ℹ️ Колонка google_rating_history уже существует")
        
        conn.commit()
        print("✅ Миграция успешно выполнена!")
        
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()


