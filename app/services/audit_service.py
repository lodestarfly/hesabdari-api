import json
from datetime import datetime
from typing import Any, Optional

from app.models.audit_log import AuditLog
from sqlalchemy.orm import Session


def _safe_str(value: Any) -> Optional[str]:
    """تبدیل امن هر مقداری به رشته برای ذخیره در TEXT"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


class AuditService:

    @staticmethod
    def log_action(
        db: Session,
        user_id: int,
        action: str,
        table_name: Optional[str] = None,
        record_id: Optional[int] = None,
        old_values: Any = None,
        new_values: Any = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """ثبت لاگ عملیات"""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_values=_safe_str(old_values),   # ✅ تبدیل امن
            new_values=_safe_str(new_values),   # ✅ تبدیل امن
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log

    @staticmethod
    def log_login(
        db: Session,
        user_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """ثبت لاگ ورود"""
        return AuditService.log_action(
            db=db,
            user_id=user_id,
            action="login",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def log_logout(
        db: Session,
        user_id: int,
    ) -> AuditLog:
        """ثبت لاگ خروج"""
        return AuditService.log_action(
            db=db,
            user_id=user_id,
            action="logout",
        )

    @staticmethod
    def log_create(
        db: Session,
        user_id: int,
        table_name: str,
        record_id: int,
        new_values: Any = None,
    ) -> AuditLog:
        """ثبت لاگ ایجاد"""
        return AuditService.log_action(
            db=db,
            user_id=user_id,
            action="create",
            table_name=table_name,
            record_id=record_id,
            new_values=new_values,
        )

    @staticmethod
    def log_update(
        db: Session,
        user_id: int,
        table_name: str,
        record_id: int,
        old_values: Any = None,
        new_values: Any = None,
    ) -> AuditLog:
        """ثبت لاگ ویرایش"""
        return AuditService.log_action(
            db=db,
            user_id=user_id,
            action="update",
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
            new_values=new_values,
        )

    @staticmethod
    def log_delete(
        db: Session,
        user_id: int,
        table_name: str,
        record_id: int,
        old_values: Any = None,
    ) -> AuditLog:
        """ثبت لاگ حذف"""
        return AuditService.log_action(
            db=db,
            user_id=user_id,
            action="delete",
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
        )
