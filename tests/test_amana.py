# -*- coding: utf-8 -*-
"""اختبارات قالب «تنفيذ أمانة» — PDF وإكسل والمواد غير المتوفرة (ق-٧٦).

**الحارس الجوهري هنا:** أن المجاميع الثلاثة في أسفل الورقة تساوي فعلاً ما جمعته
جداولها. فورقةٌ تُصرف عليها أموال ويكون مجموعها لا يطابق سطوره خطأٌ لا يُرى
بالعين، ويُكتشف بعد الصرف.
"""

import re

import pytest

pytest.importorskip("PyQt6", reason="PyQt6 غير مثبَّت")

from datetime import date  # noqa: E402

import printing  # noqa: E402
from engine import load_catalog  # noqa: E402
from engine.availability import selectable, unavailable_summary  # noqa: E402
from engine.project import compute_project  # noqa: E402
from engine.types import (  # noqa: E402
    Network11kV,
    Project,
    Segment,
    SidewalkType,
    Underground11kV,
)
from engine.underground import CIVIL_GROUP  # noqa: E402
from engine.workorder import WorkOrder  # noqa: E402
from printing.amana_form import (  # noqa: E402
    AUDIT_COMMITTEE,
    NOTES,
    PREPARATION_COMMITTEE,
    build_html,
    header_line,
    printed_labour_name,
    printed_materials,
    split_labour,
    title_line,
    totals,
)


@pytest.fixture(scope="module")
def result():
    """مشروع فيه هوائي وأرضيّان مختلفا الرصيف وعبور شوارع — ليمتلئ الجدولان."""
    project = Project("استحداث مغذيات من محطة الإسكان", [
        Segment("هوائي", Network11kV(route_length_m=750, poles_lattice=9,
                                     poles_round=15)),
        Segment("ترابي", Underground11kV(route_length_m=300, feeder_count=2,
                                         sidewalk_type=SidewalkType.EARTH)),
        Segment("مقرنص", Underground11kV(route_length_m=200, feeder_count=1,
                                         sidewalk_type=SidewalkType.TERRAZZO)),
    ], street_crossing_secondary_m=12, street_crossing_secondary_feeders=2,
       street_crossing_main_m=30, street_crossing_main_feeders=1)
    return compute_project(project, load_catalog())


@pytest.fixture
def order():
    return WorkOrder(number="148", order_date=date(2026, 9, 9),
                     classification="تشغيلي", project_name="استحداث مغذيات",
                     duration="90 يوم", start_date=None, notes="ملاحظة خاصة")


def text_of(html: str) -> str:
    """نصّ الورقة بلا وسوم — للبحث عن عبارة، لا عن خلية بعينها."""
    return re.sub(r"<[^>]+>", " ", html)


# ═══════════════ ١. الترويسة والعنوان ═══════════════


def test_the_banner_names_the_company_and_the_branch_without_the_department(order):
    """صيغة المستخدم تنتهي عند اسم الفرع — وقسم التخطيط من ترويسة الإيزو."""
    line = header_line(order)
    assert order.organisation in line
    assert "فرع توزيع كهرباء كربلاء المقدسة" in line
    assert "قسم التخطيط" not in line
    # والحقل المحفوظ لم يُمسّ
    assert "قسم التخطيط" in order.branch


def test_the_title_carries_the_number_the_style_and_the_project(order):
    line = title_line(order)
    assert "(148)" in line
    assert "أسلوب تنفيذ أمانة" in line
    assert "استحداث مغذيات" in line


def test_the_title_leaves_the_classification_out(order):
    """بنصّ المستخدم: «لا يحتاج، فقط رقم امر العمل مع العبارة ثم اسم المشروع»."""
    assert order.classification and order.classification not in title_line(order)


# ═══════════════ ٢. الفصل بين المدني والكهربائي ═══════════════


def test_the_split_follows_the_engine_tag_not_the_name(result):
    civil, electrical = split_labour(result)
    assert civil and electrical
    assert all(line.group == CIVIL_GROUP for line in civil)
    assert all(line.group != CIVIL_GROUP for line in electrical)


def test_the_two_tables_together_hold_every_labour_line(result):
    """لا بند يسقط بين الجدولين — ولا بند يظهر فيهما معاً."""
    civil, electrical = split_labour(result)
    assert len(civil) + len(electrical) == len(result["أجور_العمل"])


def test_the_civil_table_holds_the_crossings_too(result):
    """عبور الشوارع الفرعية والرئيسية ضمن الأعمال المدنية (ق-٣٨)."""
    civil, _ = split_labour(result)
    names = [line.name for line in civil]
    assert any("عبور الشوارع الفرعية" in n for n in names)
    assert any("عبور الشوارع الرئيسية" in n for n in names)


def test_the_cable_laying_stays_split_by_cable_size(result, order):
    """«مد القابلو تفصل حسب حجم القابلو» — والمحرك يفصلها أصلاً."""
    _, electrical = split_labour(result)
    assert any("3×150" in line.name for line in electrical)


# ═══════════════ ٣. اسم بند المدنية في المطبوع ═══════════════


@pytest.mark.parametrize("full,printed", [
    ("حفر الخندق — رصيف ترابي، مسار مفرد", "حفر الخندق — رصيف ترابي"),
    ("إعادة المسار — رصيف مقرنص، مسار ثلاثي", "إعادة المسار — رصيف مقرنص"),
    ("عبور الشوارع الرئيسية – حفر مخفي", "عبور الشوارع الرئيسية – حفر مخفي"),
    ("نصب عمود مشبك 11م", "نصب عمود مشبك 11م"),
])
def test_the_printed_name_drops_only_the_route_multiplicity(full, printed):
    assert printed_labour_name(full) == printed


def test_the_engine_name_keeps_the_multiplicity(result):
    """الحذف **عرضٌ في هذا القالب وحده** — والمحرك والشاشة يريان الاسم كاملاً."""
    civil, _ = split_labour(result)
    assert any("مسار" in line.name for line in civil)


def test_the_multiplicity_is_absent_from_the_printed_sheet(order, result):
    """بطلب المستخدم: «لا تذكر مسار مفرد او مزدوج او ثلاثي»."""
    body = text_of(build_html(order, result))
    assert "مسار مفرد" not in body
    assert "مسار ثنائي" not in body
    assert "رصيف ترابي" in body            # ونوع الرصيف يبقى


# ═══════════════ ٤. المجاميع — الحارس الأهمّ ═══════════════


def test_the_labour_total_equals_the_engine_total(order, result):
    """مجموع الجدولين = أجور العمل عند المحرك. أي فرق يعني بنداً ضائعاً."""
    sums = totals(order, result)
    assert sums["الأعمال_المدنية"] + sums["الأعمال_الكهربائية"] == sums["أجور_العمل"]
    assert sums["أجور_العمل"] == pytest.approx(result["كلفة_العمل"])


def test_each_table_total_equals_its_own_rows(order, result):
    civil, electrical = split_labour(result)
    sums = totals(order, result)
    assert sums["الأعمال_المدنية"] == pytest.approx(sum(l.cost for l in civil))
    assert sums["الأعمال_الكهربائية"] == pytest.approx(
        sum(l.cost for l in electrical))


def test_the_three_closing_sums_add_up(order, result):
    """المجاميع الثلاثة في الأسفل — كلٌّ منها جمعٌ صريح لسابقه."""
    order.unavailable_materials = [printed_materials(result)[0]["المادة"]]
    sums = totals(order, result)
    assert sums["العمل_مع_غير_المتوفرة"] == pytest.approx(
        sums["أجور_العمل"] + sums["المواد_غير_المتوفرة"])
    assert sums["العمل_مع_كل_المواد"] == pytest.approx(
        sums["أجور_العمل"] + result["كلفة_المواد"])


def test_the_printed_sums_are_the_computed_ones(order, result):
    """ما يُطبع هو ما يُحسب — لا رقم في الورقة خارج `totals`."""
    sums = totals(order, result)
    body = text_of(build_html(order, result))
    for key in ("أجور_العمل", "العمل_مع_غير_المتوفرة", "العمل_مع_كل_المواد",
                "كلفة_المواد"):
        assert f"{sums[key]:,.0f}" in body, key


# ═══════════════ ٥. المواد غير المتوفرة ═══════════════


def test_the_item_numbers_match_the_printed_table(order, result):
    """رقم الفقرة يشير إلى سطرها في الجدول — لا إلى ترتيبٍ آخر.

    وهذا أخطر ما في هذه الميزة: رقمٌ يشير إلى مادة غير التي أُشّرت يجعل الكشف
    يطلب صرف مادة متوفرة ويترك المفقودة.
    """
    materials = printed_materials(result)
    chosen = [materials[2]["المادة"], materials[6]["المادة"]]
    order.unavailable_materials = chosen
    summary = unavailable_summary(materials, order.unavailable_materials)

    assert summary["فقرات"] == [3, 7]
    for number, name in zip(summary["فقرات"], chosen):
        assert materials[number - 1]["المادة"] == name


def test_the_unavailable_cost_is_the_sum_of_the_ticked_rows(order, result):
    materials = printed_materials(result)
    chosen = [m for m in materials if selectable(m) and not m["سعر_مفقود"]][:3]
    order.unavailable_materials = [m["المادة"] for m in chosen]
    assert totals(order, result)["المواد_غير_المتوفرة"] == pytest.approx(
        sum(m["الكلفة"] for m in chosen))


def test_a_material_priced_inside_the_labour_is_never_unavailable(order, result):
    """بنصّ المستخدم: «هذه المواد تعتبر متوفرة دائماً».

    ولو حُسبت لأضافت **صفراً** إلى كلفة غير المتوفرة، فيظنّ القارئ أنها أُدخلت
    وحُسبت وهي لم تُحسب.
    """
    materials = printed_materials(result)
    within = [m for m in materials if m["كمية_فقط"]]
    assert within, "المشروع بلا مادة ضمن الأجور — الاختبار لا يفحص شيئاً"

    order.unavailable_materials = [m["المادة"] for m in within]
    summary = unavailable_summary(materials, order.unavailable_materials)
    assert summary["فقرات"] == []
    assert summary["الكلفة"] == 0
    assert summary["متوفرة_دائماً"] == [m["المادة"] for m in within]
    assert not any(selectable(m) for m in within)


def test_an_unpriced_ticked_material_is_reported_not_silently_zero(result):
    materials = [
        {"المادة": "مادة بلا سعر", "الوحدة": "عدد", "الكمية": 2, "الكلفة": 0,
         "كمية_فقط": False, "سعر_مفقود": True},
        {"المادة": "مادة مُسعَّرة", "الوحدة": "عدد", "الكمية": 1, "الكلفة": 500,
         "كمية_فقط": False, "سعر_مفقود": False},
    ]
    summary = unavailable_summary(materials, ["مادة بلا سعر", "مادة مُسعَّرة"])
    assert summary["بلا_سعر"] == ["مادة بلا سعر"]
    assert summary["الكلفة"] == 500          # المفقودة لم تُحسب صفراً بصمت
    assert summary["فقرات"] == [1, 2]        # لكنها تُذكر في الفقرات


def test_a_material_that_left_the_project_is_ignored_not_crashed(order, result):
    """تأشيرٌ لمادة لم تعد في المشروع يُهمَل — ولا يُسقط الطباعة."""
    order.unavailable_materials = ["مادة لا وجود لها في هذا المشروع"]
    assert totals(order, result)["فقرات_غير_متوفرة"] == []
    assert build_html(order, result)


def test_the_sheet_names_the_unavailable_items_only_when_there_are_any(order, result):
    assert "المواد غير المتوفرة تشمل الفقرات" not in build_html(order, result)
    order.unavailable_materials = [printed_materials(result)[1]["المادة"]]
    assert "المواد غير المتوفرة تشمل الفقرات (2)" in text_of(
        build_html(order, result))


# ═══════════════ ٦. أسعار المواد: فارغة افتراضياً ═══════════════


def test_material_prices_are_blank_by_default(order, result):
    """بنصّ المستخدم — والمجموع يُطبع مع ذلك."""
    body = text_of(build_html(order, result))
    priced = [m for m in printed_materials(result)
              if not m["كمية_فقط"] and not m["سعر_مفقود"]]
    shown = [f"{m['سعر الوحدة']:,.0f}" for m in priced]
    assert not any(f" {value} " in body for value in shown if len(value) > 4)
    assert f"{result['كلفة_المواد']:,.0f}" in body


def test_ticking_the_option_fills_the_price_columns(order, result):
    order.show_material_prices = True
    body = text_of(build_html(order, result))
    material = next(m for m in printed_materials(result)
                    if not m["كمية_فقط"] and not m["سعر_مفقود"])
    assert f"{material['سعر الوحدة']:,.0f}" in body
    assert f"{material['الكلفة']:,.0f}" in body


# ═══════════════ ٧. الملاحظات واللجان ═══════════════


def test_the_two_fixed_notes_are_always_printed(order, result):
    body = text_of(build_html(order, result))
    for note in NOTES:
        assert note in body


def test_the_users_own_note_is_added_below_them(order, result):
    assert "ملاحظة خاصة" in text_of(build_html(order, result))


def test_the_committees_are_named_without_any_person(order, result):
    """«تذكر اللجان بدون الاسماء» — عناوين وخطوط توقيع فارغة لا غير."""
    from printing.iso_form import SIGNATURES

    body = text_of(build_html(order, result))
    assert PREPARATION_COMMITTEE in body
    assert AUDIT_COMMITTEE in body
    # ولا أسماء التواقيع الخمسة الخاصة بقالب الإيزو
    for name in SIGNATURES:
        assert name not in body


@pytest.mark.parametrize("preparation,audit", [(3, 3), (6, 5), (0, 4)])
def test_each_committee_gets_the_number_of_signature_lines_asked_for(
    order, result, preparation, audit
):
    order.preparation_committee = preparation
    order.audit_committee = audit
    body = build_html(order, result)
    assert body.count("................") == preparation + audit


# ═══════════════ ٨. الكتابة إلى القرص ═══════════════


def test_the_template_is_registered_with_all_three_writers():
    template = printing.get("amana")
    assert callable(template.write_pdf) and callable(template.write_xlsx)
    assert "أمانة" in template.name


def test_the_pdf_is_written(order, result, tmp_path, qapp):
    path = printing.get("amana").write_pdf(order, result,
                                           str(tmp_path / "أمانة.pdf"))
    assert (tmp_path / "أمانة.pdf").stat().st_size > 1000
    assert path.endswith(".pdf")


# ═══════════════ ٩. ورقة الإكسل: معادلات حيّة ═══════════════

openpyxl = pytest.importorskip("openpyxl", reason="openpyxl غير مثبَّت")

from printing.amana_sheet import HIDDEN, SHEET, build_workbook, write_xlsx  # noqa: E402
from printing.spreadsheet import _MONEY  # noqa: E402


def _find(sheet, text: str, column: int = 1) -> int:
    for row in range(1, sheet.max_row + 1):
        if sheet.cell(row, column).value == text:
            return row
    raise AssertionError(f"لا خلية فيها «{text}» في العمود {column}")


@pytest.fixture
def book(order, result):
    order.unavailable_materials = [m["المادة"] for m in printed_materials(result)[1:4]
                                   if selectable(m)]
    return build_workbook(order, result)[SHEET]


def test_the_sheet_is_right_to_left(book):
    assert book.sheet_view.rightToLeft is True


def test_every_cost_cell_is_a_formula(book):
    """تعديل كمية أو سعر يُحدّث سطره ومجاميعه داخل الإكسل — كلّ غرض الملف."""
    first = _find(book, "ت") + 1
    assert book.cell(first, 6).value == f"=D{first}*E{first}"


def test_the_material_prices_are_hidden_but_present(book):
    """القيمة تبقى والعرض يُخفى: مجموعٌ صحيح وخانات تبدو فارغة."""
    first = _find(book, "ت") + 1
    assert book.cell(first, 5).number_format == HIDDEN
    assert book.cell(first, 6).number_format == HIDDEN
    assert isinstance(book.cell(first, 5).value, (int, float))


def test_the_labour_prices_stay_visible_while_the_material_ones_hide(book):
    """**الحارس الذي يمنع العودة إلى إخفاء العمود:** العمود واحد للجداول الثلاثة.

    فلو أُخفي العمود بدل تنسيق الخلية لاختفت أسعار الأعمال المدنية والكهربائية
    معها — وهي المطلوبة كاملة في هذا القالب.
    """
    civil_head = _find(book, "الأعمال المدنية", column=2)
    assert book.cell(civil_head + 1, 5).number_format == _MONEY
    assert book.cell(civil_head + 1, 6).number_format == _MONEY


def test_showing_the_prices_unhides_them(order, result):
    order.show_material_prices = True
    sheet = build_workbook(order, result)[SHEET]
    first = _find(sheet, "ت") + 1
    assert sheet.cell(first, 5).number_format == _MONEY


def test_the_unavailable_formula_points_at_the_ticked_rows(order, result):
    """المعادلة تجمع خلايا الفقرات المؤشَّرة بأعيانها — لا رقماً جامداً."""
    materials = printed_materials(result)
    chosen = [m["المادة"] for m in materials[1:4] if selectable(m)]
    order.unavailable_materials = chosen
    sheet = build_workbook(order, result)[SHEET]

    formula = sheet.cell(_find(sheet, "الكلفة التخمينية للمواد غير المتوفرة"), 6).value
    numbers = unavailable_summary(materials, chosen)["فقرات"]
    first = _find(sheet, "ت") + 1
    assert formula == "=" + "+".join(f"F{first + n - 1}" for n in numbers)
    # والخلايا التي تسمّيها هي فعلاً سطور تلك المواد
    for n in numbers:
        assert sheet.cell(first + n - 1, 2).value == materials[n - 1]["المادة"]


def test_the_closing_sums_reference_the_two_table_totals(book):
    """**الحارس الأهمّ في الإكسل:** المرجع يتبع عدد السطور.

    موضع صفّ المجموع يتغيّر بعدد المواد وبنود العمل، وخطأ إزاحة واحد يجعل
    الورقة تجمع سطراً من الجدول بدل مجموعه — رقمٌ معقول المظهر وخاطئ تماماً.
    """
    closing = _find(book, "مجموع اجور العمل (الاعمال الكهربائية + الاعمال المدنية)")
    formula = book.cell(closing, 6).value
    cells = re.findall(r"F(\d+)", formula)
    assert len(cells) == 2
    for reference in cells:
        assert str(book.cell(int(reference), 6).value).startswith("=SUM(")


def test_the_total_row_of_each_table_sums_its_own_rows(book):
    for label in ("مجموع اجور عمل الاعمال المدنية",
                  "مجموع اجور عمل الاعمال الكهربائية",
                  "الكلفة التخمينية الكلية للمواد"):
        row = _find(book, label)
        assert str(book.cell(row, 6).value).startswith("=SUM(F"), label


def test_the_committees_close_the_sheet_without_names(book):
    row = _find(book, PREPARATION_COMMITTEE)
    assert book.cell(row + 1, 1).value == "................"
    assert _find(book, AUDIT_COMMITTEE) > row


def test_the_file_is_written_and_reopens(order, result, tmp_path):
    path = write_xlsx(order, result, str(tmp_path / "أمانة"))
    assert path.endswith(".xlsx")
    assert openpyxl.load_workbook(path).sheetnames == [SHEET]


# ═══════════════ ١٠. الوحدات والأسماء بعد ملاحظات التجربة (ق-٧٧) ═══════════════


@pytest.mark.parametrize("engine_unit,printed", [
    ("متر × مغذٍّ", "متر"),
    ("متر", "متر"),
    ("عدد", "عدد"),
])
def test_the_printed_unit_drops_the_multiplier(engine_unit, printed):
    from printing.amana_form import printed_unit

    assert printed_unit(engine_unit) == printed


def test_the_crossing_prints_metres_while_the_engine_keeps_the_multiplier(order, result):
    """بطلبك: الوحدة في المطبوع «متر»، والكمية تبقى الطول × عدد المغذيات."""
    from printing.amana_form import printed_unit

    civil, _ = split_labour(result)
    crossing = next(line for line in civil if "عبور الشوارع الفرعية" in line.name)
    assert "×" in crossing.unit                      # المحرك يبقى صريحاً
    assert printed_unit(crossing.unit) == "متر"

    body = text_of(build_html(order, result))
    assert "متر × مغذٍّ" not in body
    assert f"{crossing.qty:,.0f}" in body            # والكمية كما هي


def test_the_excel_prints_the_same_unit_as_the_pdf(order, result):
    sheet = build_workbook(order, result)[SHEET]
    units = [sheet.cell(row, 3).value for row in range(1, sheet.max_row + 1)]
    assert "متر × مغذٍّ" not in units
    assert "متر" in units


def test_the_wiring_item_is_named_after_the_aluminium_wire_it_lays(result):
    """«تسليك سلك ألمنيوم 120/20 ملم²» — والاسم مشتقّ من اسم المادة نفسها."""
    from engine.overhead import M_WIRE_11, WIRING_11_LABEL

    _, electrical = split_labour(result)
    line = next(line for line in electrical if line.name.startswith("تسليك"))
    assert line.name == WIRING_11_LABEL == f"تسليك {M_WIRE_11[0]}"
    assert "شبكة الضغط العالي" not in line.name
    assert line.unit == "متر"


def test_the_pole_items_are_counted_in_units(result):
    """وحدة نصب الأعمدة «عدد» — كما في نسخة الأسعار."""
    _, electrical = split_labour(result)
    poles = [line for line in electrical if line.name.startswith("نصب عمود")]
    assert poles
    assert all(line.unit == "عدد" for line in poles)


def test_the_cable_boxes_belong_to_the_electrical_table(order):
    """بنصّك: «أجور عمل صندوق مستقيم وصندوق نهاية تقع ضمن الأعمال الكهربائية».

    وهي كذلك أصلاً — وهذا الحارس يمنع انزلاقها إلى الجدول المدني لاحقاً.
    """
    from engine.types import Underground33kV

    boxed = compute_project(Project("م", [
        Segment("أ", Underground11kV(route_length_m=300, feeder_count=2,
                                     straight_boxes=3, end_boxes_internal=1,
                                     end_boxes_external=2,
                                     sidewalk_type=SidewalkType.EARTH)),
        Segment("ب", Underground33kV(route_length_m=200, straight_boxes=1,
                                     end_boxes_internal=1)),
    ]), load_catalog())

    civil, electrical = split_labour(boxed)
    assert not any("صندوق" in line.name for line in civil)
    assert len([line for line in electrical if "صندوق" in line.name]) == 4
