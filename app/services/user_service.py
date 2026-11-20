# app/services/user_service.py
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.user import UserCreate, UserUpdate
from app.services.audit_service import AuditService


class UserService:
    
    @staticmethod
    def get_users(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> dict:
        """دریافت لیست کاربران با قابلیت فیلتر و جستجو"""
        query = db.query(User).filter(User.is_deleted == 0)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_pattern),
                    User.full_name.ilike(search_pattern),
                    User.email.ilike(search_pattern)
                )
            )
        
        if role:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        total = query.count()
        users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
        
        return {"total": total, "users": users}
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """دریافت کاربر بر اساس ID"""
        user = db.query(User).filter(User.id == user_id, User.is_deleted == 0).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate, admin_id: int, ip: str = None, ua: str = None) -> User:
        """ایجاد کاربر جدید توسط ادمین"""
        # بررسی تکراری نبودن
        existing = db.query(User).filter(
            (User.username == user_data.username) | 
            (User.email == user_data.email if user_data.email else False)
        ).filter(User.is_deleted == 0).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Username or Email already exists")
        
        new_user = User(
            username=user_data.username,
            password_hash=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            email=user_data.email,
            phone=user_data.phone,
            role=user_data.role,
            is_active=True,
            is_superuser=(user_data.role == 'admin'),
            created_by=admin_id
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=admin_id,
            action="create",
            table_name="users",
            record_id=new_user.id,
            new_values={
                "username": new_user.username,
                "full_name": new_user.full_name,
                "role": new_user.role,
                "email": new_user.email
            },
            ip_address=ip,
            user_agent=ua
        )
        
        return new_user
    
    @staticmethod
    def update_user(
        db: Session, 
        user_id: int, 
        user_data: UserUpdate, 
        admin_id: int,
        ip: str = None,
        ua: str = None
    ) -> User:
        """ویرایش اطلاعات کاربر"""
        user = UserService.get_user_by_id(db, user_id)
        
        # جلوگیری از تغییر نقش ادمین اصلی توسط دیگران
        if user.is_superuser and user.id != admin_id:
            raise HTTPException(status_code=403, detail="Cannot modify superadmin user")
        
        # ذخیره مقادیر قدیمی برای لاگ
        old_values = {
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "is_active": user.is_active
        }
        
        update_data = user_data.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(user, key, value)
        
        user.updated_by = admin_id
        db.commit()
        db.refresh(user)
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=admin_id,
            action="update",
            table_name="users",
            record_id=user_id,
            old_values=old_values,
            new_values={k: getattr(user, k) for k in update_data.keys()},
            ip_address=ip,
            user_agent=ua
        )
        
        return user
    
    @staticmethod
    def change_password(
        db: Session,
        user_id: int,
        current_password: str,
        new_password: str,
        admin_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """تغییر رمز عبور کاربر"""
        user = UserService.get_user_by_id(db, user_id)
        
        # بررسی رمز فعلی
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # ذخیره در لاگ (بدون ذخیره رمز!)
        AuditService.log_action(
            db=db,
            user_id=admin_id,
            action="update",
            table_name="users",
            record_id=user_id,
            old_values={"password": "***"},
            new_values={"password": "*** (changed)"},
            ip_address=ip,
            user_agent=ua
        )
        
        user.password_hash = get_password_hash(new_password)
        user.updated_by = admin_id
        db.commit()
        
        return {"message": "Password changed successfully"}
    
    @staticmethod
    def toggle_user_status(db: Session, user_id: int, admin_id: int, ip: str = None, ua: str = None) -> User:
        """فعال/غیرفعال کردن کاربر"""
        user = UserService.get_user_by_id(db, user_id)
        
        # جلوگیری از غیرفعال کردن خود ادمین
        if user.id == admin_id:
            raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
        
        # جلوگیری از تغییر وضعیت سوپرادمین
        if user.is_superuser and user.id != admin_id:
            raise HTTPException(status_code=403, detail="Cannot modify superadmin status")
        
        old_status = user.is_active
        user.is_active = not user.is_active
        user.updated_by = admin_id
        db.commit()
        db.refresh(user)
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=admin_id,
            action="update",
            table_name="users",
            record_id=user_id,
            old_values={"is_active": old_status},
            new_values={"is_active": user.is_active},
            ip_address=ip,
            user_agent=ua
        )
        
        return user
    
    @staticmethod
    def delete_user(db: Session, user_id: int, admin_id: int, ip: str = None, ua: str = None) -> dict:
        """حذف نرم (Soft Delete) کاربر"""
        user = UserService.get_user_by_id(db, user_id)
        
        if user.id == admin_id:
            raise HTTPException(status_code=400, detail="Cannot delete yourself")
        
        if user.is_superuser:
            raise HTTPException(status_code=403, detail="Cannot delete superadmin user")
        
        user.is_deleted = 1
        user.is_active = False
        user.updated_by = admin_id
        db.commit()
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=admin_id,
            action="delete",
            table_name="users",
            record_id=user_id,
            old_values={"username": user.username, "full_name": user.full_name},
            ip_address=ip,
            user_agent=ua
        )
        
        return {"message": "User deleted successfully"}