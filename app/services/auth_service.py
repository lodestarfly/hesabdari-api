# app/services/auth_service.py
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.config import settings

class AuthService:
    
    @staticmethod
    def register_user(db: Session, user_data: UserCreate) -> User:
        # بررسی تکراری نبودن نام کاربری و ایمیل
        db_user = db.query(User).filter(
            (User.username == user_data.username) | (User.email == user_data.email)
        ).first()
        
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or Email already registered"
            )
        
        # ساخت کاربر جدید
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            username=user_data.username,
            password_hash=hashed_password,
            full_name=user_data.full_name,
            email=user_data.email,
            phone=user_data.phone,
            role=user_data.role,
            is_active=True,
            is_superuser=(user_data.role == 'admin') # اگر نقش ادمین بود، سوپریوزر هم باشد
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # TODO: اینجا باید لاگ ثبت شود (در مراحل بعد اضافه می‌کنیم)
        
        return db_user

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> User:
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not verify_password(password, user.password_hash):
            # افزایش تعداد تلاش‌های ناموفق (اختیاری برای امنیت بیشتر)
            user.failed_login_attempts += 1
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # ریست کردن تلاش‌های ناموفق و ثبت زمان آخرین ورود
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        return user

    @staticmethod
    def create_login_token(user: User) -> dict:
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role}, 
            expires_delta=access_token_expires
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user
        }