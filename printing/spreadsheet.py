# -*- coding: utf-8 -*-
"""تصدير أمر العمل إلى ملف إكسل قابل للتعديل (ق-٥٧).

**الغرض بنصّ المستخدم:** «في بعض الحالات يتطلّب التعديل والحساب يدوياً بدون
الالتزام بحسابات البرنامج».

فهذا القالب يختلف عن قالبَي الطباعة اختلافاً جوهرياً: هو **ليس صورة للنتيجة بل
ورقة عمل حيّة**. الكميات والأسعار تُكتب **أرقاماً**، والكلفة **معادلة** لا رقماً
جامداً — فتعديل أي كمية يُحدِّث كلفتها ومجموعها في الإكسل نفسه بلا عودة إلى
البرنامج.

وهو **الوجهة الوحيدة التي تخرج فيها الأرقام من سيطرة المحرك** عمداً.
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from engine.workorder import WorkOrder

_HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
_HEAD_FONT = Font(bold=True, color="FFFFFF")
_TOTAL_FILL = PatternFill("solid", fgColor="F0F0F0")
_THIN = Side(style="thin", color="BBBBBB")
_BOX = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_MONEY = "#,##0"


def _sheet(workbook: Workbook, title: str):
    sheet = workbook.create_sheet(title)
    sheet.sheet_view.rightToLeft = True      # الورقة عربية الاتجاه
    return sheet


def _header(sheet, row: int, labels: list[str], widths: list[int]) -> None:
    for column, (label, width) in enumerate(zip(labels, widths), start=1):
        cell = sheet.cell(row, column, label)
        cell.font, cell.fill = _HEAD_FONT, _HEAD_FILL
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = _BOX
        sheet.column_dimensions[get_column_letter(column)].width = width


def build_workbook(order: WorkOrder, result: dict) -> Workbook:
    """يبني مصنَّف الإكسل: ورقة للترويسة وورقة للمواد وورقة للأجور."""
    workbook = Workbook()
    workbook.remove(workbook.active)

    _build_header_sheet(workbook, order, result)
    _build_materials_sheet(workbook, result)
    _build_labour_sheet(workbook, result)
    return workbook


def _build_header_sheet(workbook: Workbook, order: WorkOrder, result: dict) -> None:
    sheet = _sheet(workbook, "أمر العمل")
    sheet.column_dimensions["A"].width = 32
    sheet.column_dimensions["B"].width = 60

    rows = [
        ("أمر عمل رقم", order.number),
        ("التاريخ", order.order_date.strftime("%Y/%m/%d") if order.order_date else ""),
        ("التبويب", order.classification),
        ("اسم المشروع وموقعه", order.project_name),
        ("المدة اللازمة لتنفيذ العمل", order.duration),
        ("تاريخ المباشرة بالعمل",
         order.start_date.strftime("%Y/%m/%d") if order.start_date else ""),
        ("حجم العمل المخطط تنفيذه", order.work_scope),
        ("ملاحظات إضافية", order.notes),
        ("نسخة الأسعار", result.get("نسخة_الأسعار", "")),
    ]
    for index, (label, value) in enumerate(rows, start=1):
        key = sheet.cell(index, 1, label)
        key.font = Font(bold=True)
        key.fill = _TOTAL_FILL
        key.border = _BOX
        key.alignment = Alignment(horizontal="right")
        sheet.cell(index, 2, value).alignment = Alignment(
            horizontal="right", wrap_text=True
        )


def _build_materials_sheet(workbook: Workbook, result: dict) -> None:
    sheet = _sheet(workbook, "جدول المواد")
    _header(sheet, 1, ["ت", "اسم المادة", "الوحدة", "الكمية", "سعر الوحدة", "الكلفة"],
            [6, 46, 12, 12, 16, 18])

    row = 2
    for index, material in enumerate(result["المواد"], start=1):
        sheet.cell(row, 1, index)
        sheet.cell(row, 2, material["المادة"])
        sheet.cell(row, 3, material["الوحدة"])
        sheet.cell(row, 4, material["الكمية"])
        price = 0 if material["كمية_فقط"] else (material["سعر الوحدة"] or 0)
        sheet.cell(row, 5, price).number_format = _MONEY
        # **معادلة لا رقماً**: تعديل الكمية أو السعر يُحدّث الكلفة في الإكسل
        cost = sheet.cell(row, 6, f"=D{row}*E{row}")
        cost.number_format = _MONEY
        for column in range(1, 7):
            sheet.cell(row, column).border = _BOX
        row += 1

    _total(sheet, row, span=5, label="مجموع كلفة المواد",
           formula=f"=SUM(F2:F{row - 1})" if row > 2 else 0)
    sheet.freeze_panes = "A2"


def _build_labour_sheet(workbook: Workbook, result: dict) -> None:
    sheet = _sheet(workbook, "أجور العمل")
    _header(sheet, 1, ["ت", "الباب", "الفقرة", "الكمية", "الوحدة", "السعر", "الكلفة"],
            [6, 18, 46, 12, 14, 16, 18])

    row = 2
    for index, line in enumerate(result["أجور_العمل"], start=1):
        sheet.cell(row, 1, index)
        sheet.cell(row, 2, line.group or "الأعمال الكهربائية")
        sheet.cell(row, 3, line.name)
        sheet.cell(row, 4, line.qty)
        sheet.cell(row, 5, line.unit)
        sheet.cell(row, 6, line.rate or 0).number_format = _MONEY
        cost = sheet.cell(row, 7, f"=D{row}*F{row}")
        cost.number_format = _MONEY
        for column in range(1, 8):
            sheet.cell(row, column).border = _BOX
        row += 1

    _total(sheet, row, span=6, label="مجموع أجور التنفيذ",
           formula=f"=SUM(G2:G{row - 1})" if row > 2 else 0)
    sheet.freeze_panes = "A2"


def _total(sheet, row: int, span: int, label: str, formula) -> None:
    cell = sheet.cell(row, 1, label)
    cell.font = Font(bold=True)
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    total = sheet.cell(row, span + 1, formula)
    total.font = Font(bold=True)
    total.number_format = _MONEY
    for column in range(1, span + 2):
        sheet.cell(row, column).fill = _TOTAL_FILL
        sheet.cell(row, column).border = _BOX


def write_xlsx(order: WorkOrder, result: dict, path: str) -> str:
    """يكتب المصنَّف إلى المسار ويعيده."""
    if not path.lower().endswith(".xlsx"):
        path += ".xlsx"
    build_workbook(order, result).save(path)
    return path
