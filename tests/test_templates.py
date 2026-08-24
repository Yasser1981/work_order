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


def test_audit_warns_about_unpriced_materials(order, result):
    """«واير ستي» بلا سعر — ورقة التدقيق تُنبّه صراحةً."""
    audit = printing.get("audit").build_html(order, result)
    assert result["أسعار_مفقودة"]
    assert "تنبيه" in audit
    for name in result["أسعار_مفقودة"]:
        assert name in audit


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


def test_audit_survives_a_labour_item_with_no_rate(order, segmented_result):
    """كان القالب ينهار على أي مشروع فيه مستهلكون — الأجر None لا يُنسَّق كرقم."""
    html = printing.get("audit").build_html(order, segmented_result)
    assert "بلا أجر" in html
    assert "ربط المستهلكين" in html


def test_audit_warns_about_missing_rates_too(order, segmented_result):
    html = printing.get("audit").build_html(order, segmented_result)
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


@pytest.fixture(scope="module")
def underground_result():
    """مشروع أرضي فيه بند أجر بلا سعر — عدد مغذيات خارج جدول التعرفة."""
    from engine.project import compute_project
    from engine.types import Project, Segment, SidewalkType, Underground11kV

    project = Project(
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
    return compute_project(project, load_catalog())


@pytest.mark.parametrize("key", ["iso", "audit"])
def test_every_template_survives_an_underground_segment_with_a_missing_rate(
    key, order, underground_result, tmp_path, qapp
):
    """أهمّ اختبار: عدد مغذيات خارج جدول التعرفة يُنتج أجراً بلا سعر — لا انهيار (ق-٣٠)."""
    path = printing.get(key).write_pdf(order, underground_result, str(tmp_path / f"{key}.pdf"))
    assert (tmp_path / f"{key}.pdf").read_bytes().startswith(b"%PDF")


def test_audit_warns_about_the_out_of_table_civil_rate(order, underground_result):
    html = printing.get("audit").build_html(order, underground_result)
    assert "الأعمال المدنية" in html
    assert "بلا أجر" in html
