"""
مدیریت تامین‌کنندگان
- لیست، ایجاد، ویرایش، حذف
- Dropdown
- ✅ Recalculate Balances (به‌روزرسانی مانده همه تامین‌کنندگان)
"""
from decimal import Decimal
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_active_superuser, get_current_user
from app.models.customer import Supplier
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.user import User
from app.schemas.customer import (SupplierCreate, SupplierListResponse,
                                  SupplierResponse, SupplierUpdate)
from app.utils.request_utils import get_client_ip, get_user_agent
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


# ===== 1. Dropdown =====
@router.get("/dropdown")
async def suppliers_dropdown(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت لیست ساده تامین‌کنندگان برای dropdown"""
    try:
        result = db.query(
            Supplier.id,
            Supplier.name
        ).filter(
            Supplier.is_deleted == 0,
            Supplier.is_active == True
        ).order_by(
            Supplier.name
        ).limit(100).all()

        return [
            {"id": row.id, "name": row.name}
            for row in result
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== 2. Recalculate Balances =====
@router.post("/recalculate-balances")
def recalculate_supplier_balances(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser)
):
    """
    به‌روزرسانی مانده حساب همه تامین‌کنندگان
    - مجموع فاکتورهای خرید فعال - مجموع پرداخت‌های فعال
    """
    suppliers = db.query(Supplier).filter(Supplier.is_deleted == 0).all()

    updated_count = 0
    errors = []

    for supplier in suppliers:
        try:
            # مجموع فاکتورهای خرید فعال
            total_invoices = db.query(
                func.coalesce(func.sum(Invoice.total_amount), 0)
            ).filter(
                Invoice.supplier_id == supplier.id,
                Invoice.is_deleted == 0,
                Invoice.invoice_type == 'purchase',
                Invoice.status != 'cancelled'
            ).scalar()

            # مجموع پرداخت‌های فعال
            total_payments = db.query(
                func.coalesce(func.sum(Payment.amount), 0)
            ).join(Invoice).filter(
                Invoice.supplier_id == supplier.id,
                Invoice.is_deleted == 0,
                Invoice.invoice_type == 'purchase',
                Invoice.status != 'cancelled',
                Payment.is_deleted == 0
            ).scalar()

            old_balance = float(supplier.balance or 0)
            new_balance = Decimal(str(total_invoices)) - Decimal(str(total_payments))

            supplier.balance = new_balance
            updated_count += 1

            print(f"✅ Supplier {supplier.name} (ID={supplier.id}): "
                  f"old={old_balance}, invoices={float(total_invoices)}, "
                  f"payments={float(total_payments)}, new={float(new_balance)}")

        except Exception as e:
            errors.append(f"Supplier {supplier.id}: {str(e)}")

    db.commit()

    return {
        "message": f"مانده حساب {updated_count} تامین‌کننده به‌روز شد",
        "updated_count": updated_count,
        "total_suppliers": len(suppliers),
        "errors": errors
    }


# ===== 3. List (اصلاح‌شده) =====
@router.get("/", response_model=SupplierListResponse)
def list_suppliers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None, min_length=1),
    is_active: Optional[bool] = Query(None),
    has_balance: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت لیست تامین‌کنندگان با فیلتر و جستجو"""
    query = db.query(Supplier).filter(Supplier.is_deleted == 0)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Supplier.name.ilike(search_pattern)) |
            (Supplier.national_code.ilike(search_pattern)) |
            (Supplier.phone.ilike(search_pattern)) |
            (Supplier.mobile.ilike(search_pattern))
        )

    if is_active is not None:
        query = query.filter(Supplier.is_active == is_active)

    if has_balance is not None:
        if has_balance:
            query = query.filter(Supplier.balance != 0)
        else:
            query = query.filter(Supplier.balance == 0)

    total = query.count()
    suppliers = query.order_by(Supplier.created_at.desc()).offset(skip).limit(limit).all()

    return {"total": total, "suppliers": suppliers}


# ===== 4. Get by ID =====
@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت تامین‌کننده بر اساس ID"""
    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id,
        Supplier.is_deleted == 0
    ).first()

    if not supplier:
        raise HTTPException(status_code=404, detail="تامین‌کننده یافت نشد")

    return supplier


# ===== 5. Create =====
@router.post("/", response_model=SupplierResponse, status_code=201)
def create_supplier(
    supplier_data: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """ایجاد تامین‌کننده جدید"""
    # بررسی یکتا بودن کد ملی
    if supplier_data.national_code:
        existing = db.query(Supplier).filter(
            Supplier.national_code == supplier_data.national_code,
            Supplier.is_deleted == 0
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"کد ملی '{supplier_data.national_code}' قبلاً ثبت شده است"
            )

    new_supplier = Supplier(
        name=supplier_data.name,
        national_code=supplier_data.national_code,
        phone=supplier_data.phone,
        mobile=supplier_data.mobile,
        email=supplier_data.email,
        address=supplier_data.address,
        contact_person=supplier_data.contact_person,
        balance=0,
        bank_card_number=supplier_data.bank_card_number,
        bank_account=supplier_data.bank_account,
        iban=supplier_data.iban,
        is_active=1 if supplier_data.is_active else 0,
        notes=supplier_data.notes,
        created_by=current_user.id
    )

    db.add(new_supplier)
    db.commit()
    db.refresh(new_supplier)

    return new_supplier


# ===== 6. Update =====
@router.put("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    supplier_data: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """به‌روزرسانی تامین‌کننده"""
    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id,
        Supplier.is_deleted == 0
    ).first()

    if not supplier:
        raise HTTPException(status_code=404, detail="تامین‌کننده یافت نشد")

    # بررسی یکتا بودن کد ملی
    if supplier_data.national_code and supplier_data.national_code != supplier.national_code:
        existing = db.query(Supplier).filter(
            Supplier.national_code == supplier_data.national_code,
            Supplier.id != supplier_id,
            Supplier.is_deleted == 0
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"کد ملی '{supplier_data.national_code}' قبلاً ثبت شده است"
            )

    # به‌روزرسانی فیلدها
    if supplier_data.name is not None:
        supplier.name = supplier_data.name
    if supplier_data.national_code is not None:
        supplier.national_code = supplier_data.national_code
    if supplier_data.phone is not None:
        supplier.phone = supplier_data.phone
    if supplier_data.mobile is not None:
        supplier.mobile = supplier_data.mobile
    if supplier_data.email is not None:
        supplier.email = supplier_data.email
    if supplier_data.address is not None:
        supplier.address = supplier_data.address
    if supplier_data.contact_person is not None:
        supplier.contact_person = supplier_data.contact_person
    if supplier_data.bank_card_number is not None:
        supplier.bank_card_number = supplier_data.bank_card_number
    if supplier_data.bank_account is not None:
        supplier.bank_account = supplier_data.bank_account
    if supplier_data.iban is not None:
        supplier.iban = supplier_data.iban
    if supplier_data.is_active is not None:
        supplier.is_active = 1 if supplier_data.is_active else 0
    if supplier_data.notes is not None:
        supplier.notes = supplier_data.notes

    supplier.updated_by = current_user.id

    db.commit()
    db.refresh(supplier)

    return supplier


# ===== 7. Delete =====
@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """حذف تامین‌کننده (Soft Delete)"""
    from app.models.invoice import InvoiceItem

    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id,
        Supplier.is_deleted == 0
    ).first()

    if not supplier:
        raise HTTPException(status_code=404, detail="تامین‌کننده یافت نشد")

    # بررسی استفاده در فاکتورها
    used_in_invoice = db.query(InvoiceItem).join(Invoice).filter(
        Invoice.supplier_id == supplier_id,
        Invoice.is_deleted == 0,
        InvoiceItem.is_deleted == 0
    ).first()

    if used_in_invoice:
        raise HTTPException(
            status_code=400,
            detail=f"تامین‌کننده '{supplier.name}' در فاکتور استفاده شده و قابل حذف نیست"
        )

    supplier.is_deleted = 1
    supplier.updated_by = current_user.id

    db.commit()

    return {"message": "تامین‌کننده با موفقیت حذف شد"}
