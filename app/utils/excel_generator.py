"""
تولید فایل اکسل استاندارد با openpyxl
"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side, numbers


def create_excel_file(headers: list, data: list, sheet_name: str = "Sheet1") -> bytes:
    """
    ایجاد فایل اکسل استاندارد

    Args:
        headers: لیست عناوین ستون‌ها
        data: لیست لیست‌های داده (هر زیرلیست یک ردیف)
        sheet_name: نام شیت

    Returns:
        بایت‌های فایل اکسل
    """
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    # استایل‌ها
    header_fill = PatternFill(start_color="2563eb", end_color="2563eb", fill_type="solid")
    header_font = Font(name="Tahoma", bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    data_font = Font(name="Tahoma", size=10)
    data_align = Alignment(horizontal="center", vertical="center")
    number_align = Alignment(horizontal="left", vertical="center")

    thin_border = Border(
        left=Side(style='thin', color='000000'),
        right=Side(style='thin', color='000000'),
        top=Side(style='thin', color='000000'),
        bottom=Side(style='thin', color='000000')
    )

    # هدر
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align
        cell.border = thin_border

    # داده‌ها
    for row_idx, row_data in enumerate(data, 2):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = data_font
            cell.border = thin_border

            # فرمت عددی
            if isinstance(value, (int, float)):
                cell.alignment = number_align
                cell.number_format = '#,##0.00'
            else:
                cell.alignment = data_align

    # راست‌چین
    ws.sheet_properties.rightToLeft = True

    # عرض ستون‌ها (خودکار)
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

    # ذخیره در BytesIO
    buffer = BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    buffer.close()

    return excel_bytes
