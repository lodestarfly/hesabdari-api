"""
مدیریت مشتریان
- لیست، ایجاد، ویرایش، حذف
- Dropdown
- ✅ Recalculate Balances (به‌روزرسانی مانده همه مشتریان)
"""
from decimal import Decimal
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_active_superuser, get_current_user
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.user import User
from app.schemas.customer import (CustomerCreate, CustomerListResponse,
                                  CustomerResponse, CustomerUpdate)
from app.services.customer_service import CustomerService
from app.utils.request_utils import get_client_ip, get_user_agent
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/customers", tags=["Customers"])


# ===== 1. Dropdown =====
@router.get("/dropdown")
async def customers_dropdown(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت لیست ساده مشتریان برای dropdown"""
    try:
        result = db.query(
            Customer.id,
            Customer.name
        ).filter(
            Customer.is_deleted == 0,
            Customer.is_active == True
        ).order_by(
            Customer.name
        ).limit(100).all()

        return [
            {"id": row.id, "name": row.name}
            for row in result
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== 2. Recalculate Balances (جدید) =====
@router.post("/recalculate-balances")
def recalculate_customer_balances(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser)
):
    """
    به‌روزرسانی مانده حساب همه مشتریان
    - مجموع فاکتورهای فروش فعال - مجموع پرداخت‌های فعال
    """
    customers = db.query(Customer).filter(Customer.is_deleted == 0).all()

    updated_count = 0
    errors = []

    for customer in customers:
        try:
            # مجموع فاکتورهای فروش/پیش‌فاکتور فعال
            total_invoices = db.query(
                func.coalesce(func.sum(Invoice.total_amount), 0)
            ).filter(
                Invoice.customer_id == customer.id,
                Invoice.is_deleted == 0,
                Invoice.invoice_type.in_(['sale', 'proforma']),
                Invoice.status != 'cancelled'
            ).scalar()

            # مجموع پرداخت‌های فعال
            total_payments = db.query(
                func.coalesce(func.sum(Payment.amount), 0)
            ).join(Invoice).filter(
                Invoice.customer_id == customer.id,
                Invoice.is_deleted == 0,
                Invoice.invoice_type.in_(['sale', 'proforma']),
                Invoice.status != 'cancelled',
                Payment.is_deleted == 0
            ).scalar()

            old_balance = float(customer.balance or 0)
            new_balance = Decimal(str(total_invoices)) - Decimal(str(total_payments))

            customer.balance = new_balance
            updated_count += 1

            print(f"✅ Customer {customer.name} (ID={customer.id}): "
                  f"old={old_balance}, invoices={float(total_invoices)}, "
                  f"payments={float(total_payments)}, new={float(new_balance)}")

        except Exception as e:
            errors.append(f"Customer {customer.id}: {str(e)}")

    db.commit()

    return {
        "message": f"مانده حساب {updated_count} مشتری به‌روز شد",
        "updated_count": updated_count,
        "total_customers": len(customers),
        "errors": errors
    }


# ===== 3. List =====
@router.get("/", response_model=CustomerListResponse)
def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None, min_length=1),
    customer_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    has_balance: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return CustomerService.get_customers(
        db=db,
        skip=skip,
        limit=limit,
        search=search,
        customer_type=customer_type,
        is_active=is_active,
        has_balance=has_balance
    )


# ===== 4. Get by ID =====
@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return CustomerService.get_customer_by_id(db, customer_id)


# ===== 5. Create =====
@router.post("/", response_model=CustomerResponse, status_code=201)
def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    return CustomerService.create_customer(
        db=db,
        customer_data=customer_data,
        user_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )


# ===== 6. Update =====
@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    return CustomerService.update_customer(
        db=db,
        customer_id=customer_id,
        customer_data=customer_data,
        user_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )


# ===== 7. Delete =====
@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    return CustomerService.delete_customer(
        db=db,
        customer_id=customer_id,
        user_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )
