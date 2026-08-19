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
