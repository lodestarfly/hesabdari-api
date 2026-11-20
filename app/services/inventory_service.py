"""
سرویس مدیریت موجودی انبار
- افزایش موجودی هنگام خرید
- کاهش موجودی هنگام فروش
- برگرداندن موجودی هنگام لغو فاکتور
"""
from decimal import Decimal

from app.models.invoice import Invoice, InvoiceItem
from app.models.product import Product
from fastapi import HTTPException
from sqlalchemy.orm import Session


class InventoryService:

    @staticmethod
    def increase_stock(db: Session, product_id: int, quantity: Decimal, reason: str = "") -> bool:
        """افزایش موجودی (خرید یا برگشت از فروش)"""
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.is_deleted == 0
        ).first()

        if not product:
            return False

        product.stock_qty = (product.stock_qty or 0) + quantity
        db.commit()
        return True

    @staticmethod
    def decrease_stock(db: Session, product_id: int, quantity: Decimal, reason: str = "") -> bool:
        """کاهش موجودی (فروش یا برگشت از خرید)"""
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.is_deleted == 0
        ).first()

        if not product:
            return False

        new_stock = (product.stock_qty or 0) - quantity
        if new_stock < 0:
            return False  # موجودی کافی نیست

        product.stock_qty = new_stock
        db.commit()
        return True

    @staticmethod
    def apply_invoice_inventory(db: Session, invoice: Invoice) -> bool:
        """اعمال تغییرات موجودی برای فاکتور"""
        if invoice.invoice_type == 'purchase':
            # خرید → افزایش موجودی
            for item in invoice.items:
                if item.is_deleted == 0:
                    InventoryService.increase_stock(
                        db, item.product_id, item.quantity,
                        reason=f"فاکتور خرید {invoice.invoice_number}"
                    )
        elif invoice.invoice_type in ['sale', 'proforma']:
            # فروش → کاهش موجودی
            for item in invoice.items:
                if item.is_deleted == 0:
                    if not InventoryService.decrease_stock(
                        db, item.product_id, item.quantity,
                        reason=f"فاکتور فروش {invoice.invoice_number}"
                    ):
                        raise HTTPException(
                            status_code=400,
                            detail=f"موجودی کافی نیست برای محصول {item.product_id}"
                        )
        return True

    @staticmethod
    def reverse_invoice_inventory(db: Session, invoice: Invoice) -> bool:
        """برگرداندن تغییرات موجودی (لغو فاکتور)"""
        if invoice.invoice_type == 'purchase':
            # لغو خرید → کاهش موجودی
            for item in invoice.items:
                if item.is_deleted == 0:
                    InventoryService.decrease_stock(
                        db, item.product_id, item.quantity,
                        reason=f"لغو فاکتور خرید {invoice.invoice_number}"
                    )
        elif invoice.invoice_type in ['sale', 'proforma']:
            # لغو فروش → افزایش موجودی
            for item in invoice.items:
                if item.is_deleted == 0:
                    InventoryService.increase_stock(
                        db, item.product_id, item.quantity,
                        reason=f"لغو فاکتور فروش {invoice.invoice_number}"
                    )
        return True
