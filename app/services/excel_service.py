# app/services/excel_service.py
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime


def generate_sales_excel(report_data: dict) -> BytesIO:
    """تولید Excel گزارش فروش"""
    wb = Workbook()
    ws = wb.active
    ws.title = "گزارش فروش"
    
    # استایل هدر
    header_fill = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    
    # هدر
    headers = ['تاریخ', 'تعداد فاکتور', 'جمع فروش', 'مبلغ پرداختی', 'مانده']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
    
    # داده‌ها
    for row_idx, row_data in enumerate(report_data['data'], 2):
        ws.cell(row=row_idx, column=1, value=row_data['date'])
        ws.cell(row=row_idx, column=2, value=row_data['invoice_count'])
        ws.cell(row=row_idx, column=3, value=row_data['total_sales'])
        ws.cell(row=row_idx, column=4, value=row_data['total_paid'])
        ws.cell(row=row_idx, column=5, value=row_data['total_remaining'])
    
    # تنظیم عرض ستون‌ها
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 20
    
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    return buffer


def generate_inventory_excel(report_data: dict) -> BytesIO:
    """تولید Excel گزارش موجودی"""
    wb = Workbook()
    ws = wb.active
    ws.title = "موجودی انبار"
    
    header_fill = PatternFill(start_color="2196F3", end_color="2196F3", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    
    headers = ['کد', 'نام محصول', 'واحد', 'موجودی', 'حداقل', 'قیمت خرید', 'ارزش موجودی', 'وضعیت']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
    
    for row_idx, product in enumerate(report_data['products'], 2):
        ws.cell(row=row_idx, column=1, value=product['code'])
        ws.cell(row=row_idx, column=2, value=product['name'])
        ws.cell(row=row_idx, column=3, value=product['unit'])
        ws.cell(row=row_idx, column=4, value=product['stock_qty'])
        ws.cell(row=row_idx, column=5, value=product['min_stock'])
        ws.cell(row=row_idx, column=6, value=product['cost_price'])
        ws.cell(row=row_idx, column=7, value=product['stock_value'])
        ws.cell(row=row_idx, column=8, value='کم' if product['is_low_stock'] else 'نرمال')
    
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 18
    ws.column_dimensions['H'].width = 12
    
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    return buffer