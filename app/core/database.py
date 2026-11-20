from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# ایجاد engine برای MySQL
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,          # بررسی اتصال قبل از هر query
    pool_size=10,                # تعداد اتصال‌های باز
    max_overflow=20,             # حداکثر اتصال اضافی
    echo=settings.DEBUG,         # نمایش queryها در حالت debug
    pool_recycle=3600,           # بازسازی اتصال هر 1 ساعت
    connect_args={
        "charset": "utf8mb4",
        "collation": "utf8mb4_persian_ci"  # برای مرتب‌سازی فارسی
    }
)

# فعال‌سازی Foreign Key در MySQL (به صورت پیش‌فرض غیرفعال است!)
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency برای دریافت session دیتابیس"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()