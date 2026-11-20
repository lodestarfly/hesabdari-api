# app/services/report_service.py
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from app.models.customer import Customer, Supplier
from app.models.invoice import Invoice, InvoiceItem
from app.models.product import Product
from sqlalchemy import and_, func
from sqlalchemy.orm import Session


class ReportService:

    @staticmethod
    def get_sales_report(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = 'day'  # day, month, year
    ) -> dict:
        """گزارش فروش"""
        query = db.query(
            Invoice.issue_date,
            func.count(Invoice.id).label('invoice_count'),
            func.sum(Invoice.total_amount).label('total_sales'),
            func.sum(Invoice.paid_amount).label('total_paid'),
            func.sum(Invoice.remaining_amount).label('total_remaining')
        ).filter(
            Invoice.invoice_type == 'sale',
            Invoice.status != 'cancelled',
            Invoice.is_deleted == 0
        )

        if start_date:
            query = query.filter(Invoice.issue_date >= start_date)
        if end_date:
            query = query.filter(Invoice.issue_date <= end_date)

        # گروه‌بندی بر اساس تاریخ
        if group_by == 'day':
            query = query.group_by(func.date(Invoice.issue_date))
        elif group_by == 'month':
            query = query.group_by(func.year(Invoice.issue_date), func.month(Invoice.issue_date))
        else:
            query = query.group_by(func.year(Invoice.issue_date))

        results = query.order_by(Invoice.issue_date.desc()).all()

        return {
            'period': f"{start_date} to {end_date}" if start_date and end_date else "All time",
            'group_by': group_by,
            'data': [
                {
                    'date': row.issue_date.strftime('%Y-%m-%d') if group_by == 'day' else row.issue_date.strftime('%Y-%m'),
                    'invoice_count': row.invoice_count,
                    'total_sales': float(row.total_sales or 0),
                    'total_paid': float(row.total_paid or 0),
                    'total_remaining': float(row.total_remaining or 0)
                }
                for row in results
            ]
        }

    @staticmethod
    def get_inventory_report(db: Session, low_stock_only: bool = False) -> dict:
        """گزارش موجودی انبار"""
        query = db.query(
            Product.id,
            Product.code,
            Product.name,
            Product.unit,
            Product.stock_qty,
            Product.min_stock,
            Product.retail_price,
            Product.cost_price,
            Product.category_id
        ).filter(
            Product.is_deleted == 0,
            Product.is_active == True
        )

        if low_stock_only:
            query = query.filter(Product.stock_qty <= Product.min_stock)

        products = query.order_by(Product.name).all()

        total_value = sum(float(p.stock_qty * p.cost_price) for p in products)

        return {
            'total_products': len(products),
            'total_inventory_value': total_value,
            'low_stock_count': sum(1 for p in products if p.stock_qty <= p.min_stock),
            'products': [
                {
                    'id': p.id,
                    'code': p.code,
                    'name': p.name,
                    'unit': p.unit,
                    'stock_qty': float(p.stock_qty),
                    'min_stock': float(p.min_stock),
                    'retail_price': float(p.retail_price),
                    'cost_price': float(p.cost_price),
                    'stock_value': float(p.stock_qty * p.cost_price),
                    'is_low_stock': p.stock_qty <= p.min_stock
                }
                for p in products
            ]
        }

    @staticmethod
    def get_customer_balance_report(db: Session) -> dict:
        """گزارش مانده حساب مشتریان"""
        customers = db.query(
            Customer.id,
            Customer.name,
            Customer.customer_type,
            Customer.balance,
            Customer.credit_limit
        ).filter(
            Customer.is_deleted == 0,
            Customer.is_active == True,
            Customer.balance != 0
        ).order_by(Customer.balance.desc()).all()

        total_receivable = sum(float(c.balance) for c in customers)

        return {
            'total_customers_with_balance': len(customers),
            'total_receivable': total_receivable,
            'customers': [
                {
                    'id': c.id,
                    'name': c.name,
                    'type': c.customer_type,
                    'balance': float(c.balance),
                    'credit_limit': float(c.credit_limit),
                    'credit_usage_percent': (float(c.balance) / float(c.credit_limit) * 100) if c.credit_limit > 0 else 0
                }
                for c in customers
            ]
        }

    @staticmethod
    def get_supplier_balance_report(db: Session) -> dict:
        """گزارش مانده حساب تامین‌کنندگان"""
        from app.models.invoice import Invoice
        from app.models.supplier import Supplier

        suppliers = db.query(Supplier).filter(
            Supplier.is_deleted == 0,
            Supplier.is_active == True
        ).all()

        supplier_balances = []
        total_payable = 0
        suppliers_with_balance = 0

        for supplier in suppliers:
            invoices = db.query(Invoice).filter(
                Invoice.supplier_id == supplier.id,
                Invoice.is_deleted == 0,
                Invoice.invoice_type == 'purchase',
                Invoice.status.in_(['confirmed', 'paid'])
            ).all()

            balance = sum(inv.remaining_amount for inv in invoices)

            if balance > 0:
                suppliers_with_balance += 1
                total_payable += balance

            supplier_balances.append({
                "id": supplier.id,
                "name": supplier.name,
                "balance": balance,
            })

        return {
            "total_suppliers_with_balance": suppliers_with_balance,
            "total_payable": total_payable,
            "suppliers": supplier_balances
        }

    @staticmethod
    def get_profit_loss_report(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict:
        """گزارش سود و زیان ساده"""
        # فروش
        sales_query = db.query(
            func.sum(Invoice.total_amount).label('total_sales')
        ).filter(
            Invoice.invoice_type == 'sale',
            Invoice.status != 'cancelled',
            Invoice.is_deleted == 0
        )

        if start_date:
            sales_query = sales_query.filter(Invoice.issue_date >= start_date)
        if end_date:
            sales_query = sales_query.filter(Invoice.issue_date <= end_date)

        total_sales = sales_query.scalar() or 0

        # خرید
        purchases_query = db.query(
            func.sum(Invoice.total_amount).label('total_purchases')
        ).filter(
            Invoice.invoice_type == 'purchase',
            Invoice.status != 'cancelled',
            Invoice.is_deleted == 0
        )

        if start_date:
            purchases_query = purchases_query.filter(Invoice.issue_date >= start_date)
        if end_date:
            purchases_query = purchases_query.filter(Invoice.issue_date <= end_date)

        total_purchases = purchases_query.scalar() or 0

        # سود ناخالص
        gross_profit = total_sales - total_purchases

        return {
            'period': f"{start_date} to {end_date}" if start_date and end_date else "All time",
            'total_sales': float(total_sales),
            'total_purchases': float(total_purchases),
            'gross_profit': float(gross_profit),
            'profit_margin': (float(gross_profit) / float(total_sales) * 100) if total_sales > 0 else 0
        }
