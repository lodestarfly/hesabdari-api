from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.user import User
from app.services.payment_service import PaymentService
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("/")
def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    payment_type: Optional[str] = None,
    payment_method: Optional[str] = None,
    invoice_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت لیست پرداخت‌ها"""
    from sqlalchemy import or_

    # JOIN با Invoice
    query = db.query(Payment, Invoice.invoice_number).join(
        Invoice, Payment.invoice_id == Invoice.id
    ).filter(Payment.is_deleted == 0)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Invoice.invoice_number.ilike(search_pattern),
                Payment.reference_number.ilike(search_pattern)
            )
        )

    if payment_type:
        query = query.filter(Payment.payment_type == payment_type)

    if payment_method:
        query = query.filter(Payment.payment_method == payment_method)

    if invoice_id:
        query = query.filter(Payment.invoice_id == invoice_id)

    total = query.count()
    results = query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()

    # تبدیل به لیست دیکشنری
    payments = []
    for payment, invoice_number in results:
        payments.append({
            'id': payment.id,
            'invoice_id': payment.invoice_id,
            'invoice_number': invoice_number,  # ✅ از JOIN
            'amount': float(payment.amount),
            'payment_method': payment.payment_method,
            'payment_type': payment.payment_type,
            'reference_number': payment.reference_number,
            'notes': payment.notes,
            'created_by': payment.created_by,
            'created_at': payment.created_at.isoformat() if payment.created_at else None,
            'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
        })

    return {"total": total, "payments": payments}


@router.get("/invoice/{invoice_id}")
def get_invoice_payments(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت پرداخت‌های یک فاکتور"""
    results = db.query(Payment, Invoice.invoice_number).join(
        Invoice, Payment.invoice_id == Invoice.id
    ).filter(
        Payment.invoice_id == invoice_id,
        Payment.is_deleted == 0
    ).order_by(Payment.created_at.desc()).all()

    payments = []
    for payment, invoice_number in results:
        payments.append({
            'id': payment.id,
            'invoice_id': payment.invoice_id,
            'invoice_number': invoice_number,
            'amount': float(payment.amount),
            'payment_method': payment.payment_method,
            'payment_type': payment.payment_type,
            'reference_number': payment.reference_number,
            'notes': payment.notes,
            'created_by': payment.created_by,
            'created_at': payment.created_at.isoformat() if payment.created_at else None,
            'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
        })

    return payments


@router.get("/{payment_id}")
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت جزئیات یک پرداخت"""
    result = db.query(Payment, Invoice.invoice_number).join(
        Invoice, Payment.invoice_id == Invoice.id
    ).filter(
        Payment.id == payment_id,
        Payment.is_deleted == 0
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment, invoice_number = result

    return {
        'id': payment.id,
        'invoice_id': payment.invoice_id,
        'invoice_number': invoice_number,
        'amount': float(payment.amount),
        'payment_method': payment.payment_method,
        'payment_type': payment.payment_type,
        'reference_number': payment.reference_number,
        'notes': payment.notes,
        'created_by': payment.created_by,
        'created_at': payment.created_at.isoformat() if payment.created_at else None,
        'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
    }


@router.post("/", status_code=201)
def create_payment(
    payment_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ثبت پرداخت جدید"""
    invoice = db.query(Invoice).filter(
        Invoice.id == payment_data['invoice_id'],
        Invoice.is_deleted == 0
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status == 'cancelled':
        raise HTTPException(status_code=400, detail="Cannot add payment to cancelled invoice")

    amount = float(payment_data['amount'])
    if amount > invoice.remaining_amount:
        raise HTTPException(status_code=400, detail="مبلغ پرداخت بیشتر از مانده فاکتور است")

    if invoice.invoice_type == 'sale' and payment_data['payment_type'] != 'receipt':
        raise HTTPException(status_code=400, detail="برای فاکتور فروش باید نوع 'دریافت' باشد")
    if invoice.invoice_type == 'purchase' and payment_data['payment_type'] != 'payment':
        raise HTTPException(status_code=400, detail="برای فاکتور خرید باید نوع 'پرداخت' باشد")

    new_payment = Payment(
        invoice_id=payment_data['invoice_id'],
        amount=amount,
        payment_method=payment_data['payment_method'],
        payment_type=payment_data['payment_type'],
        reference_number=payment_data.get('reference_number'),
        notes=payment_data.get('notes'),
        created_by=current_user.id
    )

    db.add(new_payment)

    invoice.paid_amount = (invoice.paid_amount or 0) + amount
    invoice.remaining_amount = (invoice.remaining_amount or 0) - amount

    if invoice.remaining_amount <= 0:
        invoice.status = 'paid'
        invoice.remaining_amount = 0

    db.commit()
    db.refresh(new_payment)

    return {
        'id': new_payment.id,
        'invoice_id': new_payment.invoice_id,
        'invoice_number': invoice.invoice_number,
        'amount': float(new_payment.amount),
        'payment_method': new_payment.payment_method,
        'payment_type': new_payment.payment_type,
        'reference_number': new_payment.reference_number,
        'notes': new_payment.notes,
        'created_by': new_payment.created_by,
        'created_at': new_payment.created_at.isoformat() if new_payment.created_at else None,
        'updated_at': new_payment.updated_at.isoformat() if new_payment.updated_at else None,
    }


@router.delete("/{payment_id}")
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """حذف پرداخت"""
    result = db.query(Payment, Invoice.invoice_number).join(
        Invoice, Payment.invoice_id == Invoice.id
    ).filter(
        Payment.id == payment_id,
        Payment.is_deleted == 0
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment, invoice_number = result

    invoice = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.paid_amount = max(0, (invoice.paid_amount or 0) - payment.amount)
    invoice.remaining_amount = (invoice.remaining_amount or 0) + payment.amount

    if invoice.status == 'paid' and invoice.remaining_amount > 0:
        invoice.status = 'confirmed'

    payment.is_deleted = 1

    db.commit()

    return {
        'id': payment.id,
        'invoice_id': payment.invoice_id,
        'invoice_number': invoice_number,
        'amount': float(payment.amount),
        'payment_method': payment.payment_method,
        'payment_type': payment.payment_type,
        'reference_number': payment.reference_number,
        'notes': payment.notes,
        'created_by': payment.created_by,
        'created_at': payment.created_at.isoformat() if payment.created_at else None,
        'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
    }
