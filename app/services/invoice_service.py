"""
سرویس مدیریت فاکتورها
- ایجاد فاکتور (خرید/فروش/پیش‌فاکتور)
- به‌روزرسانی موجودی انبار
- به‌روزرسانی مانده حساب مشتری/تامین‌کننده
- لغو فاکتور + برگرداندن موجودی + حذف پرداخت‌ها
- ثبت و حذف پرداخت
"""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from app.models.customer import Customer, Supplier
from app.models.invoice import Invoice, InvoiceItem
from app.models.payment import Payment
from app.models.product import Product
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate, PaymentCreate
from app.services.account_service import AccountService
from app.services.audit_service import AuditService
from app.services.inventory_service import InventoryService
from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session


class InvoiceService:

    @staticmethod
    def generate_invoice_number(db: Session, invoice_type: str) -> str:
        """تولید شماره فاکتور خودکار"""
        type_prefix = {
            'sale': 'S',
            'purchase': 'P',
            'proforma': 'PR'
        }.get(invoice_type, 'X')

        year = datetime.now().year
        prefix = f"{type_prefix}-{year}"

        last_invoice = db.query(Invoice).filter(
            Invoice.invoice_number.like(f"{prefix}-%"),
            Invoice.is_deleted == 0
        ).order_by(Invoice.id.desc()).first()

        if last_invoice:
            last_number = int(last_invoice.invoice_number.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1

        return f"{prefix}-{new_number:04d}"

    @staticmethod
    def calculate_totals(items: List[dict], discount_amount: Decimal, discount_percent: Decimal, tax_percent: Decimal) -> dict:
        """محاسبه جمع کل، تخفیف و مالیات"""
        subtotal = Decimal('0')

        for item in items:
            quantity = Decimal(str(item['quantity']))
            unit_price = Decimal(str(item['unit_price']))
            item_discount_amount = Decimal(str(item.get('discount_amount', 0)))
            item_discount_percent = Decimal(str(item.get('discount_percent', 0)))

            item_total = quantity * unit_price

            if item_discount_percent > 0:
                item_discount = item_total * (item_discount_percent / 100)
                item_total -= item_discount
            item_total -= item_discount_amount

            item['total_price'] = item_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            subtotal += item_total

        if discount_percent > 0:
            discount = subtotal * (discount_percent / 100)
            subtotal -= discount
        subtotal -= discount_amount

        tax_amount = subtotal * (tax_percent / 100)
        total_amount = subtotal + tax_amount

        return {
            'subtotal': subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'tax_amount': tax_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'total_amount': total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        }

    @staticmethod
    def create_invoice(
        db: Session,
        invoice_data: InvoiceCreate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> Invoice:
        """ایجاد فاکتور جدید"""
        # بررسی وجود مشتری/تامین‌کننده
        if invoice_data.invoice_type == 'sale' and invoice_data.customer_id:
            customer = db.query(Customer).filter(
                Customer.id == invoice_data.customer_id,
                Customer.is_deleted == 0
            ).first()
            if not customer:
                raise HTTPException(status_code=404, detail="مشتری یافت نشد")

        if invoice_data.invoice_type == 'purchase' and invoice_data.supplier_id:
            supplier = db.query(Supplier).filter(
                Supplier.id == invoice_data.supplier_id,
                Supplier.is_deleted == 0
            ).first()
            if not supplier:
                raise HTTPException(status_code=404, detail="تامین‌کننده یافت نشد")

        # تولید شماره فاکتور
        invoice_number = InvoiceService.generate_invoice_number(db, invoice_data.invoice_type)

        # محاسبه totals
        items_data = [item.model_dump() for item in invoice_data.items]
        totals = InvoiceService.calculate_totals(
            items_data,
            invoice_data.discount_amount,
            invoice_data.discount_percent,
            invoice_data.tax_percent
        )

        # وضعیت پیش‌فرض: پیش‌فاکتور = draft، بقیه = confirmed
        initial_status = 'draft' if invoice_data.invoice_type == 'proforma' else 'confirmed'

        # ایجاد فاکتور
        new_invoice = Invoice(
            invoice_number=invoice_number,
            invoice_type=invoice_data.invoice_type,
            status=initial_status,
            customer_id=invoice_data.customer_id,
            supplier_id=invoice_data.supplier_id,
            user_id=user_id,
            due_date=invoice_data.due_date,
            subtotal=totals['subtotal'],
            discount_amount=invoice_data.discount_amount,
            discount_percent=invoice_data.discount_percent,
            tax_amount=totals['tax_amount'],
            tax_percent=invoice_data.tax_percent,
            total_amount=totals['total_amount'],
            paid_amount=0,
            remaining_amount=totals['total_amount'],
            is_official=1 if invoice_data.is_official else 0,
            notes=invoice_data.notes,
            created_by=user_id
        )

        db.add(new_invoice)
        db.flush()

        # ایجاد آیتم‌های فاکتور
        invoice_items = []
        for item_data in items_data:
            item = InvoiceItem(
                invoice_id=new_invoice.id,
                product_id=item_data['product_id'],
                description=item_data.get('description'),
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                discount_amount=item_data.get('discount_amount', 0),
                discount_percent=item_data.get('discount_percent', 0),
                total_price=item_data['total_price'],
                row_number=item_data['row_number'],
                created_by=user_id
            )
            db.add(item)
            invoice_items.append(item)

        db.commit()
        db.refresh(new_invoice)

        # ✅ اعمال تغییرات موجودی (فقط برای فاکتورهای قطعی)
        if new_invoice.status == 'confirmed':
            InventoryService.apply_invoice_inventory(db, new_invoice)
            # ✅ به‌روزرسانی مانده حساب
            AccountService.apply_invoice_accounting(db, new_invoice)

        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="create",
            table_name="invoices",
            record_id=new_invoice.id,
            new_values={
                "invoice_number": new_invoice.invoice_number,
                "invoice_type": new_invoice.invoice_type,
                "total_amount": float(new_invoice.total_amount)
            },
            ip_address=ip,
            user_agent=ua
        )

        return new_invoice

    @staticmethod
    def get_invoices(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        invoice_type: Optional[str] = None,
        status: Optional[str] = None,
        customer_id: Optional[int] = None,
        supplier_id: Optional[int] = None
    ) -> dict:
        """دریافت لیست فاکتورها"""
        query = db.query(Invoice).filter(Invoice.is_deleted == 0)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(Invoice.invoice_number.ilike(search_pattern))

        if invoice_type:
            query = query.filter(Invoice.invoice_type == invoice_type)

        if status:
            query = query.filter(Invoice.status == status)

        if customer_id:
            query = query.filter(Invoice.customer_id == customer_id)

        if supplier_id:
            query = query.filter(Invoice.supplier_id == supplier_id)

        total = query.count()
        invoices = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()

        return {"total": total, "invoices": invoices}

    @staticmethod
    def get_invoice_by_id(db: Session, invoice_id: int) -> Invoice:
        """دریافت فاکتور بر اساس ID"""
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == 0
        ).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="فاکتور یافت نشد")
        return invoice

    @staticmethod
    def convert_proforma_to_invoice(
        db: Session,
        invoice_id: int,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> Invoice:
        """تبدیل پیش‌فاکتور به فاکتور قطعی"""
        invoice = InvoiceService.get_invoice_by_id(db, invoice_id)

        if invoice.invoice_type != 'proforma':
            raise HTTPException(status_code=400, detail="فقط پیش‌فاکتور قابل تبدیل است")

        if invoice.status != 'draft':
            raise HTTPException(status_code=400, detail="فاکتور قبلاً تایید شده است")

        old_status = invoice.status
        old_type = invoice.invoice_type

        # تغییر وضعیت و نوع
        invoice.status = 'confirmed'
        invoice.invoice_type = 'sale'
        invoice.updated_by = user_id

        # ✅ اعمال تغییرات موجودی (کاهش برای فروش)
        InventoryService.apply_invoice_inventory(db, invoice)

        # ✅ به‌روزرسانی مانده حساب مشتری
        AccountService.apply_invoice_accounting(db, invoice)

        db.commit()
        db.refresh(invoice)

        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="update",
            table_name="invoices",
            record_id=invoice_id,
            old_values={"status": old_status, "invoice_type": old_type},
            new_values={"status": "confirmed", "invoice_type": "sale"},
            ip_address=ip,
            user_agent=ua
        )

        return invoice

    @staticmethod
    def cancel_invoice(
        db: Session,
        invoice_id: int,
        reason: str,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> Invoice:
        """
        لغو فاکتور
        - برگرداندن موجودی انبار
        - حذف (soft delete) پرداخت‌های مرتبط
        - به‌روزرسانی مانده حساب مشتری/تامین‌کننده
        """
        invoice = InvoiceService.get_invoice_by_id(db, invoice_id)

        if invoice.status == 'cancelled':
            raise HTTPException(status_code=400, detail="فاکتور قبلاً لغو شده است")

        old_status = invoice.status

        # ✅ ۱. برگرداندن موجودی (اگر فاکتور قطعی بود)
        if old_status in ['confirmed', 'paid']:
            InventoryService.reverse_invoice_inventory(db, invoice)

        # ✅ ۲. حذف تمام پرداخت‌های مرتبط (soft delete)
        payments = db.query(Payment).filter(
            Payment.invoice_id == invoice_id,
            Payment.is_deleted == 0
        ).all()

        deleted_payments_count = 0
        for payment in payments:
            payment.is_deleted = 1
            db.add(payment)
            deleted_payments_count += 1

        # ✅ ۳. به‌روزرسانی وضعیت فاکتور
        invoice.status = 'cancelled'
        invoice.cancellation_reason = reason
        invoice.updated_by = user_id

        # ✅ ۴. به‌روزرسانی مانده حساب مشتری/تامین‌کننده
        AccountService.reverse_invoice_accounting(db, invoice)

        db.commit()
        db.refresh(invoice)

        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="update",
            table_name="invoices",
            record_id=invoice_id,
            old_values={
                "status": old_status,
                "deleted_payments": deleted_payments_count
            },
            new_values={"status": "cancelled", "reason": reason},
            ip_address=ip,
            user_agent=ua
        )

        return invoice

    @staticmethod
    def add_payment(
        db: Session,
        invoice_id: int,
        payment_data: PaymentCreate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> Payment:
        """ثبت پرداخت برای فاکتور"""
        invoice = InvoiceService.get_invoice_by_id(db, invoice_id)

        if invoice.status == 'cancelled':
            raise HTTPException(status_code=400, detail="نمی‌توان به فاکتور لغو شده پرداخت اضافه کرد")

        if invoice.status == 'paid':
            raise HTTPException(status_code=400, detail="فاکتور قبلاً تسویه شده است")

        # بررسی مبلغ پرداختی
        if payment_data.amount > invoice.remaining_amount:
            raise HTTPException(
                status_code=400,
                detail=f"مبلغ پرداخت بیشتر از مانده فاکتور است. مانده: {invoice.remaining_amount}"
            )

        # ایجاد پرداخت
        new_payment = Payment(
            invoice_id=invoice_id,
            amount=payment_data.amount,
            payment_method=payment_data.payment_method,
            payment_type=payment_data.payment_type,
            reference_number=payment_data.reference_number,
            notes=payment_data.notes,
            created_by=user_id
        )

        db.add(new_payment)

        # به‌روزرسانی مبالغ فاکتور
        invoice.paid_amount = (invoice.paid_amount or 0) + payment_data.amount
        invoice.remaining_amount = max(0, (invoice.remaining_amount or 0) - payment_data.amount)

        if invoice.remaining_amount <= 0:
            invoice.status = 'paid'
            invoice.remaining_amount = 0

        # ✅ به‌روزرسانی مانده حساب مشتری/تامین‌کننده
        AccountService.apply_invoice_accounting(db, invoice)

        db.commit()
        db.refresh(new_payment)
        db.refresh(invoice)

        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="create",
            table_name="payments",
            record_id=new_payment.id,
            new_values={
                "invoice_id": invoice_id,
                "amount": float(payment_data.amount),
                "payment_method": payment_data.payment_method
            },
            ip_address=ip,
            user_agent=ua
        )

        return new_payment

    @staticmethod
    def delete_payment(
        db: Session,
        payment_id: int,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> Payment:
        """
        حذف پرداخت (soft delete)
        - برگرداندن مبلغ به فاکتور
        - تغییر وضعیت فاکتور از paid به confirmed (اگر لازم باشد)
        - به‌روزرسانی مانده حساب مشتری/تامین‌کننده
        """
        payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.is_deleted == 0
        ).first()

        if not payment:
            raise HTTPException(status_code=404, detail="پرداخت یافت نشد")

        invoice = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="فاکتور یافت نشد")

        if invoice.status == 'cancelled':
            raise HTTPException(status_code=400, detail="فاکتور لغو شده است")

        # ✅ ۱. برگرداندن مبلغ به فاکتور
        invoice.paid_amount = max(0, (invoice.paid_amount or 0) - payment.amount)
        invoice.remaining_amount = (invoice.remaining_amount or 0) + payment.amount

        # ✅ ۲. اگر فاکتور paid بود و حالا مانده دارد، به confirmed برگردان
        if invoice.status == 'paid' and invoice.remaining_amount > 0:
            invoice.status = 'confirmed'

        # ✅ ۳. حذف پرداخت (soft delete)
        payment.is_deleted = 1
        payment.updated_by = user_id

        # ✅ ۴. به‌روزرسانی مانده حساب مشتری/تامین‌کننده
        AccountService.apply_invoice_accounting(db, invoice)

        db.commit()
        db.refresh(payment)
        db.refresh(invoice)

        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="delete",
            table_name="payments",
            record_id=payment_id,
            old_values={
                "amount": float(payment.amount),
                "invoice_id": payment.invoice_id
            },
            new_values={"status": "deleted"},
            ip_address=ip,
            user_agent=ua
        )

        return payment

    @staticmethod
    def update_invoice(
        db: Session,
        invoice_id: int,
        invoice_data: InvoiceUpdate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> Invoice:
        """به‌روزرسانی فاکتور (فقط در حالت draft)"""
        invoice = InvoiceService.get_invoice_by_id(db, invoice_id)

        if invoice.status != 'draft':
            raise HTTPException(status_code=400, detail="فقط فاکتورهای پیش‌نویس قابل ویرایش هستند")

        # به‌روزرسانی فیلدها
        if invoice_data.customer_id is not None:
            invoice.customer_id = invoice_data.customer_id
        if invoice_data.supplier_id is not None:
            invoice.supplier_id = invoice_data.supplier_id
        if invoice_data.due_date is not None:
            invoice.due_date = invoice_data.due_date
        if invoice_data.discount_amount is not None:
            invoice.discount_amount = invoice_data.discount_amount
        if invoice_data.discount_percent is not None:
            invoice.discount_percent = invoice_data.discount_percent
        if invoice_data.tax_percent is not None:
            invoice.tax_percent = invoice_data.tax_percent
        if invoice_data.notes is not None:
            invoice.notes = invoice_data.notes
        if invoice_data.is_official is not None:
            invoice.is_official = 1 if invoice_data.is_official else 0

        invoice.updated_by = user_id

        db.commit()
        db.refresh(invoice)

        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="update",
            table_name="invoices",
            record_id=invoice_id,
            new_values={"updated": True},
            ip_address=ip,
            user_agent=ua
        )

        return invoice
