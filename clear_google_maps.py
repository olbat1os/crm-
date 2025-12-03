"""
Скрипт для очистки данных Google Maps у всех бизнесов
"""
from sqlmodel import Session, select
from app.db import engine
from app.models import Business
from datetime import datetime

def clear_google_maps_data():
    """Очищает все данные Google Maps у всех бизнесов"""
    with Session(engine) as session:
        # Получаем все бизнесы
        businesses = session.exec(select(Business)).all()
        
        updated_count = 0
        for business in businesses:
            has_data = False
            
            # Проверяем, есть ли данные Google Maps
            if business.google_maps_url:
                business.google_maps_url = None
                has_data = True
                print(f"  - Udalen google_maps_url dlya: {business.business_name}")
            
            if business.google_rating is not None:
                business.google_rating = None
                has_data = True
                print(f"  - Udalen google_rating ({business.google_rating}) dlya: {business.business_name}")
            
            if business.google_rating_history:
                business.google_rating_history = None
                has_data = True
                print(f"  - Udalena google_rating_history dlya: {business.business_name}")
            
            if has_data:
                business.updated_at = datetime.utcnow()
                session.add(business)
                updated_count += 1
        
        # Сохраняем изменения
        session.commit()
        
        print(f"\n[OK] Ochishcheno dannyh Google Maps u {updated_count} biznesov iz {len(businesses)}")
        return updated_count

if __name__ == "__main__":
    print("Nachinayu ochistku dannyh Google Maps...")
    print("=" * 50)
    try:
        count = clear_google_maps_data()
        print("=" * 50)
        print(f"[OK] Ochistka zavershena uspeshno!")
    except Exception as e:
        print(f"[ERROR] Oshibka pri ochistke: {e}")
        import traceback
        traceback.print_exc()

