"""
سرویس مدیریت پرداخت‌ها
- ثبت پرداخت جدید (با به‌روزرسانی مانده حساب)
- حذف پرداخت (با برگرداندن مانده و به‌روزرسانی وضعیت فاکتور)
- دریافت لیست پرداخت‌ها با فیلتر و جستجو
"""
from decimal import Decimal
from typing import List, Optional

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate
from app.services.account_service import AccountService
from app.services.audit_service import AuditService
from fastapi import HTTPException
from sqlalchemy.orm import Session


class PaymentService:

    @staticmethod
    def get_payments(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        payment_type: Optional[str] = None,
        payment_method: Optional[str] = None,
        invoice_id: Optional[int] = None
    ) -> dict:
        """دریافت لیست پرداخت‌ها با فیلتر و جستجو"""
        from sqlalchemy import or_

        query = db.query(Payment).filter(Payment.is_deleted == 0)

        if search:
            search_pattern = f"%{search}%"
            query = query.join(Invoice).filter(
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
        payments = query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()

        result = []
        for payment in payments:
            result.append({
                'id': payment.id,
                'invoice_id': payment.invoice_id,
                'invoice_number': payment.invoice.invoice_number if payment.invoice else None,
                'amount': float(payment.amount),
                'payment_method': payment.payment_method,
                'payment_type': payment.payment_type,
                'reference_number': payment.reference_number,
                'notes': payment.notes,
                'created_by': payment.created_by,
                'created_at': payment.created_at.isoformat() if payment.created_at else None,
                'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
            })

        return {"total": total, "payments": result}

    @staticmethod
    def get_payment_by_id(db: Session, payment_id: int) -> dict:
        """دریافت پرداخت بر اساس ID"""
        payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.is_deleted == 0
        ).first()

        if not payment:
            raise HTTPException(status_code=404, detail="پرداخت یافت نشد")

        return {
            'id': payment.id,
            'invoice_id': payment.invoice_id,
            'invoice_number': payment.invoice.invoice_number if payment.invoice else None,
            'amount': float(payment.amount),
            'payment_method': payment.payment_method,
            'payment_type': payment.payment_type,
            'reference_number': payment.reference_number,
            'notes': payment.notes,
            'created_by': payment.created_by,
            'created_at': payment.created_at.isoformat() if payment.created_at else None,
            'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
        }

    @staticmethod
    def get_invoice_payments(db: Session, invoice_id: int) -> list:
        """دریافت پرداخت‌های یک فاکتور"""
        payments = db.query(Payment).filter(
            Payment.invoice_id == invoice_id,
            Payment.is_deleted == 0
        ).order_by(Payment.created_at.desc()).all()

        result = []
        for payment in payments:
            result.append({
                'id': payment.id,
                'invoice_id': payment.invoice_id,
                'invoice_number': payment.invoice.invoice_number if payment.invoice else None,
                'amount': float(payment.amount),
                'payment_method': payment.payment_method,
                'payment_type': payment.payment_type,
                'reference_number': payment.reference_number,
                'notes': payment.notes,
                'created_by': payment.created_by,
                'created_at': payment.created_at.isoformat() if payment.created_at else None,
                'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
            })

        return result

    @staticmethod
    def create_payment(
        db: Session,
        payment_data: PaymentCreate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """
        ثبت پرداخت جدید
        - بررسی اعتبار فاکتور
        - بررسی نوع پرداخت متناسب با نوع فاکتور
        - به‌روزرسانی مانده فاکتور و وضعیت
        - به‌روزرسانی مانده حساب مشتری/تامین‌کننده
        - ثبت لاگ
        """
        # بررسی وجود فاکتور
        invoice = db.query(Invoice).filter(
            Invoice.id == payment_data.invoice_id,
            Invoice.is_deleted == 0
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="فاکتور یافت نشد")

        # بررسی وضعیت فاکتور
        if invoice.status == 'cancelled':
            raise HTTPException(status_code=400, detail="نمی‌توان به فاکتور لغو شده پرداخت اضافه کرد")

        if invoice.status == 'paid':
            raise HTTPException(status_code=400, detail="فاکتور قبلاً تسویه شده است")

        # بررسی مبلغ پرداخت
        if payment_data.amount <= 0:
            raise HTTPException(status_code=400, detail="مبلغ پرداخت باید مثبت باشد")

        if payment_data.amount > invoice.remaining_amount:
            raise HTTPException(
                status_code=400,
                detail=f"مبلغ پرداخت ({payment_data.amount}) بیشتر از مانده فاکتور ({invoice.remaining_amount}) است"
            )

        # ✅ بررسی نوع پرداخت متناسب با نوع فاکتور
        if invoice.invoice_type == 'sale' and payment_data.payment_type != 'receipt':
            raise HTTPException(status_code=400, detail="برای فاکتور فروش باید نوع پرداخت 'دریافت' باشد")
        if invoice.invoice_type == 'purchase' and payment_data.payment_type != 'payment':
            raise HTTPException(status_code=400, detail="برای فاکتور خرید باید نوع پرداخت 'پرداخت' باشد")

        # ایجاد پرداخت
        new_payment = Payment(
            invoice_id=payment_data.invoice_id,
            amount=Decimal(str(payment_data.amount)),
            payment_method=payment_data.payment_method,
            payment_type=payment_data.payment_type,
            reference_number=payment_data.reference_number,
            notes=payment_data.notes,
            created_by=user_id
        )

        db.add(new_payment)

        # به‌روزرسانی مبالغ فاکتور با دقت Decimal
        invoice.paid_amount = (invoice.paid_amount or 0) + Decimal(str(payment_data.amount))
        invoice.remaining_amount = max(0, (invoice.remaining_amount or 0) - Decimal(str(payment_data.amount)))

        # تغییر وضعیت فاکتور در صورت تسویه کامل
        if invoice.remaining_amount <= 0:
            invoice.status = 'paid'
            invoice.remaining_amount = 0

        # ✅ به‌روزرسانی مانده حساب مشتری/تامین‌کننده
        AccountService.apply_invoice_accounting(db, invoice)

        db.commit()
        db.refresh(new_payment)
        db.refresh(invoice)

        # ✅ ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="create",
            table_name="payments",
            record_id=new_payment.id,
            new_values={
                "invoice_id": new_payment.invoice_id,
                "invoice_number": invoice.invoice_number,
                "amount": float(new_payment.amount),
                "payment_method": new_payment.payment_method,
                "payment_type": new_payment.payment_type,
            },
            ip_address=ip,
            user_agent=ua
        )

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

    @staticmethod
    def delete_payment(
        db: Session,
        payment_id: int,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """
        حذف پرداخت (Soft Delete)
        - برگرداندن مبلغ به فاکتور
        - تغییر وضعیت فاکتور از paid به confirmed (در صورت نیاز)
        - به‌روزرسانی مانده حساب مشتری/تامین‌کننده
        - ثبت لاگ
        """
        # بررسی وجود پرداخت
        payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.is_deleted == 0
        ).first()

        if not payment:
            raise HTTPException(status_code=404, detail="پرداخت یافت نشد")

        # بررسی وجود فاکتور
        invoice = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="فاکتور یافت نشد")

        # بررسی وضعیت فاکتور
        if invoice.status == 'cancelled':
            raise HTTPException(status_code=400, detail="فاکتور لغو شده است و پرداخت قابل حذف نیست")

        # ذخیره اطلاعات قدیم برای لاگ
        old_invoice_status = invoice.status
        old_paid_amount = float(invoice.paid_amount or 0)
        old_remaining_amount = float(invoice.remaining_amount or 0)

        # ✅ ۱. برگرداندن مبلغ به فاکتور
        invoice.paid_amount = max(0, (invoice.paid_amount or 0) - payment.amount)
        invoice.remaining_amount = (invoice.remaining_amount or 0) + payment.amount

        # ✅ ۲. تغییر وضعیت فاکتور از paid به confirmed (اگر مانده دارد)
        if invoice.status == 'paid' and invoice.remaining_amount > 0:
            invoice.status = 'confirmed'

        # ✅ ۳. حذف پرداخت (Soft Delete)
        payment.is_deleted = 1
        payment.updated_by = user_id

        # ✅ ۴. به‌روزرسانی مانده حساب مشتری/تامین‌کننده
        AccountService.apply_invoice_accounting(db, invoice)

        db.commit()
        db.refresh(payment)
        db.refresh(invoice)

        # ✅ ۵. ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="delete",
            table_name="payments",
            record_id=payment_id,
            old_values={
                "amount": float(payment.amount),
                "invoice_number": invoice.invoice_number,
                "invoice_status": old_invoice_status,
                "paid_amount": old_paid_amount,
                "remaining_amount": old_remaining_amount,
            },
            new_values={
                "status": "deleted",
                "new_invoice_status": invoice.status,
                "new_paid_amount": float(invoice.paid_amount or 0),
                "new_remaining_amount": float(invoice.remaining_amount or 0),
            },
            ip_address=ip,
            user_agent=ua
        )

        return {
            'id': payment.id,
            'invoice_id': payment.invoice_id,
            'invoice_number': invoice.invoice_number,
            'amount': float(payment.amount),
            'payment_method': payment.payment_method,
            'payment_type': payment.payment_type,
            'reference_number': payment.reference_number,
            'notes': payment.notes,
            'created_by': payment.created_by,
            'created_at': payment.created_at.isoformat() if payment.created_at else None,
            'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
        }
