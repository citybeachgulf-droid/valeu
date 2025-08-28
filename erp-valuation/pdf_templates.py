from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors


def create_pdf(filename: str,
               title: str,
               client_name: str,
               date_str: str,
               doc_no: str,
               items: list,
               currency: str = 'ريال عماني') -> None:
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # العنوان
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 50, title)

    # بيانات العميل
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 100, f"العميل: {client_name}")
    c.drawString(50, height - 120, f"التاريخ: {date_str}")
    c.drawString(50, height - 140, f"رقم {title}: {doc_no}")

    # جدول العناصر
    data = [['المنتج/الخدمة', 'الكمية', 'سعر الوحدة', 'الإجمالي']]
    total = 0
    for item in items:
        qty = float(item.get('qty', 0) or 0)
        unit_price = float(item.get('unit_price', 0) or 0)
        total_item = qty * unit_price
        name = str(item.get('name', ''))
        data.append([name, str(int(qty) if qty.is_integer() else qty), f"{unit_price} {currency}", f"{total_item} {currency}"])
        total += total_item

    # إضافة المجموع الكلي
    data.append(['', '', 'المجموع الكلي', f"{total} {currency}"])

    # تصميم الجدول
    table = Table(data, colWidths=[200, 60, 80, 80])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ])
    table.setStyle(style)

    # رسم الجدول
    table.wrapOn(c, width, height)
    table.drawOn(c, 50, height - 350)

    c.save()
