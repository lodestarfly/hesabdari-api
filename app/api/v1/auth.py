# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.user import UserCreate, LoginRequest, Token, UserResponse
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.utils.request_utils import get_client_ip, get_user_agent

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user: UserCreate, 
    db: Session = Depends(get_db),
    request: Request = None
):
    """ثبت نام کاربر جدید"""
    # ثبت کاربر
    new_user = AuthService.register_user(db, user)
    
    # ثبت لاگ
    AuditService.log_action(
        db=db,
        user_id=new_user.id,
        action="create",
        table_name="users",
        record_id=new_user.id,
        new_values={"username": new_user.username, "role": new_user.role},
        ip_address=get_client_ip(request) if request else None,
        user_agent=get_user_agent(request) if request else None
    )
    
    return new_user

@router.post("/login", response_model=Token)
def login(
    user_credentials: LoginRequest, 
    db: Session = Depends(get_db),
    request: Request = None
):
    """ورود کاربر و دریافت توکن"""
    user = AuthService.authenticate_user(db, user_credentials.username, user_credentials.password)
    token_data = AuthService.create_login_token(user)
    
    # ثبت لاگ ورود موفق
    AuditService.log_action(
        db=db,
        user_id=user.id,
        action="login",
        table_name="users",
        record_id=user.id,
        new_values={"username": user.username},
        ip_address=get_client_ip(request) if request else None,
        user_agent=get_user_agent(request) if request else None
    )
    
    return token_data