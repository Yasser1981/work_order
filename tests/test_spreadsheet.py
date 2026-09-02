# -*- coding: utf-8 -*-
"""اختبارات قالب الإكسل — ورقة عمل حيّة تحاكي النموذج المطبوع (ق-٥٧، ق-٧١)."""

import re
from datetime import date

import pytest

openpyxl = pytest.importorskip("openpyxl", reason="openpyxl غير مثبَّت")

from engine import load_catalog  # noqa: E402
from engine.overhead import compute  # noqa: E402
from engine.types import Network11kV, OverheadProject  # noqa: E402
from engine.workorder import WorkOrder  # noqa: E402
from printing.spreadsheet import (  # noqa: E402
    LABOUR_SHEET,
    ORDER_SHEET,
    build_workbook,
    write_xlsx,
)


@pytest.fixture(scope="module")
def result():
    project = OverheadProject(
        net11=Network11kV(route_length_m=500, poles_lattice=5, poles_round=16,
                          stay_rod_sets=2)
    )
    return compute(project, load_catalog())


@pytest.fixture
def order():
    wo = WorkOrder(number="45", order_date=date(2026, 9, 2), classification="توسعات",
                   project_name="مشروع اختباري", duration="90 يوم",
                   start_date=None, notes="ملاحظة")
    wo.staff[0].count, wo.staff[0].days = 1, 90      # مهندس
    wo.equipment[2].count, wo.equipment[2].days = 2, 45   # رافعة
    return wo


@pytest.fixture
def sheets(order, result):
    book = build_workbook(order, result)
    return book, book[ORDER_SHEET], book[LABOUR_SHEET]


def _column(sheet, column: int) -> list:
    return [sheet.cell(r, column).value for r in range(1, sheet.max_row + 1)]


def _row_of(sheet, column: int, text: str) -> int:
    for row in range(1, sheet.max_row + 1):
        if sheet.cell(row, column).value == text:
            return row
    raise AssertionError(f"لا خلية فيها «{text}» في العمود {column}")


# ═══════════════ ١. البنية: ورقتان تحاكيان المطبوع ═══════════════


def test_the_workbook_has_the_order_sheet_and_the_labour_sheet(sheets):
    book, _, _ = sheets
    assert book.sheetnames == [ORDER_SHEET, LABOUR_SHEET]


def test_both_sheets_are_right_to_left(sheets):
    """إكسل يقلب الأعمدة بنفسه، فالعمود A يظهر أقصى اليمين — كـ«ت» في المطبوع."""
    _, order_sheet, labour = sheets
    assert order_sheet.sheet_view.rightToLeft is True
    assert labour.sheet_view.rightToLeft is True


def test_the_order_sheet_mirrors_the_printed_form(sheets, order):
    """الترويسة الرسمية والأقسام الثلاثة والتواقيع — كما في نموذج الإيزو."""
    _, sheet, _ = sheets
    first = _column(sheet, 1)
    side = _column(sheet, 8)

    assert order.organisation in first
    assert order.branch in first
    assert f"أمر عمل رقم {order.number}" in first
    for label in ("التبويب", "اسم المشروع وموقعه", "المدة اللازمة لتنفيذ العمل",
                  "الكلفة التخمينية للمواد + العمل", "حجم العمل المخطط تنفيذه",
                  "تاريخ المباشرة بالعمل", "أ - جدول المواد المخمنة"):
        assert label in first, label
    for label in ("ب - الاشراف الفني", "ج - الاليات والمعدات", "ملاحظات إضافية"):
        assert label in side, label


def test_the_side_tables_sit_beside_the_materials_not_below(sheets):
    """**نظير ق-٦٨:** الإشراف يبدأ في الصفّ نفسه الذي يبدأ فيه جدول المواد."""
    _, sheet, _ = sheets
    assert _row_of(sheet, 1, "أ - جدول المواد المخمنة") == \
        _row_of(sheet, 8, "ب - الاشراف الفني")


def test_the_five_signature_titles_close_the_sheet(sheets):
    """نظير ق-٦٦ — والأسماء تُقرأ من مصدر واحد مع المطبوع، فلا يفترقان."""
    from printing.iso_form import SIGNATURES

    _, sheet, _ = sheets
    row = _row_of(sheet, 1, SIGNATURES[0])
    placed = [sheet.cell(row, 1 + i * 2).value for i in range(len(SIGNATURES))]
    assert placed == list(SIGNATURES)
    assert sheet.cell(row + 1, 1).value.startswith(".")


def test_zero_rows_are_left_out_of_the_side_tables(sheets, order):
    """نظير ق-٦٤: المُدخَل وحده يُطبع."""
    _, sheet, _ = sheets
    names = _column(sheet, 9)
    assert "مهندس" in names and "رافعة" in names
    for absent in ("فني", "سائق", "محاسب", "كرين", "شفل", "بيكب حمل"):
        assert absent not in names, absent


# ═══════════════ ٢. الحياة: معادلات لا أرقام جامدة ═══════════════


def test_each_material_cost_is_a_formula(sheets):
    """تعديل الكمية أو السعر يُحدّث الكلفة داخل الإكسل — كلّ الغرض (ق-٥٧)."""
    _, sheet, _ = sheets
    head = _row_of(sheet, 1, "ت")
    first = head + 1
    assert sheet.cell(first, 6).value == f"=D{first}*E{first}"


def test_each_labour_cost_is_a_formula(sheets):
    _, _, labour = sheets
    assert labour.cell(2, 7).value == "=D2*F2"


def test_the_totals_are_sums_not_numbers(sheets):
    _, sheet, labour = sheets
    materials_total = _row_of(sheet, 1, "مجموع كلفة المواد")
    assert str(sheet.cell(materials_total, 6).value).startswith("=SUM(F")
    labour_total = _row_of(labour, 1, "مجموع أجور التنفيذ")
    assert str(labour.cell(labour_total, 7).value).startswith("=SUM(G")


# ═══════════════ ٣. سطر الكلفة يشير إلى الخليتين الصحيحتين ═══════════════


@pytest.mark.parametrize("lattice,round_", [(1, 0), (5, 16), (9, 32)])
def test_the_cost_line_points_at_the_two_total_cells(order, lattice, round_):
    """**الحارس الأهمّ في هذا القالب (ق-٧١):** المرجع يتبع عدد المواد.

    سطر الكلفة يشير إلى صفّ مجموع المواد بالاسم (`F43` مثلاً)، وموضع ذلك الصفّ
    **يتغيّر بعدد المواد**. فخطأ إزاحة واحد يجعل الترويسة تعرض كلفة سطرٍ من
    الجدول بدل المجموع — **رقمٌ معقول المظهر وخاطئ تماماً**، ولا شيء في الورقة
    يدلّ عليه.

    فيُفحص على ثلاثة أحجام مشاريع: أن الخلية التي يسمّيها المرجع هي فعلاً
    خلية `SUM`.
    """
    res = compute(OverheadProject(net11=Network11kV(
        route_length_m=500, poles_lattice=lattice, poles_round=round_)), load_catalog())
    book = build_workbook(order, res)
    sheet, labour = book[ORDER_SHEET], book[LABOUR_SHEET]

    formula = sheet.cell(_row_of(sheet, 1, "الكلفة التخمينية للمواد + العمل"), 2).value
    assert formula.startswith("=")

    materials_ref = re.search(r"TEXT\(F(\d+),", formula)
    labour_ref = re.search(r"TEXT\('([^']+)'!G(\d+),", formula)
    assert materials_ref and labour_ref, formula

    assert str(sheet.cell(int(materials_ref.group(1)), 6).value).startswith("=SUM(")
    assert labour_ref.group(1) == LABOUR_SHEET
    assert str(labour.cell(int(labour_ref.group(2)), 7).value).startswith("=SUM(")


def test_the_cost_line_reads_like_the_printed_one(sheets):
    """نصّ ق-٦٥ نفسه — لكن أرقامه من الخلايا لا مطبوعة فيه."""
    _, sheet, _ = sheets
    formula = sheet.cell(_row_of(sheet, 1, "الكلفة التخمينية للمواد + العمل"), 2).value
    for part in ("كلفة المواد التخمينية", "كلفة العمل التخمينية",
                 "الكلفة التخمينية الكلية", "د.ع"):
        assert part in formula, part
    # ولا رقم مطبوع في السطر: الأرقام كلها مراجع
    assert not re.search(r'"\s*\d[\d,]{3,}', formula), formula


# ═══════════════ ٤. الكتابة إلى القرص ═══════════════


def test_the_file_is_written_and_reopens(order, result, tmp_path):
    path = write_xlsx(order, result, str(tmp_path / "أمر"))
    assert path.endswith(".xlsx")
    book = openpyxl.load_workbook(path)
    assert book.sheetnames == [ORDER_SHEET, LABOUR_SHEET]
