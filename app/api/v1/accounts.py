"""
Endpointهای مدیریت حساب‌ها و تراز
"""
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.account_service import AccountService
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("/{account_type}/{account_id}/balance")
def get_account_balance(
    account_type: str,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت تراز حساب (مشتری یا تامین‌کننده)"""
    if account_type not in ['customer', 'supplier']:
        raise HTTPException(status_code=400, detail="نوع حساب نامعتبر است")

    return AccountService.get_account_balance(db, account_type, account_id)


@router.get("/summary")
def get_accounts_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """خلاصه تراز همه حساب‌ها"""
    from app.models.customer import Customer
    from app.models.supplier import Supplier

    customers = db.query(Customer).filter(Customer.is_deleted == 0).all()
    suppliers = db.query(Supplier).filter(Supplier.is_deleted == 0).all()

    total_receivable = sum(float(c.balance) for c in customers if c.balance and c.balance > 0)
    total_payable = sum(float(s.balance) for s in suppliers if s.balance and s.balance > 0)
    total_customer_debt = sum(float(c.balance) for c in customers if c.balance and c.balance < 0)
    total_supplier_debt = sum(float(s.balance) for s in suppliers if s.balance and s.balance < 0)

    return {
        "total_customers": len(customers),
        "total_suppliers": len(suppliers),
        "total_receivable": total_receivable,      # مطالبات از مشتریان
        "total_payable": total_payable,            # بدهی به تامین‌کنندگان
        "total_customer_debt": abs(total_customer_debt),  # بدهی مشتریان به ما
        "total_supplier_credit": abs(total_supplier_debt),  # اعتبار تامین‌کنندگان
        "net_balance": total_receivable - total_payable,
    }
