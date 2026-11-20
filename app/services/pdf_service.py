# app/services/pdf_service.py
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from datetime import datetime
import os

# ثبت فونت فارسی (از فونت‌های سیستمی ویندوز)
FONT_PATHS = [
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

def register_persian_font():
    """ثبت فونت فارسی"""
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('PersianFont', font_path))
                return 'PersianFont'
            except:
                continue
    return 'Helvetica'  # فونت پیش‌فرض

PERSIAN_FONT = register_persian_font()


def generate_invoice_pdf(invoice: dict, items: list) -> BytesIO:
    """تولید PDF فاکتور"""
    buffer = BytesIO()
    
    # تنظیمات صفحه
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # استایل‌ها
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName=PERSIAN_FONT
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        fontName=PERSIAN_FONT,
        alignment=TA_RIGHT
    )
    
    # محتوای PDF
    elements = []
    
    # عنوان
    elements.append(Paragraph("فاکتور فروش", title_style))
    elements.append(Spacer(1, 10))
    
    # اطلاعات فاکتور
    invoice_info = [
        ['شماره فاکتور:', invoice['invoice_number']],
        ['تاریخ:', invoice['issue_date'].strftime('%Y-%m-%d') if invoice['issue_date'] else ''],
        ['نوع:', 'فروش' if invoice['invoice_type'] == 'sale' else 'خرید'],
        ['وضعیت:', invoice['status']],
    ]
    
    invoice_table = Table(invoice_info, colWidths=[4*cm, 8*cm])
    invoice_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), PERSIAN_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
    ]))
    elements.append(invoice_table)
    elements.append(Spacer(1, 20))
    
    # جدول آیتم‌ها
    item_data = [['ردیف', 'شرح', 'تعداد', 'قیمت واحد', 'تخفیف', 'مبلغ کل']]
    
    for item in items:
        item_data.append([
            str(item['row_number']),
            item['description'] or '',
            str(item['quantity']),
            f"{item['unit_price']:,.0f}",
            f"{item['discount_amount']:,.0f}",
            f"{item['total_price']:,.0f}"
        ])
    
    item_table = Table(item_data, colWidths=[1.5*cm, 6*cm, 2*cm, 3*cm, 2.5*cm, 3*cm])
    item_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), PERSIAN_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(item_table)
    elements.append(Spacer(1, 20))
    
    # جمع کل
    totals = [
        ['جمع کل:', f"{invoice['subtotal']:,.0f}"],
        ['تخفیف:', f"{invoice['discount_amount']:,.0f}"],
        ['مالیات:', f"{invoice['tax_amount']:,.0f}"],
        ['مبلغ نهایی:', f"{invoice['total_amount']:,.0f}"],
    ]
    
    totals_table = Table(totals, colWidths=[6*cm, 6*cm])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), PERSIAN_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFC107')),
        ('FONTNAME', (0, -1), (-1, -1), PERSIAN_FONT),
        ('FONTSIZE', (0, -1), (-1, -1), 13),
    ]))
    elements.append(totals_table)
    
    # ساخت PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer