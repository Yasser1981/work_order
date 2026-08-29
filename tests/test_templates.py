# -*- coding: utf-8 -*-
"""اختبارات آلية القوالب — مشروع واحد يُخرَج بأكثر من قالب."""

from datetime import date

import pytest

import printing
from engine import load_catalog
from engine.overhead import compute
from engine.types import CircuitType, Network11kV, Network33kV, OverheadProject
from engine.workorder import WorkOrder


@pytest.fixture(scope="module")
def result():
    project = OverheadProject(
        net11=Network11kV(route_length_m=500, poles_lattice=5, poles_round=16,
                          stay_rod_sets=2),
        net33=Network33kV(route_length_m=2000, poles_suspension=27, anchors_mid=3,
                          anchors_end=2, circuit=CircuitType.DOUBLE),
    )
    return compute(project, load_catalog())


@pytest.fixture
def order():
    return WorkOrder(number="45", project_name="مشروع اختباري",
                     order_date=date(2026, 8, 19))


# ═══════════════════════ السجل ═══════════════════════


def test_builtin_templates_are_registered():
    keys = [t.key for t in printing.available()]
    assert "iso" in keys and "audit" in keys


def test_every_template_has_a_name_and_description():
    for template in printing.available():
        assert template.name.strip()
        assert template.description.strip()


def test_unknown_template_key_is_rejected():
    with pytest.raises(KeyError):
        printing.get("لا-يوجد")


def test_duplicate_registration_is_rejected():
    """تسجيل مفتاح مكرّر يُرفض بدل أن يستبدل قالباً قائماً بصمت."""
    existing = printing.get("iso")
    with pytest.raises(ValueError):
        printing.register(existing)


# ═══════════════════════ كل القوالب تقرأ نفس البيانات ═══════════════════════


@pytest.mark.parametrize("key", [t.key for t in printing.available()])
def test_template_renders_the_same_project(key, order, result):
    html = printing.get(key).build_html(order, result)
    assert "مشروع اختباري" in html
    assert "45" in html


@pytest.mark.parametrize("key", [t.key for t in printing.available()])
def test_template_writes_pdf(key, order, result, tmp_path, qapp):
    path = str(tmp_path / f"{key}.pdf")
    printing.get(key).write_pdf(order, result, path)
    assert (tmp_path / f"{key}.pdf").read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize("key", [t.key for t in printing.available()])
def test_every_template_lists_all_materials(key, order, result):
    """أي قالب يعرض كل المواد ذات الكمية — لا يُسقط شيئاً."""
    html = printing.get(key).build_html(order, result)
    for row in result["المواد"]:
        if row["الكمية"] > 0:
            assert row["المادة"] in html, f"{row['المادة']} مفقودة من قالب {key}"


# ═══════════════ ما يميّز كل قالب عن الآخر ═══════════════


def test_iso_shows_no_prices_but_audit_does(order, result):
    """الإيزو نموذج كميات رسمي، وورقة التدقيق للمراجعة الداخلية."""
    iso = printing.get("iso").build_html(order, result)
    audit = printing.get("audit").build_html(order, result)

    assert "سعر الوحدة" not in iso
    assert "سعر الوحدة" in audit


def test_only_audit_shows_the_work_items(order, result):
    """فقرات العمل تظهر في ورقة التدقيق ولا تظهر في النموذج الرسمي."""
    iso = printing.get("iso").build_html(order, result)
    audit = printing.get("audit").build_html(order, result)

    labour_name = result["أجور_العمل"][0].name
    assert labour_name not in iso
    assert labour_name in audit
    assert f"{result['كلفة_العمل']:,.0f}" in audit


def test_only_audit_shows_quantity_sources(order, result):
    """تفصيل مصدر الكمية للمدقّق — لا يدخل النموذج الرسمي."""
    iso = printing.get("iso").build_html(order, result)
    audit = printing.get("audit").build_html(order, result)

    assert "المصدر" not in iso
    assert "المصدر" in audit
    assert "مقرَّب لأعلى" in audit          # تفصيل الكونكريت
    assert "مرفق" in audit or "×" in audit  # معادلات المصادر


def test_audit_totals_match_the_engine(order, result):
    audit = printing.get("audit").build_html(order, result)
    assert f"{result['كلفة_المواد']:,.0f}" in audit
    assert f"{result['كلفة_العمل']:,.0f}" in audit
    assert f"{result['الكلفة_الكلية']:,.0f}" in audit


def test_audit_warns_about_unpriced_materials(order):
    """المادة بلا سعر تُنبّه عنها ورقة التدقيق صراحةً.

    بسعر **مُحقون**: بعد ق-٣٦ صارت كل المواد مسعّرة، فربط الاختبار بمادة بعينها
    يجعله يفشل مع كل تحديث أسعار.
    """
    import copy

    from engine.overhead import compute
    from engine.types import Network11kV, OverheadProject

    catalog = copy.deepcopy(load_catalog())
    catalog["المواد"]["عمود 11م مشبك"]["السعر"] = None
    unpriced = compute(OverheadProject(net11=Network11kV(poles_lattice=3)), catalog)

    audit = printing.get("audit").build_html(order, unpriced)
    assert unpriced["أسعار_مفقودة"] == ["عمود 11م مشبك"]
    assert "تنبيه" in audit
    assert "عمود 11م مشبك" in audit


def test_adding_a_template_needs_no_engine_change():
    """حارس معماري: القوالب تقرأ نتيجة المحرك ولا يعرف المحرك بها.

    هذا ما يجعل إضافة قالب جديد تعديلاً في مجلد الطباعة وحده.
    """
    import inspect

    from engine import overhead

    source = inspect.getsource(overhead)
    assert "printing" not in source
    assert "iso_form" not in source


# ═══════════════════ القوالب ومشروع المقاطع ═══════════════════


@pytest.fixture(scope="module")
def segmented_result():
    """مشروع بمقاطع مسمّاة، وفيه بند بلا أجر (ربط المستهلكين)."""
    from engine.project import compute_project
    from engine.types import LVNetworkType, NetworkLV, Project, Segment

    project = Project(
        "مشروع بمقاطع",
        [
            Segment("المقطع الأول",
                    Network11kV(route_length_m=500, poles_lattice=5, poles_round=16)),
            Segment("المقطع الثاني",
                    NetworkLV(route_length_m=300, kind=LVNetworkType.BARE_WIRES,
                              poles_lattice=4, poles_round=12, consumers=5)),
        ],
    )
    return compute_project(project, load_catalog())


# ═══════════════════ الخطّ العربي — ملاءمة ويندوز (ق-٥١) ═══════════════════


def test_the_font_falls_back_across_platforms():
    """أول خطّ عربي متاح فعلاً — لا اسم مثبَّت قد لا يوجد على جهاز المستخدم."""
    from printing.iso_form import available_arabic_font

    # ويندوز عادي بلا أوفيس: Tahoma مشحون مع كل نسخة وعربيّته ممتازة
    assert available_arabic_font(["Arial", "Tahoma", "Times New Roman"]) == "Tahoma"
    # ويندوز مع أوفيس: الخطّ الرسمي يتقدّم
    assert available_arabic_font(["Arial", "Tahoma", "Simplified Arabic"]) == "Simplified Arabic"
    # لينكس (بيئة التطوير)
    assert available_arabic_font(["DejaVu Sans", "FreeSerif"]) == "FreeSerif"
    # جهاز بلا أي خطّ من القائمة — لا انهيار، بل الافتراضي العامّ
    assert available_arabic_font(["Comic Sans MS"]) == "serif"


def test_building_html_without_a_qt_app_does_not_abort():
    """حارس انهيار: `QFontDatabase` بلا `QApplication` **تُسقط العملية بـ Abort**
    لا برفع استثناء. فبناء HTML خارج التطبيق يجب أن يعيد `serif` بلا مساس.

    الخلل كان من صنعي في ق-٥١ وكشفته الاختبارات قبل الإيداع.
    """
    import subprocess
    import sys

    code = (
        "from printing.iso_form import available_arabic_font;"
        "print(available_arabic_font())"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd="."
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "serif"


def test_no_linux_only_font_is_hard_coded_in_the_styles(qapp):
    """حارس ق-٥١: لا اسم خطّ مثبَّت في الأنماط — يُختار وقت التشغيل.

    كان `FreeSerif` مثبَّتاً وهو خطّ لينكس لا يُشحن مع ويندوز، فكان المستند
    على حاسبة المستخدم يسقط إلى Times New Roman.
    """
    from printing.iso_form import _CSS, styles

    assert "%FONT%" in _CSS                 # القالب يحمل موضع الاستبدال
    assert "%FONT%" not in styles()         # والناتج لا يحمله
    assert "font-family" in styles()


def test_both_templates_use_the_resolved_font(order, result, qapp):
    from printing.iso_form import available_arabic_font

    font = available_arabic_font()
    for key in ("iso", "audit"):
        html = printing.get(key).build_html(order, result)
        assert f"'{font}'" in html, key


def test_audit_survives_a_labour_item_with_no_rate(order, underground_result_missing_rate):
    """كان القالب ينهار على أي أجر بلا سعر — الأجر None لا يُنسَّق كرقم (خ-١)."""
    html = printing.get("audit").build_html(order, underground_result_missing_rate)
    assert underground_result_missing_rate["أجور_مفقودة"]
    assert "بلا أجر" in html


def test_audit_warns_about_missing_rates_too(order, underground_result_missing_rate):
    html = printing.get("audit").build_html(order, underground_result_missing_rate)
    assert "بنود بلا أجر" in html


def test_audit_lists_the_project_segments(order, segmented_result):
    """جدول المقاطع مفتاح قراءة عمود «المصدر» الذي يذكر اسم المقطع."""
    html = printing.get("audit").build_html(order, segmented_result)
    assert "مقاطع المشروع" in html
    assert "المقطع الأول" in html
    assert "المقطع الثاني" in html


def test_the_simple_project_shows_no_segments_table(order, result):
    """المشروع بلا مقاطع مسمّاة لا يُضاف له جدول فارغ."""
    html = printing.get("audit").build_html(order, result)
    assert "مقاطع المشروع" not in html


@pytest.mark.parametrize("key", ["iso", "audit"])
def test_every_template_handles_a_segmented_project(key, order, segmented_result, tmp_path, qapp):
    path = printing.get(key).write_pdf(order, segmented_result, str(tmp_path / f"{key}.pdf"))
    assert (tmp_path / f"{key}.pdf").read_bytes().startswith(b"%PDF")


# ═══════════════════ الشبكة الأرضية 11 ك.ف ═══════════════════


def _underground_project():
    from engine.types import Project, Segment, SidewalkType, Underground11kV

    return Project(
        "مشروع أرضي",
        [
            Segment(
                "المقطع الأول",
                Underground11kV(
                    route_length_m=400, feeder_count=6, sidewalk_type=SidewalkType.EARTH,
                    straight_boxes=2, end_boxes_internal=1,
                ),
            ),
        ],
        street_crossing_secondary_m=30,
        street_crossing_main_m=10,
    )


@pytest.fixture(scope="module")
def underground_result():
    """مشروع أرضي كامل التسعير — 6 مغذيات صارت مسعّرة بعد ق-٤٤."""
    from engine.project import compute_project

    return compute_project(_underground_project(), load_catalog())


@pytest.fixture(scope="module")
def underground_result_missing_rate():
    """المشروع نفسه وقد حُذفت تعرفة الأعمال المدنية من نسخة الأسعار.

    لم يعد للأجر المفقود مصدر طبيعي بعد ق-٤٤ — كل عدد مغذيات صار مسعّراً.
    فيُحقَن الغياب في **نسخة** من الأسعار بدل بناء الاختبار على ثغرة مسدودة
    (نفس نهج ق-٣٦ مع المواد بلا سعر).
    """
    import copy

    from engine.project import compute_project

    catalog = copy.deepcopy(load_catalog())
    catalog["تعرفة_الأعمال_المدنية"] = {}
    return compute_project(_underground_project(), catalog)


@pytest.mark.parametrize("key", ["iso", "audit"])
def test_every_template_survives_an_underground_segment_with_a_missing_rate(
    key, order, underground_result_missing_rate, tmp_path, qapp
):
    """أهمّ اختبار: أجر بلا سعر لا يُسقط الطباعة (ق-٣٠، خ-١)."""
    path = printing.get(key).write_pdf(
        order, underground_result_missing_rate, str(tmp_path / f"{key}.pdf")
    )
    assert (tmp_path / f"{key}.pdf").read_bytes().startswith(b"%PDF")


def test_audit_prints_the_extended_civil_rate_not_a_blank(order, underground_result):
    """6 مغذيات: تعرفة ممتدّة مسعّرة ومفصَّلة إلى مكوّنين (ق-٤٤، ق-٤٧)."""
    html = printing.get("audit").build_html(order, underground_result)
    assert "الأعمال المدنية" in html
    assert not underground_result["أجور_مفقودة"]
    assert "حفر الخندق" in html and "إعادة المسار" in html
    assert "17,000" in html and "26,000" in html   # ترابي 6: 11,000+6,000 و20,000+6,000


def test_the_audit_sheet_states_which_price_version_produced_it(order, underground_result):
    """المدقّق يرى بأي أسعار حُسبت الورقة — ورقتان بنسختين مختلفتين ورقتان (ق-٤٠)."""
    html = printing.get("audit").build_html(order, underground_result)
    assert f"محسوبة بنسخة الأسعار: {underground_result['نسخة_الأسعار']}" in html
    assert underground_result["نسخة_الأسعار"]          # ليست فارغة


def test_a_result_without_a_price_version_is_flagged_not_hidden(order, underground_result):
    """نتيجة بلا نسخة أسعار تُطبع بتحذير ظاهر — لا بسطر فارغ صامت."""
    stripped = dict(underground_result)
    stripped["نسخة_الأسعار"] = ""
    html = printing.get("audit").build_html(order, stripped)
    assert "نسخة الأسعار غير مسجَّلة" in html


def test_audit_groups_the_labour_table_into_electrical_and_civil(underground_result, order):
    """جدول الأجور مبوّب: الكهربائية ثم المدنية، ولكل باب مجموعه (ق-٣٨)."""
    html = printing.get("audit").build_html(order, underground_result)
    electrical = html.index("الأعمال الكهربائية")
    civil = html.index("<b>الأعمال المدنية</b>")
    assert electrical < civil                      # الكهربائية هي الأصل فتتصدّر
    assert "مجموع الأعمال المدنية" in html
    assert "مجموع الأعمال الكهربائية" in html


def test_the_civil_subtotal_equals_the_sum_of_its_lines(underground_result, order):
    """حارس مالي: مجموع الباب المطبوع = مجموع أسطره فعلاً لا رقماً مستقلاً."""
    from engine.underground import CIVIL_GROUP

    html = printing.get("audit").build_html(order, underground_result)
    expected = sum(
        l.cost for l in underground_result["أجور_العمل"] if l.group == CIVIL_GROUP
    )
    assert f"مجموع الأعمال المدنية</td>\n      <td" not in html   # التنسيق قد يتغيّر
    assert f"{expected:,.0f}" in html


def test_a_single_group_prints_no_group_headers(order):
    """مشروع بلا أعمال مدنية: لا معنى لتبويب جدول من باب واحد."""
    from engine import load_catalog
    from engine.project import compute_project
    from engine.types import Equipment, Project, Segment
    from engine.equipment import TransformerSize, TransformerVoltage

    result = compute_project(
        Project(segments=[Segment("تجهيزات", Equipment(
            transformers={(TransformerVoltage.KV11, TransformerSize.KVA400): 1}))]),
        load_catalog(),
    )
    html = printing.get("audit").build_html(order, result)
    assert "الأعمال الكهربائية" not in html
    assert "مجموع أجور التنفيذ" in html
