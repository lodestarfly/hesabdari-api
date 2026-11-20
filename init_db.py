from app.core.database import engine, Base
from app.models import *  # Import all models

def init_database():
    """ساخت تمام جداول در MySQL"""
    print("🔧 Creating database tables in MySQL...")
    
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ All tables created successfully!")
        
        # نمایش جداول ساخته شده
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result]
            print(f"\n📊 Tables created ({len(tables)}):")
            for table in tables:
                print(f"   - {table}")
                
    except Exception as e:
        print(f"❌ Error creating tables: {e}")

if __name__ == "__main__":
    init_database()