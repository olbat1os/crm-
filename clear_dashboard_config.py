"""
Script to clean dashboard config from rejting_google metric
"""
from sqlmodel import Session, select
from app.db import engine
from app.models import Business
from datetime import datetime
import json

def clear_dashboard_config():
    """Clears rejting_google from dashboard config for all businesses"""
    with Session(engine) as session:
        businesses = session.exec(select(Business)).all()
        
        updated_count = 0
        for business in businesses:
            if business.dashboard_config:
                config = business.dashboard_config
                if isinstance(config, dict) and "metrics" in config:
                    if isinstance(config["metrics"], list):
                        original_count = len(config["metrics"])
                        config["metrics"] = [m for m in config["metrics"] if m != "rejting_google"]
                        if len(config["metrics"]) != original_count:
                            business.dashboard_config = config
                            business.updated_at = datetime.utcnow()
                            session.add(business)
                            updated_count += 1
                            print(f"  - Updated config for: {business.business_name} (removed rejting_google)")
        
        session.commit()
        
        print(f"\n[OK] Updated dashboard config for {updated_count} businesses")
        return updated_count

if __name__ == "__main__":
    print("Cleaning dashboard config...")
    print("=" * 50)
    try:
        count = clear_dashboard_config()
        print("=" * 50)
        print(f"[OK] Cleaning completed!")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()

