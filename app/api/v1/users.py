import os
import uuid
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_active_superuser, get_current_user
from app.models.user import User
from app.schemas.user import (ChangePasswordRequest, UserCreate,
                              UserListResponse, UserResponse, UserUpdate)
from app.services.user_service import UserService
from app.utils.request_utils import get_client_ip, get_user_agent
from fastapi import (APIRouter, Depends, File, Form, Query, Request,
                     UploadFile, status)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/users", tags=["Users Management"])


# ==================== پروفایل کاربر فعلی ====================

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """دریافت پروفایل کاربر فعلی (همه کاربران)"""
    return current_user


@router.put("/me")
def update_current_user_profile(
    full_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    به‌روزرسانی پروفایل کاربر فعلی
    - پشتیبانی از FormData (برای آپلود آواتار)
    - فیلدهای اختیاری: full_name, email, phone, avatar
    """
    # به‌روزرسانی فیلدهای متنی
    if full_name is not None:
        current_user.full_name = full_name
    if email is not None:
        current_user.email = email
    if phone is not None:
        current_user.phone = phone

    # آپلود آواتار (اختیاری)
    if avatar and avatar.filename:
        from app.core.config import settings

        ext = os.path.splitext(avatar.filename)[1].lower()
        allowed_ext = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        if ext not in allowed_ext:
            raise HTTPException(
                status_code=400,
                detail=f"فرمت فایل نامعتبر است. فرمت‌های مجاز: {', '.join(allowed_ext)}"
            )

        if avatar.size and avatar.size > 2 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="حجم آواتار نباید بیشتر از 2 مگابایت باشد"
            )

        filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
        upload_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            content = avatar.file.read()
            f.write(content)

        current_user.avatar_url = f"avatars/{filename}"

    current_user.updated_by = current_user.id
    db.commit()
    db.refresh(current_user)

    # ثبت لاگ
    try:
        from app.services.audit_service import AuditService
        AuditService.log_action(
            db=db,
            user_id=current_user.id,
            action="update",
            table_name="users",
            record_id=current_user.id,
            new_values='{"profile": "updated"}',
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
        )
    except Exception:
        pass  # لاگ اختیاری است

    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "avatar_url": getattr(current_user, "avatar_url", None),
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
    }


@router.put("/me/password")
def change_my_password(
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """تغییر رمز عبور توسط کاربر فعلی"""
    return UserService.change_password(
        db=db,
        user_id=current_user.id,
        current_password=password_data.current_password,
        new_password=password_data.new_password,
        admin_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )


# ==================== مدیریت کاربران (فقط ادمین) ====================

@router.get("/", response_model=UserListResponse)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=1),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser)
):
    """دریافت لیست کاربران با فیلتر و جستجو (فقط ادمین)"""
    return UserService.get_users(
        db=db,
        skip=skip,
        limit=limit,
        search=search,
        role=role,
        is_active=is_active
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser)
):
    """دریافت جزئیات یک کاربر (فقط ادمین)"""
    return UserService.get_user_by_id(db, user_id)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """ایجاد کاربر جدید (فقط ادمین)"""
    return UserService.create_user(
        db=db,
        user_data=user_data,
        admin_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """ویرایش اطلاعات کاربر (فقط ادمین)"""
    return UserService.update_user(
        db=db,
        user_id=user_id,
        user_data=user_data,
        admin_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )


@router.put("/{user_id}/toggle-status", response_model=UserResponse)
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """فعال/غیرفعال کردن کاربر (فقط ادمین)"""
    return UserService.toggle_user_status(
        db=db,
        user_id=user_id,
        admin_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )


@router.put("/{user_id}/change-password")
def admin_change_user_password(
    user_id: int,
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """تغییر رمز عبور کاربر توسط ادمین"""
    return UserService.change_password(
        db=db,
        user_id=user_id,
        current_password=password_data.current_password,
        new_password=password_data.new_password,
        admin_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """حذف کاربر (Soft Delete - فقط ادمین)"""
    UserService.delete_user(
        db=db,
        user_id=user_id,
        admin_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )
