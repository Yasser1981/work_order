# -*- coding: utf-8 -*-
"""اختبارات الواجهة — تتأكّد أن الواجهة تعكس المحرك بلا انحراف.

تعمل بلا شاشة عبر QT_QPA_PLATFORM=offscreen (يُضبط في conftest.py).
"""

import pytest

pytest.importorskip("PyQt6", reason="PyQt6 غير مثبَّت")

from engine import load_catalog  # noqa: E402
from engine.overhead import suggest_poles_11kv  # noqa: E402
from engine.project import compute_project  # noqa: E402
from engine.types import Project, SegmentKind  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


@pytest.fixture
def window(qapp):
    return MainWindow(load_catalog())


@pytest.fixture
def p11(window):
    """مقطع شبكة 11 ك.ف جاهز للتحرير."""
    return window.add_segment(SegmentKind.HV11)


@pytest.fixture
def p33(window):
    return window.add_segment(SegmentKind.HV33)


@pytest.fixture
def plv(window):
    return window.add_segment(SegmentKind.LV)


@pytest.fixture
def pequip(window):
    return window.add_segment(SegmentKind.EQUIPMENT)


# ═══════════════════ المقاطع ═══════════════════


def test_a_new_project_starts_with_no_segments(window):
    """المشروع يبدأ فارغاً — لا شبكة تسلّلت إلى التخمين قبل أن يُدخلها المستخدم."""
    assert window.segments.segments() == []
    assert window.result["المواد"] == []
    assert window.materials.rowCount() == 0


def test_adding_a_segment_names_it_and_shows_its_editor(window):
    from ui.panels import Panel11kV

    editor = window.add_segment(SegmentKind.HV11)
    assert isinstance(editor, Panel11kV)
    assert window.segments.segments()[0].name == "المقطع الأول"
    assert window.segments.stack.currentWidget() is editor


def test_each_kind_gets_its_own_editor(window):
    from ui.panels import Panel11kV, Panel33kV, PanelEquipment, PanelLV

    pairs = [
        (SegmentKind.HV11, Panel11kV),
        (SegmentKind.HV33, Panel33kV),
        (SegmentKind.LV, PanelLV),
        (SegmentKind.EQUIPMENT, PanelEquipment),
    ]
    for kind, cls in pairs:
        assert isinstance(window.add_segment(kind), cls)
    assert [s.kind for s in window.segments.segments()] == [k for k, _ in pairs]


def test_segments_of_the_same_kind_are_independent(window):
    """مقطعان مزدوج ومفرد — كلٌّ بحساباته. هذا كل سبب وجود المقاطع."""
    from engine.types import CircuitType

    a = window.add_segment(SegmentKind.HV11)
    b = window.add_segment(SegmentKind.HV11)
    a.route.setValue(1000)
    a.circuit.setCurrentIndex(1)      # مزدوجة
    b.route.setValue(1000)
    b.circuit.setCurrentIndex(0)      # مفردة

    segments = window.segments.segments()
    assert segments[0].content.circuit is CircuitType.DOUBLE
    assert segments[1].content.circuit is CircuitType.SINGLE
    wire = next(m for m in window.result["المواد"] if m["المادة"].startswith("سلك ألمنيوم 120"))
    assert wire["الكمية"] == 6600 + 3300


def test_renaming_a_segment_reaches_the_breakdown(window):
    editor = window.add_segment(SegmentKind.HV11)
    editor.route.setValue(500)
    window.segments.name.setText("خط المستشفى")
    window.segments._rename_current("خط المستشفى")
    wire = next(m for m in window.result["المواد"] if m["المادة"].startswith("سلك ألمنيوم 120"))
    assert wire["تفصيل"][0]["المصدر"].startswith("خط المستشفى ←")


def test_removing_a_segment_removes_its_materials(window):
    editor = window.add_segment(SegmentKind.HV11)
    editor.route.setValue(500)
    assert window.result["المواد"]
    window.segments.list.setCurrentRow(0)
    window.segments._remove_segment()
    assert window.segments.segments() == []
    assert window.result["المواد"] == []


def test_moving_a_segment_reorders_the_project(window):
    a = window.add_segment(SegmentKind.HV11)
    window.add_segment(SegmentKind.LV)
    window.segments.list.setCurrentRow(1)
    window.segments._move(-1)
    assert [s.kind for s in window.segments.segments()] == [
        SegmentKind.LV, SegmentKind.HV11
    ]
    # المحرّر تبع مقطعه ولم يتشتّت الربط
    assert window.segments.editor(1) is a


def test_the_junction_note_appears_only_with_more_than_one_segment(window):
    window.add_segment(SegmentKind.HV11)
    assert window.segments.note.isHidden()
    window.add_segment(SegmentKind.HV11)
    assert not window.segments.note.isHidden()
    assert "عمود شد واحداً" in window.segments.note.text()


def test_move_buttons_disable_at_the_ends(window):
    window.add_segment(SegmentKind.HV11)
    window.add_segment(SegmentKind.HV11)
    window.segments.list.setCurrentRow(0)
    assert not window.segments.up.isEnabled() and window.segments.down.isEnabled()
    window.segments.list.setCurrentRow(1)
    assert window.segments.up.isEnabled() and not window.segments.down.isEnabled()


# ═══════════════════ الحساب والعرض ═══════════════════


def test_window_builds_and_computes(window, p11):
    p11.route.setValue(500)
    p11._adopt_suggestion()
    assert window.materials.rowCount() > 0
    assert window.labour.rowCount() > 0


def test_adopt_button_matches_engine_suggestion(window, p11):
    """ق-١٠: زرّ الاعتماد ينقل مقترح المحرك حرفياً — لا حساب موازٍ في الواجهة."""
    p11.route.setValue(1000)
    expected = suggest_poles_11kv(p11.network(), window.catalog)
    p11._adopt_suggestion()
    assert p11.lattice.value() == expected.lattice
    assert p11.round_.value() == expected.round_


def test_user_spans_flow_through_to_suggestion(window, p11):
    """ق-٢٠: تغيير المسافات في الواجهة يغيّر المقترح."""
    p11.route.setValue(1000)
    p11.span.setValue(25)
    p11.tension_span.setValue(125)
    p11._adopt_suggestion()
    assert (p11.lattice.value(), p11.round_.value()) == (9, 32)

    p11.span.setValue(40)
    p11._adopt_suggestion()
    assert (p11.lattice.value(), p11.round_.value()) == (10, 16)


def test_totals_match_engine_exactly(window, p11):
    """الواجهة تعرض ما يحسبه المحرك — بلا فرق ولو دينار واحد."""
    p11.route.setValue(500)
    p11._adopt_suggestion()
    result = compute_project(Project(segments=window.segments.segments()), window.catalog)
    assert f"{result['الكلفة_الكلية']:,.0f}" in window.total_all.text()


def test_missing_price_warning_is_shown(window, p11):
    """السعر المفقود يُعرض تحذيراً ولا يُحتسب صفراً بصمت."""
    p11.stay.setValue(2)          # يُدخل «واير ستي» وهو بلا سعر
    assert window.warning.isVisible() or "واير ستي" in window.warning.text()

    p11.stay.setValue(0)
    window.recalculate()
    assert window.warning.text() == "" or not window.warning.isVisible()


def test_waste_field_disabled_when_length_already_includes_it(p11):
    """ق-٢: تفعيل «الطول يشمل الزيادة» يُعطّل حقل النسبة."""
    p11.waste_included.setChecked(True)
    assert not p11.waste_pct.isEnabled()
    p11.waste_included.setChecked(False)
    assert p11.waste_pct.isEnabled()


def test_bracket_pattern_only_enabled_for_double_circuit(p11):
    """نمط البراكيت خاص بالمزدوجة."""
    p11.circuit.setCurrentIndex(0)   # مفردة
    assert not p11.pattern.isEnabled()
    p11.circuit.setCurrentIndex(1)   # مزدوجة
    assert p11.pattern.isEnabled()


def test_33kv_adopt_matches_engine(p33):
    p33.route.setValue(2000)
    p33._adopt_suggestion()
    assert p33.suspension.value() == 27
    assert p33.anchors_mid.value() == 3
    assert p33.anchors_end.value() == 2


# ═══════════════════ ربط الطباعة بالواجهة ═══════════════════


def _fill_order(window):
    """يملأ حقول أمر العمل بقيم معروفة."""
    from PyQt6.QtCore import QDate

    p = window.order_panel
    p.number.setText("45")
    p.classification.setText("توسعات")
    p.project_name.setText("شبكة حي الحسين / كربلاء")
    p.duration.setText("90 يوم")
    p.order_date.setDate(QDate(2026, 8, 19))
    p.start_date.setDate(QDate(2026, 9, 1))
    p.work_scope.setPlainText("مد خط هوائي 11 ك.ف")
    p.notes.setPlainText("وفق المواصفات المعتمدة")
    p.staff.cellWidget(0, 1).setValue(2)      # مهندس: العدد
    p.staff.cellWidget(0, 2).setValue(30)     # مهندس: عدد الأيام
    p.equipment.cellWidget(2, 1).setValue(1)  # رافعة


def test_order_panel_builds_workorder_from_fields(window):
    _fill_order(window)
    order = window.order_panel.order()
    assert order.number == "45"
    assert order.classification == "توسعات"
    assert order.project_name == "شبكة حي الحسين / كربلاء"
    assert order.order_date.isoformat() == "2026-08-19"
    assert order.start_date.isoformat() == "2026-09-01"
    assert order.staff[0].count == 2 and order.staff[0].days == 30
    assert order.equipment[2].count == 1


def test_unfilled_counts_are_none_not_zero(window):
    """الصفر يعني «غير مُدخَل» فيُطبع فارغاً — لا صفراً في النموذج الورقي."""
    order = window.order_panel.order()
    assert order.staff[1].count is None
    assert order.equipment[0].days is None


def test_print_button_writes_pdf_with_header_fields(window, p11, tmp_path):
    """أهمّ اختبار: ما يُدخله المستخدم في الواجهة يصل فعلاً إلى النموذج المطبوع."""
    from printing.iso_form import build_html

    p11.route.setValue(500)
    p11._adopt_suggestion()
    _fill_order(window)

    path = str(tmp_path / "order.pdf")
    assert window.write_order_pdf(path) == path
    assert (tmp_path / "order.pdf").read_bytes().startswith(b"%PDF")

    html = build_html(window.order_panel.order(), window.result)
    assert "أمر عمل رقم 45" in html
    assert "شبكة حي الحسين / كربلاء" in html
    assert "2026/08/19" in html
    assert "عمود 11م مشبك" in html


def test_printed_totals_match_the_screen(window, p11, tmp_path):
    """الكلفة في النموذج المطبوع هي نفسها المعروضة على الشاشة."""
    from printing.iso_form import build_html

    p11.route.setValue(500)
    p11._adopt_suggestion()
    html = build_html(window.order_panel.order(), window.result)
    printed = f"{window.result['الكلفة_الكلية']:,.0f}"
    assert printed in html
    assert printed in window.total_all.text()


def test_pdf_extension_is_added_when_missing(window, p11, tmp_path):
    p11.route.setValue(500)
    p11._adopt_suggestion()
    result = window.write_order_pdf(str(tmp_path / "بلا_امتداد"))
    assert result.endswith(".pdf")
    assert (tmp_path / "بلا_امتداد.pdf").exists()


def test_print_refuses_when_there_are_no_materials(window, tmp_path):
    """مشروع فارغ لا يُنتج أمر عمل — يُرفض صراحةً بدل إخراج نموذج فارغ."""
    window.recalculate()

    with pytest.raises(ValueError):
        window.write_order_pdf(str(tmp_path / "x.pdf"))
    assert not (tmp_path / "x.pdf").exists()


def test_export_pdf_has_no_blocking_dialog_in_the_write_path():
    """حارس تصميمي: دالة الكتابة خالية من الحوارات الحاجزة.

    خلط الحوارات بمنطق الكتابة عطّل الاختبارات مرة، فيمنعه هذا الاختبار مستقبلاً.
    """
    import inspect

    from ui.main_window import MainWindow

    source = inspect.getsource(MainWindow.write_order_pdf)
    assert "QMessageBox" not in source
    assert "QFileDialog" not in source


# ═══════════════════ مقطع الضغط الواطئ ═══════════════════


def test_lv_segment_needs_no_enable_checkbox(plv):
    """وجود المقطع نفسه هو التفعيل — مربّع تفعيل ثانٍ فوقه يُربك لا أكثر (ق-٢٤)."""
    assert plv.enabled.isHidden()
    assert plv.enabled.isChecked()


def test_enabling_lv_adds_its_materials(window, plv):
    plv.route.setValue(1000)
    plv._adopt_suggestion()
    names = [m["المادة"] for m in window.result["المواد"]]
    assert "عمود 9م مشبك" in names
    assert "سلك ألمنيوم 95 ملم²" in names


def test_lv_adopt_matches_engine(plv):
    """20 م بين الأعمدة و100 م بين أعمدة الشد."""
    plv.route.setValue(1000)
    plv._adopt_suggestion()
    assert plv.lattice.value() == 11
    assert plv.round_.value() == 40


def test_lv_kind_switches_the_material(window, plv):
    plv.route.setValue(500)
    plv.kind.setCurrentIndex(0)          # أسلاك
    assert any(m["المادة"] == "سلك ألمنيوم 95 ملم²" for m in window.result["المواد"])
    plv.kind.setCurrentIndex(1)          # قابلو معلق
    names = [m["المادة"] for m in window.result["المواد"]]
    assert "قابلو ألمنيوم معلق 3×120+95+16 ملم²" in names
    assert "سلك ألمنيوم 95 ملم²" not in names


def test_mixed_low_voltage_project(window):
    """مقطع بالأسلاك ومقطع بالقابلو المعلق معاً — ما كان مستحيلاً قبل المقاطع."""
    a = window.add_segment(SegmentKind.LV)
    b = window.add_segment(SegmentKind.LV)
    a.route.setValue(400)
    a.kind.setCurrentIndex(1)            # قابلو معلق
    b.route.setValue(600)
    b.kind.setCurrentIndex(0)            # أسلاك
    names = [m["المادة"] for m in window.result["المواد"]]
    assert "قابلو ألمنيوم معلق 3×120+95+16 ملم²" in names
    assert "سلك ألمنيوم 95 ملم²" in names


def test_hv_pole_fields_follow_their_checkbox(plv):
    plv.on_hv.setChecked(False)
    assert not plv.hv_lattice.isEnabled()
    plv.on_hv.setChecked(True)
    assert plv.hv_lattice.isEnabled()


def test_warning_reports_both_missing_prices_and_missing_rates(window, plv):
    """المادة بلا سعر والبند بلا أجر يظهران معاً في التحذير."""
    plv.consumers.setValue(10)
    assert "كونكتر ربط مشتركين" in window.warning.text()
    assert "ربط المستهلكين" in window.warning.text()


def test_warning_renders_as_rich_text_not_raw_markup(window):
    """اللافتة في وضع RichText — وإلا ظهرت رموز HTML نصّاً خاماً للمستخدم."""
    from PyQt6.QtCore import Qt

    assert window.warning.textFormat() == Qt.TextFormat.RichText


# ═══════════════════ مقطع التجهيزات ═══════════════════


def test_equipment_segment_is_empty_by_default(window, pequip):
    """لا محولة ولا فاصل ما لم يُدخلهما المستخدم."""
    assert not pequip.equipment()
    assert not any(m["المادة"] == "محولة 400 KVA" for m in window.result["المواد"])


def test_entering_a_transformer_adds_its_kit_and_its_labour(window, pequip):
    from engine.equipment import TransformerSize

    pequip.transformers[TransformerSize.KVA400].setValue(1)
    names = [m["المادة"] for m in window.result["المواد"]]
    assert "محولة 400 KVA" in names
    assert "لنك فيوز 15 KV مع سلك فيوز 40 أمبير" in names
    assert "نصب المحولة" in [l.name for l in window.result["أجور_العمل"]]


def test_each_rating_has_its_own_field_and_pulls_its_own_breaker(window, pequip):
    """قاطع الدورة يتبع السعة رقماً برقم (ق-٢٦)."""
    from engine.equipment import TransformerSize

    for size in TransformerSize:
        pequip.transformers[size].setValue(1)
    quantities = {m["المادة"]: m["الكمية"] for m in window.result["المواد"]}
    for size in TransformerSize:
        assert quantities[f"محولة {size.value} KVA"] == 1
        assert quantities[f"قاطع دورة {size.value} أمبير مع المتسعة"] == 2
    # الملحق المشترك يُجمَّع من السعات الثلاث
    assert quantities["قاعدة محولة 2.4 متر"] == 3


def test_both_onload_positions_feed_one_labour_line(window, pequip):
    pequip.onload_11_mid.setValue(2)
    pequip.onload_11_head.setValue(3)
    labour = [l for l in window.result["أجور_العمل"] if l.name == "نصب الفاصل ON-LOAD"]
    assert len(labour) == 1 and labour[0].qty == 5


def test_the_two_isolator_voltages_use_their_own_cables(window, pequip):
    """الحقول الأربعة موصولة فعلاً بالمحرك، وكلٌّ يجرّ قابلوه (ق-٢٥)."""
    pequip.onload_11_mid.setValue(1)
    pequip.isolator_33_mid.setValue(1)
    quantities = {m["المادة"]: m["الكمية"] for m in window.result["المواد"]}
    assert quantities["قابلو نحاس 1×150 ملم²"] == 20
    assert quantities["قابلو 1×185 ملم2"] == 20


def test_cable_head_halves_the_cable_on_screen(window, pequip):
    pequip.onload_11_head.setValue(1)
    quantities = {m["المادة"]: m["الكمية"] for m in window.result["المواد"]}
    assert quantities["قابلو نحاس 1×150 ملم²"] == 10
    assert quantities["مانعة صواعق 11 KV"] == 1


def test_mid_network_isolator_pulls_no_arrester_on_screen(window, pequip):
    pequip.onload_11_mid.setValue(3)
    assert not any("مانعة" in m["المادة"] for m in window.result["المواد"])


def test_equipment_hint_lists_the_kit_so_the_checker_sees_it(pequip):
    """المستخدم يرى ما تجرّه المحولة قبل الطباعة لا بعدها."""
    from engine.equipment import TransformerSize

    pequip.transformers[TransformerSize.KVA400].setValue(2)
    text = pequip.transformer_hint.text()
    assert "قاطع دورة 400 أمبير مع المتسعة: <b>4</b>" in text
    assert "ترمنل 150 ملم²: <b>60</b>" in text


def test_equipment_totals_reach_the_screen(window, pequip):
    from engine.equipment import TransformerSize

    pequip.transformers[TransformerSize.KVA400].setValue(1)
    assert f"{window.result['الكلفة_الكلية']:,.0f}" in window.total_all.text()
    assert not window.warning.text()          # سعة 400 مسعّرة بالكامل

    pequip.transformers[TransformerSize.KVA630].setValue(1)
    assert "محولة 630 KVA" in window.warning.text()


def test_labour_rows_merge_across_segments(window):
    """بند «نصب عمود مشبك 11م» سطر واحد في الجدول مهما تعدّدت المقاطع."""
    for _ in range(3):
        editor = window.add_segment(SegmentKind.HV11)
        editor.route.setValue(200)
        editor._adopt_suggestion()
    rows = [
        window.labour.item(r, 0).text() for r in range(window.labour.rowCount())
    ]
    assert rows.count("نصب عمود مشبك 11م") == 1
