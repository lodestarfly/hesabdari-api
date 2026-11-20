"""
اسکریپت ایجاد کاربر ادمین
اجرا: python create_admin.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User


def create_admin(
    username: str = "admin",
    password: str = "admin123",
    full_name: str = "System Administrator",
    email: str = "admin@accounting.com",
    role: str = "admin",
):
    db = SessionLocal()
    try:
        # بررسی وجود کاربر
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"⚠️  کاربر '{username}' از قبل وجود دارد")
            print(f"   شناسه: {existing.id}")
            print(f"   نام: {existing.full_name}")
            print(f"   نقش: {existing.role}")
            return

        # ایجاد کاربر جدید
        admin = User(
            username=username,
            password_hash=get_password_hash(password),
            full_name=full_name,
            email=email,
            role=role,
            is_active=True,
            is_superuser=True,
            is_deleted=0,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("=" * 60)
        print("✅ کاربر ادمین با موفقیت ایجاد شد")
        print("=" * 60)
        print(f"   نام کاربری: {username}")
        print(f"   رمز عبور:   {password}")
        print(f"   نام کامل:   {full_name}")
        print(f"   ایمیل:      {email}")
        print(f"   نقش:        {role}")
        print("=" * 60)
        print("⚠️  لطفاً بعد از اولین ورود، رمز عبور را تغییر دهید!")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"❌ خطا: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
