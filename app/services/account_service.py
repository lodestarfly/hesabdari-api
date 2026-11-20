"""
سرویس مدیریت حساب‌ها و تراز
- به‌روزرسانی مانده مشتری/تامین‌کننده
- مدیریت پرداخت‌ها
- تراز حساب‌ها
"""
from decimal import Decimal

from app.models.customer import (  # ✅ Supplier از customer.py import می‌شود
    Customer, Supplier)
from app.models.invoice import Invoice
from app.models.payment import Payment
from sqlalchemy import func
from sqlalchemy.orm import Session


class AccountService:

    @staticmethod
    def update_customer_balance(db: Session, customer_id: int) -> None:
        """به‌روزرسانی مانده حساب مشتری"""
        if not customer_id:
            return

        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return

        # مجموع فاکتورهای فروش فعال
        total_invoices = db.query(
            func.coalesce(func.sum(Invoice.total_amount), 0)
        ).filter(
            Invoice.customer_id == customer_id,
            Invoice.is_deleted == 0,
            Invoice.invoice_type.in_(['sale', 'proforma']),
            Invoice.status != 'cancelled'
        ).scalar()

        # مجموع پرداخت‌های فعال
        total_payments = db.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).join(Invoice).filter(
            Invoice.customer_id == customer_id,
            Invoice.is_deleted == 0,
            Invoice.invoice_type.in_(['sale', 'proforma']),
            Invoice.status != 'cancelled',
            Payment.is_deleted == 0
        ).scalar()

        customer.balance = Decimal(str(total_invoices)) - Decimal(str(total_payments))
        db.commit()

    @staticmethod
    def update_supplier_balance(db: Session, supplier_id: int) -> None:
        """به‌روزرسانی مانده حساب تامین‌کننده"""
        if not supplier_id:
            return

        supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            return

        # مجموع فاکتورهای خرید فعال
        total_invoices = db.query(
            func.coalesce(func.sum(Invoice.total_amount), 0)
        ).filter(
            Invoice.supplier_id == supplier_id,
            Invoice.is_deleted == 0,
            Invoice.invoice_type == 'purchase',
            Invoice.status != 'cancelled'
        ).scalar()

        # مجموع پرداخت‌های فعال
        total_payments = db.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).join(Invoice).filter(
            Invoice.supplier_id == supplier_id,
            Invoice.is_deleted == 0,
            Invoice.invoice_type == 'purchase',
            Invoice.status != 'cancelled',
            Payment.is_deleted == 0
        ).scalar()

        supplier.balance = Decimal(str(total_invoices)) - Decimal(str(total_payments))
        db.commit()

    @staticmethod
    def apply_invoice_accounting(db: Session, invoice: Invoice) -> None:
        """اعمال حسابداری فاکتور (به‌روزرسانی مانده)"""
        if invoice.customer_id:
            AccountService.update_customer_balance(db, invoice.customer_id)
        if invoice.supplier_id:
            AccountService.update_supplier_balance(db, invoice.supplier_id)

    @staticmethod
    def reverse_invoice_accounting(db: Session, invoice: Invoice) -> None:
        """برگرداندن حسابداری فاکتور (لغو)"""
        if invoice.customer_id:
            AccountService.update_customer_balance(db, invoice.customer_id)
        if invoice.supplier_id:
            AccountService.update_supplier_balance(db, invoice.supplier_id)

    @staticmethod
    def get_account_balance(db: Session, account_type: str, account_id: int) -> dict:
        """دریافت تراز حساب"""
        if account_type == 'customer':
            account = db.query(Customer).filter(Customer.id == account_id).first()
            if not account:
                return {"error": "مشتری یافت نشد"}

            invoices = db.query(Invoice).filter(
                Invoice.customer_id == account_id,
                Invoice.is_deleted == 0,
                Invoice.status != 'cancelled'
            ).all()

            payments = db.query(Payment).join(Invoice).filter(
                Invoice.customer_id == account_id,
                Invoice.is_deleted == 0,
                Invoice.status != 'cancelled',
                Payment.is_deleted == 0
            ).all()

            total_invoices = sum(float(inv.total_amount) for inv in invoices)
            total_payments = sum(float(p.amount) for p in payments)

            return {
                "account_type": "customer",
                "account_name": account.name,
                "total_invoices": total_invoices,
                "total_payments": total_payments,
                "balance": float(account.balance or 0),
                "is_creditor": (account.balance or 0) > 0,
                "is_debtor": (account.balance or 0) < 0,
            }

        elif account_type == 'supplier':
            account = db.query(Supplier).filter(Supplier.id == account_id).first()
            if not account:
                return {"error": "تامین‌کننده یافت نشد"}

            invoices = db.query(Invoice).filter(
                Invoice.supplier_id == account_id,
                Invoice.is_deleted == 0,
                Invoice.status != 'cancelled'
            ).all()

            payments = db.query(Payment).join(Invoice).filter(
                Invoice.supplier_id == account_id,
                Invoice.is_deleted == 0,
                Invoice.status != 'cancelled',
                Payment.is_deleted == 0
            ).all()

            total_invoices = sum(float(inv.total_amount) for inv in invoices)
            total_payments = sum(float(p.amount) for p in payments)

            return {
                "account_type": "supplier",
                "account_name": account.name,
                "total_invoices": total_invoices,
                "total_payments": total_payments,
                "balance": float(account.balance or 0),
                "is_creditor": (account.balance or 0) > 0,
                "is_debtor": (account.balance or 0) < 0,
            }

        return {"error": "نوع حساب نامعتبر است"}
