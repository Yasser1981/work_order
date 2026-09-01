# -*- coding: utf-8 -*-
"""اختبارات قالب الإيزو الرسمي — MOE / D6-FO-30."""

import re
from datetime import date

import pytest

from engine import load_catalog
from engine.overhead import compute
from engine.types import CircuitType, Network11kV, Network33kV, OverheadProject
from engine.workorder import WorkOrder
from printing.iso_form import build_html


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def result(catalog):
    project = OverheadProject(
        net11=Network11kV(route_length_m=500, poles_lattice=5, poles_round=16,
                          stay_rod_sets=2),
        net33=Network33kV(route_length_m=2000, poles_suspension=27, anchors_mid=3,
                          anchors_end=2, circuit=CircuitType.DOUBLE, stay_rod_sets=3),
    )
    return compute(project, catalog)


@pytest.fixture
def order():
    return WorkOrder(
        number="45",
        order_date=date(2026, 8, 18),
        classification="توسعات",
        project_name="تجهيز ونصب شبكة 33 و11 ك.ف",
        duration="90 يوم",
        start_date=date(2026, 9, 1),
    )


def _material_rows(html_text: str) -> list[str]:
    """أسطر بيانات جدول المواد وحده — بين عنوان القسم أ وعنوان القسم ب.

    الاستبعاد بـ (?!<th) يكفي لإسقاط سطر العناوين — بلا اقتطاع إضافي.
    """
    section = html_text.split("أ - جدول المواد المخمنة")[1].split("ب - الاشراف")[0]
    return re.findall(r"<tr>(?!<th).*?</tr>", section, flags=re.S)


# ═══════════════════════ محتوى جدول المواد ═══════════════════════


def test_every_material_with_quantity_is_printed(order, result):
    """لا تُقطع أي مادة — الملف الأصلي كان يقطع ما زاد عن 35 بلا تحذير."""
    expected = [row for row in result["المواد"] if row["الكمية"] > 0]
    assert len(_material_rows(build_html(order, result))) == len(expected)


def test_zero_quantity_materials_are_excluded(order, catalog):
    """المواد ذات الكمية صفر لا تظهر في النموذج الرسمي."""
    project = OverheadProject(net11=Network11kV(route_length_m=500, poles_lattice=5))
    res = compute(project, catalog)
    html_text = build_html(order, res)
    assert "عمود 11م مدوّر" not in html_text   # لم تُدخَل أعمدة مدوّرة
    assert "عمود 11م مشبك" in html_text


def test_material_table_carries_no_prices(order, result):
    """النموذج الرسمي جدول كميات لا جدول كلف — لا سعر وحدة ولا كلفة سطر."""
    section = build_html(order, result).split("أ - جدول المواد")[1].split("ب - الاشراف")[0]
    assert "سعر" not in section
    assert "الكلفة" not in section
    for row in result["المواد"]:
        if row["الكلفة"]:
            assert f"{row['الكلفة']:,.0f}" not in section


def test_quantity_only_materials_appear_in_the_form(order, result):
    """ق-١٧: الكونكريت وشيش التسليح يظهران ككميات رغم أنهما بلا كلفة مواد."""
    html_text = build_html(order, result)
    assert "كونكريت أساسات الأعمدة" in html_text
    assert "شيش تسليح" in html_text


def test_unpriced_material_still_listed(order, result):
    """«واير ستي» بلا سعر لكنه مادة بكمية — فيُدرج في جدول الكميات."""
    assert "واير ستي" in build_html(order, result)


def test_quantities_match_the_engine(order, result):
    html_text = build_html(order, result)
    rows = _material_rows(html_text)
    printed = [re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S) for r in rows]
    # الخلايا تُكتب مقلوبة منذ ق-٦٤ (الكمية أولاً و«ت» أخيراً)، فتُقلب هنا
    # لتُقرأ بترتيبها المنطقي: ت، الاسم، الوحدة، الكمية.
    printed = [list(reversed(cells)) for cells in printed]
    by_name = {cells[1]: cells[3] for cells in printed}
    assert by_name["كونكريت أساسات الأعمدة"] == "161"
    assert by_name["سلك نحاس 50 ملم²"] == "87"
    assert by_name["شيش تسليح"] == "0.2"           # مقرَّب لأقرب عُشر لأعلى (ق-٣٢)


def test_fractional_quantity_keeps_its_decimals(order, result):
    """31.5 م لا تُقرَّب إلى 32 في النموذج، و0.2 لا تُبتَر إلى صفر."""
    assert "0.2" in build_html(order, result)


def test_rows_are_numbered_consecutively(order, result):
    rows = _material_rows(build_html(order, result))
    # «ت» آخر خلية في الصفّ بعد قلب الترتيب (ق-٦٤)
    numbers = [re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S)[-1] for r in rows]
    assert numbers == [str(i) for i in range(1, len(rows) + 1)]


# ═══════════════════════ الترويسة والأقسام ═══════════════════════


def test_header_carries_the_official_form_identity(order, result):
    html_text = build_html(order, result)
    assert "الشركة العامة لتوزيع كهرباء الفرات الأوسط" in html_text
    assert "فرع توزيع كهرباء كربلاء المقدسة" in html_text
    assert "MOE / D6-FO-30" in html_text
    assert "أمر عمل رقم 45" in html_text


def test_estimated_cost_appears_once_in_the_header(order, result):
    """الكلفة التخمينية رقم واحد في الترويسة — لا في جدول المواد."""
    html_text = build_html(order, result)
    assert f"{result['الكلفة_الكلية']:,.0f}" in html_text
    assert "الكلفة التخمينية للمواد + العمل" in html_text


def test_dates_are_formatted(order, result):
    html_text = build_html(order, result)
    assert "2026/08/18" in html_text
    assert "2026/09/01" in html_text


def test_manual_sections_print_only_what_was_entered(order, result):
    """**يُعدِّل السلوك السابق (ق-٦٤):** كانت الأسماء الأحد عشر كلها تُطبع ولو
    بلا عدد، فبطلبك صار يُطبع المُدخَل وحده."""
    order.staff[1].count, order.staff[1].days = 3, 60          # فني
    order.equipment[4].count, order.equipment[4].days = 1, 60  # كرين
    html_text = build_html(order, result)
    assert "فني" in html_text and "كرين" in html_text
    for absent in ("مهندس", "سائق", "محاسب", "رافعة", "شفل", "لوري هايب"):
        assert absent not in html_text, absent


def test_filled_staff_counts_are_printed(result):
    """الأقسام اليدوية تُطبع فارغة، وتُطبع معبّأة إن أدخلها المستخدم."""
    order = WorkOrder()
    order.staff[0].count, order.staff[0].days = 2, 30
    html_text = build_html(order, result)
    # الترتيب مقلوب منذ ق-٦٤: الأيام ثم العدد ثم الاسم ثم «ت»
    assert re.search(
        r'<td align="center">30</td><td align="center">2</td>'
        r'<td align="right">مهندس</td>',
        html_text,
    ), html_text


def test_special_characters_are_escaped(result):
    """اسم مشروع فيه محارف HTML لا يكسر النموذج."""
    order = WorkOrder(project_name='مشروع <script> & "اختبار"')
    html_text = build_html(order, result)
    assert "<script>" not in html_text
    assert "&lt;script&gt;" in html_text


# ═══════════════════════ إخراج PDF ═══════════════════════


def test_pdf_is_written(tmp_path, order, result, qapp):
    from printing.iso_form import write_pdf

    path = tmp_path / "order.pdf"
    write_pdf(order, result, str(path))
    assert path.exists() and path.stat().st_size > 5000
    assert path.read_bytes().startswith(b"%PDF")


def test_large_project_flows_onto_more_than_one_page(tmp_path, order, qapp):
    """60 مادة تتدفّق على صفحتين بدل أن تُقطع (حدّ 35 في الملف الأصلي)."""
    from printing.iso_form import write_pdf

    big = {
        "المواد": [
            {"المادة": f"مادة {i}", "الوحدة": "عدد", "الكمية": i, "سعر الوحدة": 1000,
             "الكلفة": i * 1000, "كمية_فقط": False, "سعر_مفقود": False}
            for i in range(1, 61)
        ],
        "الكلفة_الكلية": 1_000_000,
    }
    assert len(_material_rows(build_html(order, big))) == 60

    path = tmp_path / "big.pdf"
    write_pdf(order, big, str(path))
    assert path.read_bytes().count(b"/Type /Page\n") >= 2 or b"/Count 2" in path.read_bytes()
