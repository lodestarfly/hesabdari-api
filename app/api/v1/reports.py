from datetime import datetime
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/sales")
def sales_report(
    group_by: str = 'month',
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    export_format: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """گزارش فروش"""
    from app.models.invoice import Invoice
    from app.utils.excel_generator import create_excel_file
    from fastapi import Response

    query = db.query(Invoice).filter(
        Invoice.is_deleted == 0,
        Invoice.invoice_type == 'sale',
        Invoice.status.in_(['confirmed', 'paid'])
    )

    if start_date:
        query = query.filter(Invoice.issue_date >= start_date)
    if end_date:
        query = query.filter(Invoice.issue_date <= end_date)

    invoices = query.all()

    # گروه‌بندی
    report_data = {}
    for inv in invoices:
        if inv.issue_date is None:
            key = 'unknown'
        elif group_by == 'day':
            key = inv.issue_date.strftime('%Y-%m-%d')
        elif group_by == 'month':
            key = inv.issue_date.strftime('%Y-%m')
        else:
            key = inv.issue_date.strftime('%Y')

        if key not in report_data:
            report_data[key] = {
                'date': key,
                'invoice_count': 0,
                'total_sales': 0,
                'total_paid': 0,
                'total_remaining': 0
            }

        report_data[key]['invoice_count'] += 1
        report_data[key]['total_sales'] += float(inv.total_amount or 0)
        report_data[key]['total_paid'] += float(inv.paid_amount or 0)
        report_data[key]['total_remaining'] += float(inv.remaining_amount or 0)

    data_list = list(report_data.values())

    # ========== خروجی Excel ==========
    if export_format == 'excel':
        headers = ['تاریخ', 'تعداد فاکتور', 'جمع فروش (تومان)', 'دریافتی (تومان)', 'مانده (تومان)']

        data_rows = []
        for row in data_list:
            data_rows.append([
                row['date'],
                row['invoice_count'],
                row['total_sales'],
                row['total_paid'],
                row['total_remaining']
            ])

        excel_bytes = create_excel_file(headers, data_rows, "گزارش فروش")

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=sales_report.xlsx",
                "Content-Length": str(len(excel_bytes))
            }
        )

    # ========== خروجی JSON ==========
    return {
        'period': f"{start_date} to {end_date}" if start_date and end_date else 'all',
        'group_by': group_by,
        'data': data_list
    }


@router.get("/inventory")
def inventory_report(
    low_stock_only: bool = False,
    export_format: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """گزارش موجودی انبار (JSON یا Excel)"""
    from io import BytesIO

    from app.models.product import Product
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    query = db.query(Product).filter(Product.is_deleted == 0)

    if low_stock_only:
        query = query.filter(Product.stock_qty <= Product.min_stock)

    products = query.all()

    product_list = []
    total_value = 0
    low_stock_count = 0

    for product in products:
        stock_qty = float(product.stock_qty or 0)
        cost_price = float(product.cost_price or 0)
        stock_value = stock_qty * cost_price
        total_value += stock_value

        min_stock = float(product.min_stock or 0)
        is_low = stock_qty <= min_stock
        if is_low:
            low_stock_count += 1

        product_list.append({
            "id": product.id,
            "code": product.code,
            "name": product.name,
            "unit": product.unit,
            "stock_qty": stock_qty,
            "min_stock": min_stock,
            "retail_price": float(product.retail_price or 0),
            "cost_price": cost_price,
            "stock_value": stock_value,
            "is_low_stock": is_low
        })

    # ========== خروجی Excel ==========
    if export_format == 'excel':
        wb = Workbook()
        ws = wb.active
        ws.title = "موجودی انبار"

        header_fill = PatternFill(start_color="2563eb", end_color="2563eb", fill_type="solid")
        header_font = Font(name="Tahoma", bold=True, color="FFFFFF", size=11)
        header_align = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        headers = ['کد', 'نام محصول', 'واحد', 'موجودی', 'حداقل', 'قیمت خرید', 'قیمت فروش', 'ارزش موجودی', 'وضعیت']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            cell.border = thin_border

        data_font = Font(name="Tahoma", size=10)
        data_align = Alignment(horizontal="center", vertical="center")
        number_align = Alignment(horizontal="left", vertical="center")

        for row_idx, p in enumerate(product_list, 2):
            ws.cell(row=row_idx, column=1, value=p['code']).font = data_font
            ws.cell(row=row_idx, column=1).alignment = data_align
            ws.cell(row=row_idx, column=1).border = thin_border

            ws.cell(row=row_idx, column=2, value=p['name']).font = data_font
            ws.cell(row=row_idx, column=2).alignment = Alignment(horizontal="right", vertical="center")
            ws.cell(row=row_idx, column=2).border = thin_border

            ws.cell(row=row_idx, column=3, value=p['unit']).font = data_font
            ws.cell(row=row_idx, column=3).alignment = data_align
            ws.cell(row=row_idx, column=3).border = thin_border

            ws.cell(row=row_idx, column=4, value=p['stock_qty']).font = data_font
            ws.cell(row=row_idx, column=4).alignment = data_align
            ws.cell(row=row_idx, column=4).border = thin_border

            ws.cell(row=row_idx, column=5, value=p['min_stock']).font = data_font
            ws.cell(row=row_idx, column=5).alignment = data_align
            ws.cell(row=row_idx, column=5).border = thin_border

            ws.cell(row=row_idx, column=6, value=p['cost_price']).font = data_font
            ws.cell(row=row_idx, column=6).alignment = number_align
            ws.cell(row=row_idx, column=6).number_format = '#,##0'
            ws.cell(row=row_idx, column=6).border = thin_border

            ws.cell(row=row_idx, column=7, value=p['retail_price']).font = data_font
            ws.cell(row=row_idx, column=7).alignment = number_align
            ws.cell(row=row_idx, column=7).number_format = '#,##0'
            ws.cell(row=row_idx, column=7).border = thin_border

            ws.cell(row=row_idx, column=8, value=p['stock_value']).font = data_font
            ws.cell(row=row_idx, column=8).alignment = number_align
            ws.cell(row=row_idx, column=8).number_format = '#,##0'
            ws.cell(row=row_idx, column=8).border = thin_border

            ws.cell(row=row_idx, column=9, value='موجودی کم' if p['is_low_stock'] else 'نرمال').font = data_font
            ws.cell(row=row_idx, column=9).alignment = data_align
            ws.cell(row=row_idx, column=9).border = thin_border

        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 25
        ws.column_dimensions['C'].width = 10
        ws.column_dimensions['D'].width = 12
        ws.column_dimensions['E'].width = 12
        ws.column_dimensions['F'].width = 15
        ws.column_dimensions['G'].width = 15
        ws.column_dimensions['H'].width = 18
        ws.column_dimensions['I'].width = 12

        ws.sheet_properties.rightToLeft = True

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=inventory_report.xlsx"}
        )

    # ========== خروجی JSON ==========
    return {
        "total_products": len(products),
        "total_inventory_value": total_value,
        "low_stock_count": low_stock_count,
        "products": product_list
    }


@router.get("/customer-balance")
def customer_balance_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """گزارش مانده حساب مشتریان"""
    from app.models.customer import Customer
    from app.models.invoice import Invoice

    customers = db.query(Customer).filter(
        Customer.is_deleted == 0,
        Customer.is_active == True
    ).all()

    customer_balances = []
    total_receivable = 0
    customers_with_balance = 0

    for customer in customers:
        invoices = db.query(Invoice).filter(
            Invoice.customer_id == customer.id,
            Invoice.is_deleted == 0,
            Invoice.invoice_type == 'sale',
            Invoice.status.in_(['confirmed', 'paid'])
        ).all()

        balance = sum(float(inv.remaining_amount or 0) for inv in invoices)

        if balance > 0:
            customers_with_balance += 1
            total_receivable += balance

        credit_usage_percent = 0
        if customer.credit_limit and float(customer.credit_limit) > 0:
            credit_usage_percent = (balance / float(customer.credit_limit)) * 100

        customer_balances.append({
            "id": customer.id,
            "name": customer.name,
            "type": customer.customer_type,
            "balance": balance,
            "credit_limit": float(customer.credit_limit or 0),
            "credit_usage_percent": round(credit_usage_percent, 2)
        })

    return {
        "total_customers_with_balance": customers_with_balance,
        "total_receivable": total_receivable,
        "customers": customer_balances
    }


@router.get("/supplier-balance")
def supplier_balance_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """گزارش مانده حساب تامین‌کنندگان"""
    from app.models.customer import Supplier
    from app.models.invoice import Invoice

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

        balance = sum(float(inv.remaining_amount or 0) for inv in invoices)

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


@router.get("/inventory")
def inventory_report(
    low_stock_only: bool = False,
    export_format: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """گزارش موجودی انبار"""
    from app.models.product import Product

    query = db.query(Product).filter(Product.is_deleted == 0)

    if low_stock_only:
        query = query.filter(Product.stock_qty <= Product.min_stock)

    products = query.all()

    product_list = []
    total_value = 0
    low_stock_count = 0

    for product in products:
        stock_qty = float(product.stock_qty or 0)
        cost_price = float(product.cost_price or 0)
        stock_value = stock_qty * cost_price
        total_value += stock_value

        min_stock = float(product.min_stock or 0)
        is_low = stock_qty <= min_stock
        if is_low:
            low_stock_count += 1

        product_list.append({
            "id": product.id,
            "code": product.code,
            "name": product.name,
            "unit": product.unit,
            "stock_qty": stock_qty,
            "min_stock": min_stock,
            "retail_price": float(product.retail_price or 0),
            "cost_price": cost_price,
            "stock_value": stock_value,
            "is_low_stock": is_low
        })

    return {
        "total_products": len(products),
        "total_inventory_value": total_value,
        "low_stock_count": low_stock_count,
        "products": product_list
    }


@router.get("/profit-loss")
def profit_loss_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """گزارش سود و زیان"""
    from app.models.invoice import Invoice

    sales_query = db.query(Invoice).filter(
        Invoice.is_deleted == 0,
        Invoice.invoice_type == 'sale',
        Invoice.status.in_(['confirmed', 'paid'])
    )

    purchases_query = db.query(Invoice).filter(
        Invoice.is_deleted == 0,
        Invoice.invoice_type == 'purchase',
        Invoice.status.in_(['confirmed', 'paid'])
    )

    if start_date:
        sales_query = sales_query.filter(Invoice.issue_date >= start_date)
        purchases_query = purchases_query.filter(Invoice.issue_date >= start_date)
    if end_date:
        sales_query = sales_query.filter(Invoice.issue_date <= end_date)
        purchases_query = purchases_query.filter(Invoice.issue_date <= end_date)

    total_sales = sum(float(inv.total_amount or 0) for inv in sales_query.all())
    total_purchases = sum(float(inv.total_amount or 0) for inv in purchases_query.all())
    gross_profit = total_sales - total_purchases
    profit_margin = (gross_profit / total_sales * 100) if total_sales > 0 else 0

    return {
        "period": f"{start_date} to {end_date}" if start_date and end_date else 'all',
        "total_sales": total_sales,
        "total_purchases": total_purchases,
        "gross_profit": gross_profit,
        "profit_margin": profit_margin
    }
