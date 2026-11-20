# app/api/v1/invoices.py
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_active_superuser, get_current_user
from app.models.user import User
from app.schemas.invoice import (InvoiceCreate, InvoiceListResponse,
                                 InvoiceResponse, InvoiceUpdate, PaymentCreate)
from app.schemas.payment import PaymentResponse  # ✅ از payment.py که درست است
from app.services.invoice_service import InvoiceService
from app.services.payment_service import PaymentService
from app.utils.request_utils import get_client_ip, get_user_agent
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("/", response_model=InvoiceListResponse)
def list_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=1),
    invoice_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    supplier_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # همه کاربران لاگین کرده
):
    return InvoiceService.get_invoices(
        db=db, skip=skip, limit=limit, search=search,
        invoice_type=invoice_type, status=status,
        customer_id=customer_id, supplier_id=supplier_id
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # همه کاربران لاگین کرده
):
    return InvoiceService.get_invoice_by_id(db, invoice_id)


@router.post("/", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    invoice_data: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user), # <--- فقط نیاز به لاگین دارد (نه لزوماً ادمین)
    request: Request = None
):
    """
    ایجاد فاکتور جدید
    - invoice_type: sale (فروش), purchase (خرید), proforma (پیش‌فاکتور)
    """
    return InvoiceService.create_invoice(
        db=db,
        invoice_data=invoice_data,
        user_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )


@router.put("/{invoice_id}/convert", response_model=InvoiceResponse)
def convert_proforma_to_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser), # فقط ادمین
    request: Request = None
):
    return InvoiceService.convert_proforma_to_invoice(
        db=db, invoice_id=invoice_id, user_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )


@router.put("/{invoice_id}/cancel", response_model=InvoiceResponse)
def cancel_invoice(
    invoice_id: int,
    reason: str = Query(..., min_length=5),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser), # فقط ادمین
    request: Request = None
):
    return InvoiceService.cancel_invoice(
        db=db, invoice_id=invoice_id, reason=reason, user_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )


@router.post("/{invoice_id}/payments", response_model=PaymentResponse, status_code=201)
def add_payment(
    invoice_id: int,  # ✅ از URL
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """ثبت پرداخت برای فاکتور"""
    # ✅ اگر invoice_id در body نبود، از URL بگیر
    if payment_data.invoice_id is None:
        payment_data.invoice_id = invoice_id

    return PaymentService.create_payment(
        db=db,
        payment_data=payment_data,
        user_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )

@router.delete("/{invoice_id}/payments/{payment_id}")
def delete_payment(
    invoice_id: int,
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """حذف پرداخت"""
    return PaymentService.delete_payment(
        db=db,
        payment_id=payment_id,
        user_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )
