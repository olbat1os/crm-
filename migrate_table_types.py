#!/usr/bin/env python3
"""
Migration for adding table_types field to business table
"""

import sqlite3
import sys
from pathlib import Path

def migrate():
    """Adds table_types column to business table"""
    
    db_path = Path("app.db")
    
    if not db_path.exists():
        print(f"[ERROR] Database {db_path} not found!")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(business)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'table_types' in columns:
            print("[OK] Column table_types already exists")
            conn.close()
            return True
        
        # Add column
        print("[INFO] Adding column table_types...")
        cursor.execute("""
            ALTER TABLE business 
            ADD COLUMN table_types TEXT
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
    print("[INFO] Starting migration for table_types...")
    success = migrate()
    if success:
        print("[OK] Migration completed successfully!")
    else:
        print("[ERROR] Migration failed!")
        sys.exit(1)







