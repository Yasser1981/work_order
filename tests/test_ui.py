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


@pytest.fixture
def pug11(window):
    return window.add_segment(SegmentKind.UG11)


@pytest.fixture
def pug33(window):
    return window.add_segment(SegmentKind.UG33)


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


def test_missing_price_warning_is_shown(qapp, p11):
    """السعر المفقود يُعرض تحذيراً ولا يُحتسب صفراً بصمت.

    بسعر **مُحقون**: بعد ق-٣٦ صارت كل المواد مسعّرة، فربط الاختبار بمادة بعينها
    يجعله يفشل مع كل تحديث أسعار.
    """
    import copy

    catalog = copy.deepcopy(load_catalog())
    catalog["المواد"]["عمود 11م مشبك"]["السعر"] = None
    w = MainWindow(catalog)
    editor = w.add_segment(SegmentKind.HV11)

    editor.lattice.setValue(3)
    assert "عمود 11م مشبك" in w.warning.text()

    editor.lattice.setValue(0)
    assert w.warning.text() == "" or not w.warning.isVisible()


def test_no_warning_when_everything_is_priced(window, p11):
    """المشروع العادي بلا تحذير — كل المواد والأجور مسعّرة بعد ق-٣٦."""
    p11.route.setValue(1000)
    p11.stay.setValue(2)
    p11._adopt_suggestion()
    assert window.result["أسعار_مفقودة"] == []
    assert window.result["أجور_مفقودة"] == []
    assert not window.warning.text()


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


def test_warning_reports_both_missing_prices_and_missing_rates(qapp):
    """المادة بلا سعر والبند بلا أجر يظهران معاً في التحذير — بقيم مُحقونة."""
    import copy

    catalog = copy.deepcopy(load_catalog())
    catalog["المواد"]["كونكتر ربط مشتركين"]["السعر"] = None
    catalog["أجور_العمل"]["ربط المستهلكين"]["السعر"] = None
    w = MainWindow(catalog)
    editor = w.add_segment(SegmentKind.LV)

    editor.consumers.setValue(10)
    assert "كونكتر ربط مشتركين" in w.warning.text()
    assert "ربط المستهلكين" in w.warning.text()


def test_warning_renders_as_rich_text_not_raw_markup(window):
    """اللافتة في وضع RichText — وإلا ظهرت رموز HTML نصّاً خاماً للمستخدم."""
    from PyQt6.QtCore import Qt

    assert window.warning.textFormat() == Qt.TextFormat.RichText


def test_street_crossing_feeders_reach_the_engine(window):
    """حقول المغذيات موصولة فعلاً — التعرفة لمغذٍّ ولمتر (ق-٤٥)."""
    window.segments.street_main.setValue(10)
    window.segments.street_main_feeders.setValue(3)
    line = next(l for l in window.result["أجور_العمل"] if "الرئيسية" in l.name)
    assert line.qty == 30 and line.cost == 6_000_000
    # ولا أنبوب للرئيسية — حفر مخفي (ق-٤٦)
    assert not any("أنبوب" in m["المادة"] for m in window.result["المواد"])

    window.segments.street_secondary.setValue(10)
    window.segments.street_secondary_feeders.setValue(3)
    quantities = {m["المادة"]: m["الكمية"] for m in window.result["المواد"]}
    assert quantities["أنبوب 8 انج 10 بار"] == 7       # ⌈10÷6⌉ × 3 مغذيات + احتياط


def test_the_street_hint_shows_the_multiplication_and_the_pipes(window):
    window.segments.street_secondary.setValue(24)
    window.segments.street_secondary_feeders.setValue(2)
    text = window.segments.street_hint.text()
    assert "24 م × 2 مغذيات × 100,000 = <b>4,800,000 د</b>" in text
    assert "⌈24 ÷ 6⌉ × 2 + 1 احتياط = <b>9</b>" in text


def test_the_pipe_is_quantity_only_and_raises_no_warning(window):
    """كلفة الأنبوب ضمن أجر العبور — كمية بلا كلفة، ولا تحذير أصفر (ق-٤٦)."""
    window.segments.street_secondary.setValue(10)
    row = next(m for m in window.result["المواد"] if "أنبوب" in m["المادة"])
    assert row["كمية_فقط"] is True and row["الكلفة"] == 0
    assert not window.result["أسعار_مفقودة"]
    assert not window.warning.text()


# ═══════════════════ مقطع التجهيزات ═══════════════════


def test_equipment_segment_is_empty_by_default(window, pequip):
    """لا محولة ولا فاصل ما لم يُدخلهما المستخدم."""
    assert not pequip.equipment()
    assert not any(m["المادة"] == "محولة 400 KVA جهد 11/0.4 ك.ف" for m in window.result["المواد"])


def test_entering_a_transformer_adds_its_kit_and_its_labour(window, pequip):
    from engine.equipment import TransformerSize, TransformerVoltage

    pequip.transformers[
        (TransformerVoltage.KV11, TransformerSize.KVA400)
    ].setValue(1)
    names = [m["المادة"] for m in window.result["المواد"]]
    assert "محولة 400 KVA جهد 11/0.4 ك.ف" in names
    assert "لنك فيوز 11 ك.ف مع السلك" in names
    assert "نصب المحولة" in [l.name for l in window.result["أجور_العمل"]]


def test_the_33kv_transformer_has_its_own_field_and_its_own_accessories(window, pequip):
    """محولة 33/0.4: مانعة وفاصل فيوز 33 ك.ف، والقاطع يبقى 400 أمبير (ق-٣٧)."""
    from engine.equipment import TransformerSize, TransformerVoltage

    pequip.transformers[
        (TransformerVoltage.KV33, TransformerSize.KVA400)
    ].setValue(1)
    quantities = {m["المادة"]: m["الكمية"] for m in window.result["المواد"]}
    assert quantities["محولة 400 KVA جهد 33/0.4 ك.ف"] == 1
    assert quantities["مانعة صواعق 33 ك.ف"] == 1
    assert quantities["لنك فيوز 33 ك.ف مع السلك"] == 1
    assert quantities["قاطع دورة 400 أمبير مع المتسعة"] == 2   # لا يتبع الجهد
    assert quantities["قاعدة مانعة صواعق مع الملحقات"] == 1    # واحدة مهما اختلف الجهد
    assert "مانعة صواعق 11 KV" not in quantities
    assert "لنك فيوز 11 ك.ف مع السلك" not in quantities


def test_every_rating_is_offered_at_both_voltages(pequip):
    """ستة حقول: ثلاث سعات × جهدين — 250 متاحة بالجهدين معاً (ق-٣٨)."""
    from engine.equipment import TransformerSize, TransformerVoltage

    assert len(pequip.transformers) == 6
    for voltage in TransformerVoltage:
        for size in TransformerSize:
            assert (voltage, size) in pequip.transformers


def test_each_rating_has_its_own_field_and_pulls_its_own_breaker(window, pequip):
    """عدد المخارج يحكم القاطع والقابلو (ق-٢٧)."""
    from engine.equipment import TransformerSize, TransformerVoltage

    for size in TransformerSize:
        pequip.transformers[(TransformerVoltage.KV11, size)].setValue(1)
    quantities = {m["المادة"]: m["الكمية"] for m in window.result["المواد"]}
    for size in TransformerSize:
        assert quantities[f"محولة {size.value} KVA جهد 11/0.4 ك.ف"] == 1
    assert quantities["قاطع دورة 250 أمبير مع المتسعة"] == 2
    assert quantities["قاطع دورة 400 أمبير مع المتسعة"] == 2 + 4   # 400 و630 معاً
    assert quantities["قابلو نحاس 1×150 ملم²"] == 80 + 80 + 160
    # الملحق المشترك يُجمَّع من السعات الثلاث
    assert quantities["قاعدة محولة مع الملحقات"] == 3


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
    assert quantities["قابلو 1×185 ملم²"] == 20


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
    from engine.equipment import TransformerSize, TransformerVoltage

    pequip.transformers[
        (TransformerVoltage.KV11, TransformerSize.KVA400)
    ].setValue(2)
    text = pequip.transformer_hint.text()
    assert "قاطع دورة 400 أمبير مع المتسعة: <b>4</b>" in text
    assert "ترمنل 150 ملم²: <b>48</b>" in text   # 12 لكل مخرج × مخرجين × محولتين


def test_equipment_totals_reach_the_screen(window, pequip):
    """كل السعات في الجهدين مسعّرة بعد ق-٣٦ و ق-٣٧ — لا تحذير مع أيٍّ منها."""
    for key, field in pequip.transformers.items():
        field.setValue(1)
        assert f"{window.result['الكلفة_الكلية']:,.0f}" in window.total_all.text()
        assert not window.warning.text(), key
        field.setValue(0)


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


# ═══════════════════ مقطع الشبكة الأرضية 11 ك.ف ═══════════════════


def test_ug11_segment_is_empty_by_default(window, pug11):
    """لا قابلو ولا صناديق ما لم يُدخلها المستخدم."""
    assert not any(
        m["المادة"].startswith("قابلو 3×150") for m in window.result["المواد"]
    )


def test_ug11_cable_quantity_matches_the_users_example(window, pug11):
    """طول المسار × عدد المغذيات × 1.1 — يصل فعلاً إلى جدول المواد."""
    pug11.route.setValue(600)
    pug11.feeders.setValue(2)
    cable = next(
        m for m in window.result["المواد"] if m["المادة"].startswith("قابلو 3×150")
    )
    assert cable["الكمية"] == 1320


def test_ug11_adopt_button_matches_the_engine_suggestion(window, pug11):
    """350÷250 → 1، و600÷250 → 2 — نفس مثالَي المستخدم، عبر الواجهة لا المحرك مباشرة."""
    pug11.route.setValue(350)
    pug11.feeders.setValue(1)
    pug11._adopt_suggestion()
    assert pug11.straight_boxes.value() == 1

    pug11.route.setValue(600)
    pug11._adopt_suggestion()
    assert pug11.straight_boxes.value() == 2


def test_ug11_civil_works_depends_on_route_length_only(window, pug11):
    """الأعمال المدنية من طول المسار وحده — لا كمية القابلو المضروبة بالمغذيات."""
    from engine.underground import CIVIL_GROUP

    pug11.route.setValue(400)
    pug11.feeders.setValue(3)
    civil = [l for l in window.result["أجور_العمل"] if l.group == CIVIL_GROUP]
    # بندان بعد التفصيل: حفر الخندق وإعادة المسار (ق-٣٨)
    assert [l.name for l in civil] == [
        "حفر الخندق — رصيف ترابي، مسار ثلاثي",
        "إعادة المسار — رصيف ترابي، مسار ثلاثي",
    ]
    assert all(l.qty == 400 for l in civil)


def test_ug11_trench_hint_shows_the_width_and_the_quantities(window, pug11):
    """عرض الخندق رقم لا حقل له، ومع ذلك يحكم الرمل وتضاعف الشتايكر (ق-٤٣)."""
    pug11.route.setValue(900)
    pug11.feeders.setValue(5)
    text = pug11.trench_hint.text()
    assert "عرض الخندق لـ<b>5</b> مغذيات = <b>1 م</b>" in text
    assert "عريض" in text                       # التنبيه إلى المضاعفة
    quantities = {m["المادة"]: m["الكمية"] for m in window.result["المواد"]}
    assert quantities["شتايكر 50×50×5 سم"] == 3600      # ⌈900÷0.5⌉ × 2
    assert quantities["شريط تحذير"] == 20               # ⌈900÷90⌉ × 2
    assert quantities["رمل نهري"] == 360                # 900 × 1.0 × 0.4


def test_ug11_staker_does_not_multiply_below_the_wide_threshold(window, pug11):
    """1 و4 مغذيات: العرض 0.5 و0.8 م — كلاهما دون المتر فلا مضاعفة (ق-٤٣)."""
    def staker():
        return next(m["الكمية"] for m in window.result["المواد"]
                    if m["المادة"] == "شتايكر 50×50×5 سم")

    pug11.route.setValue(500)
    pug11.feeders.setValue(1)
    staker_one = staker()
    pug11.feeders.setValue(4)
    assert staker() == staker_one == 1000
    pug11.feeders.setValue(5)                 # العرض 1.0 م ← يتضاعف
    assert staker() == 2000


def test_ug11_civil_rate_extends_beyond_the_table_with_no_warning(window, pug11):
    """6 مغذيات: التعرفة تمتدّ بالصيغة، مفصَّلةً إلى مكوّنين، بلا تحذير (ق-٤٧)."""
    pug11.route.setValue(100)
    pug11.feeders.setValue(6)
    text = pug11.civil_hint.text()
    assert "⚠️" not in text
    assert "حفر الخندق: 100 م × 17,000 د/م" in text      # 11,000 + 3 × 2,000
    assert "إعادة المسار: 100 م × 26,000 د/م" in text     # 20,000 + 3 × 2,000
    assert "المجموع: 43,000 د/م" in text


def test_street_crossings_are_project_wide_fields_not_per_segment(window, pug11):
    """حقلا عبور الشوارع في لوحة المقاطع نفسها — لا داخل محرّر أي مقطع."""
    window.segments.street_secondary.setValue(50)
    window.segments.street_main.setValue(20)
    names = {l.name for l in window.result["أجور_العمل"]}
    assert "عبور الشوارع الفرعية" in names
    assert "عبور الشوارع الرئيسية – حفر مخفي" in names


def test_end_boxes_are_purely_manual_with_no_adopt_button_effect(window, pug11):
    pug11.route.setValue(500)
    pug11.end_internal.setValue(2)
    pug11.end_external.setValue(3)
    pug11._adopt_suggestion()          # يمسّ الصندوق المستقيم فقط
    assert pug11.end_internal.value() == 2
    assert pug11.end_external.value() == 3


def test_mixing_overhead_and_underground_segments_in_the_ui(window):
    """مشروع فيه شبكة هوائية وأرضية معاً في الواجهة نفسها."""
    hv = window.add_segment(SegmentKind.HV11)
    hv.route.setValue(500)
    hv._adopt_suggestion()
    ug = window.add_segment(SegmentKind.UG11)
    ug.route.setValue(300)
    names = {m["المادة"] for m in window.result["المواد"]}
    assert "عمود 11م مشبك" in names
    assert "قابلو 3×150 ملم² جهد 11 ك.ف" in names


# ═══════════════════ مقطع الشبكة الأرضية 33 ك.ف ═══════════════════


def test_ug33_segment_is_empty_by_default(window, pug33):
    assert not any(m["المادة"].startswith("قابلو 1×400") for m in window.result["المواد"])


def test_ug33_matches_the_users_worked_example(window, pug33):
    """500م مزدوجة الدائرة ← 3300م قابلو — عبر الواجهة لا المحرك مباشرة."""
    pug33.route.setValue(500)
    pug33.circuit.setCurrentIndex(1)          # مزدوجة
    cable = next(m for m in window.result["المواد"] if m["المادة"].startswith("قابلو 1×400"))
    assert cable["الكمية"] == 3300


def test_ug33_single_circuit_is_half_of_double(window, pug33):
    pug33.route.setValue(500)
    pug33.circuit.setCurrentIndex(0)          # مفردة
    cable = next(m for m in window.result["المواد"] if m["المادة"].startswith("قابلو 1×400"))
    assert cable["الكمية"] == 1650


def test_ug33_civil_works_treats_one_feeder_like_11kv(window, pug33):
    """المغذي الواحد (3 كابلات) يُعامَل معاملة مغذٍّ واحد — لا 3 — في الأعمال المدنية."""
    from engine.underground import CIVIL_GROUP

    pug33.route.setValue(500)
    pug33.circuit.setCurrentIndex(0)          # مفردة = مغذٍّ واحد
    civil = [l for l in window.result["أجور_العمل"] if l.group == CIVIL_GROUP]
    # تعرفة "1" — نفس عمود 11 ك.ف الأول: 7,000 حفر + 13,000 إعادة = 20,000
    assert [l.rate for l in civil] == [7000, 13000]
    assert sum(l.cost for l in civil) == 500 * 20000


def test_ug33_adopt_button_uses_the_cable_count(window, pug33):
    """1000م مزدوجة ببكرة 500م: لكل كابل صندوق × 6 كابلات = 6."""
    pug33.route.setValue(1000)
    pug33.circuit.setCurrentIndex(1)          # مزدوجة
    pug33.drum_length.setValue(500)
    pug33._adopt_suggestion()
    assert pug33.straight_boxes.value() == 6


def test_ug33_end_boxes_are_purely_manual(window, pug33):
    pug33.route.setValue(500)
    pug33.end_internal.setValue(2)
    pug33.end_external.setValue(1)
    pug33._adopt_suggestion()                 # يمسّ الصندوق المستقيم فقط
    assert pug33.end_internal.value() == 2
    assert pug33.end_external.value() == 1


def test_11kv_and_33kv_underground_segments_together_in_the_ui(window):
    ug11 = window.add_segment(SegmentKind.UG11)
    ug11.route.setValue(300)
    ug33 = window.add_segment(SegmentKind.UG33)
    ug33.route.setValue(500)
    names = {m["المادة"] for m in window.result["المواد"]}
    assert "قابلو 3×150 ملم² جهد 11 ك.ف" in names
    assert "قابلو 1×400 ملم² جهد 33 ك.ف" in names


# ═══════════════════ قفيص العمود المشبك — استرشادي (ق-٣٥) ═══════════════════


def test_cage_advisory_is_six_per_cable_head_isolator(window, pequip):
    """6 أقفاص لكل عمود مشبك عليه رأس قابلو، وأعمدة رأس القابلو = الفواصل عليه."""
    pequip.onload_11_head.setValue(1)
    pequip.isolator_33_head.setValue(2)
    pequip._adopt_cages()
    assert pequip.cages.value() == 18          # (1 + 2) × 6


def test_mid_network_isolators_do_not_add_cages(window, pequip):
    """فواصل منتصف الشبكة لا رأس قابلو لها — فلا أقفاص."""
    pequip.onload_11_mid.setValue(4)
    pequip.isolator_33_mid.setValue(4)
    pequip._adopt_cages()
    assert pequip.cages.value() == 0


def test_cage_count_stays_editable_after_adopting(window, pequip):
    """استرشادي غير مُلزِم — التعديل اليدوي بعد الاعتماد يبقى (ق-١٠)."""
    pequip.onload_11_head.setValue(1)
    pequip._adopt_cages()
    assert pequip.cages.value() == 6
    pequip.cages.setValue(5)
    quantities = {m["المادة"]: m["الكمية"] for m in window.result["المواد"]}
    assert quantities["قفيص عمود مشبك"] == 5


# ═══════════════════ صناديق نهاية 33 ك.ف: السيت 3 صناديق (ق-٣٥) ═══════════════════


def test_ug33_end_box_set_becomes_three_boxes_on_screen(window, pug33):
    pug33.route.setValue(500)
    pug33.end_internal.setValue(1)
    pug33.end_external.setValue(2)
    quantities = {m["المادة"]: m["الكمية"] for m in window.result["المواد"]}
    assert quantities["صندوق نهاية داخلي 1×400 ملم² جهد 33 ك.ف"] == 3
    assert quantities["صندوق نهاية خارجي 1×400 ملم² جهد 33 ك.ف"] == 6


def test_ug33_end_box_hint_shows_the_resulting_count(window, pug33):
    """اللافتة تُظهر العدد الفعلي كي لا يظنّ المستخدم أن مُدخَله هو الكمية."""
    pug33.end_internal.setValue(2)
    assert "6 صندوق" in pug33.end_box_hint.text()
