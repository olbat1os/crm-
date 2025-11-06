#!/usr/bin/env python3
"""
Миграция для добавления поля business_id в таблицу booking
"""

import sqlite3
import os

def migrate_booking_business_id():
    """Добавляет поле business_id в таблицу booking"""
    
    # Путь к базе данных
    db_path = "crm.db"
    
    if not os.path.exists(db_path):
        print("❌ База данных не найдена")
        return False
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже поле business_id
        cursor.execute("PRAGMA table_info(booking)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'business_id' in columns:
            print("✅ Поле business_id уже существует в таблице booking")
            conn.close()
            return True
        
        # Добавляем поле business_id
        print("🔄 Добавляем поле business_id в таблицу booking...")
        cursor.execute("ALTER TABLE booking ADD COLUMN business_id INTEGER")
        
        # Обновляем существующие записи - устанавливаем business_id из contact
        print("🔄 Обновляем существующие записи...")
        cursor.execute("""
            UPDATE booking 
            SET business_id = (
                SELECT contact.business_id 
                FROM contact 
                WHERE contact.id = booking.contact_id
            )
        """)
        
        # Делаем поле NOT NULL
        print("🔄 Делаем поле business_id обязательным...")
        cursor.execute("""
            CREATE TABLE booking_new (
                id INTEGER PRIMARY KEY,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                contact_id INTEGER NOT NULL,
                business_id INTEGER NOT NULL,
                date DATE NOT NULL,
                time_from TIME NOT NULL,
                time_to TIME,
                end_date DATE,
                table_type VARCHAR,
                party_size INTEGER,
                booking_source VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'dogovoreno',
                spend_eur FLOAT,
                special_case_note TEXT,
                comment TEXT,
                FOREIGN KEY (contact_id) REFERENCES contact (id),
                FOREIGN KEY (business_id) REFERENCES business (id)
            )
        """)
        
        cursor.execute("""
            INSERT INTO booking_new 
            SELECT * FROM booking
        """)
        
        cursor.execute("DROP TABLE booking")
        cursor.execute("ALTER TABLE booking_new RENAME TO booking")
        
        # Создаем индексы
        cursor.execute("CREATE INDEX ix_booking_contact_id ON booking (contact_id)")
        cursor.execute("CREATE INDEX ix_booking_business_id ON booking (business_id)")
        cursor.execute("CREATE INDEX ix_booking_date ON booking (date)")
        
        conn.commit()
        conn.close()
        
        print("✅ Миграция успешно завершена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    migrate_booking_business_id()

