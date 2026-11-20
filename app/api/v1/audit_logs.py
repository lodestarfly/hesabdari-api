from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit_log import AuditLog
from app.models.user import User
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("/")
def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    table_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت لاگ‌های سیستم با فیلتر و جستجو"""
    query = db.query(AuditLog)

    # جستجو در action، table_name، old_values، new_values
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                AuditLog.action.ilike(search_pattern),
                AuditLog.table_name.ilike(search_pattern),
                AuditLog.old_values.ilike(search_pattern),
                AuditLog.new_values.ilike(search_pattern)
            )
        )

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if action:
        query = query.filter(AuditLog.action == action)

    if table_name:
        query = query.filter(AuditLog.table_name == table_name)

    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)

    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()

    # تبدیل به دیکشنری
    result = []
    for log in logs:
        # گرفتن نام کاربر
        username = None
        if log.user_id:
            user = db.query(User).filter(User.id == log.user_id).first()
            username = user.username if user else None

        result.append({
            'id': log.id,
            'user_id': log.user_id,
            'username': username,
            'action': log.action,
            'table_name': log.table_name,
            'record_id': log.record_id,
            'old_values': log.old_values,
            'new_values': log.new_values,
            'ip_address': log.ip_address,
            'user_agent': log.user_agent,
            'created_at': log.created_at.isoformat() if log.created_at else None,
        })

    return {"total": total, "logs": result}


@router.get("/stats")
def get_audit_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """آمار لاگ‌ها"""
    from sqlalchemy import func

    total_logs = db.query(func.count(AuditLog.id)).scalar()

    actions_count = db.query(
        AuditLog.action,
        func.count(AuditLog.id)
    ).group_by(AuditLog.action).all()

    tables_count = db.query(
        AuditLog.table_name,
        func.count(AuditLog.id)
    ).group_by(AuditLog.table_name).all()

    return {
        "total_logs": total_logs,
        "actions": [{"action": a, "count": c} for a, c in actions_count],
        "tables": [{"table": t, "count": c} for t, c in tables_count],
    }
