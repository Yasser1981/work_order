# -*- coding: utf-8 -*-
"""اختبارات الواجهة — تتأكّد أن الواجهة تعكس المحرك بلا انحراف.

تعمل بلا شاشة عبر QT_QPA_PLATFORM=offscreen (يُضبط في conftest.py).
"""

import pytest

pytest.importorskip("PyQt6", reason="PyQt6 غير مثبَّت")

from engine import load_catalog  # noqa: E402
from engine.overhead import compute, suggest_poles_11kv  # noqa: E402
from engine.types import OverheadProject  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


@pytest.fixture
def window(qapp):
    return MainWindow(load_catalog())


def test_window_builds_and_computes(window):
    assert window.materials.rowCount() > 0
    assert window.labour.rowCount() > 0


def test_adopt_button_matches_engine_suggestion(window):
    """ق-١٠: زرّ الاعتماد ينقل مقترح المحرك حرفياً — لا حساب موازٍ في الواجهة."""
    window.panel11.route.setValue(1000)
    expected = suggest_poles_11kv(window.panel11.network(), window.catalog)
    window.panel11._adopt_suggestion()
    assert window.panel11.lattice.value() == expected.lattice
    assert window.panel11.round_.value() == expected.round_


def test_user_spans_flow_through_to_suggestion(window):
    """ق-٢٠: تغيير المسافات في الواجهة يغيّر المقترح."""
    window.panel11.route.setValue(1000)
    window.panel11.span.setValue(25)
    window.panel11.tension_span.setValue(125)
    window.panel11._adopt_suggestion()
    assert (window.panel11.lattice.value(), window.panel11.round_.value()) == (9, 32)

    window.panel11.span.setValue(40)
    window.panel11._adopt_suggestion()
    assert (window.panel11.lattice.value(), window.panel11.round_.value()) == (10, 16)


def test_totals_match_engine_exactly(window):
    """الواجهة تعرض ما يحسبه المحرك — بلا فرق ولو دينار واحد."""
    window.panel11.route.setValue(500)
    window.panel11._adopt_suggestion()
    result = compute(
        OverheadProject(net11=window.panel11.network(), net33=window.panel33.network()),
        window.catalog,
    )
    assert f"{result['الكلفة_الكلية']:,.0f}" in window.total_all.text()


def test_missing_price_warning_is_shown(window):
    """السعر المفقود يُعرض تحذيراً ولا يُحتسب صفراً بصمت."""
    window.panel11.stay.setValue(2)          # يُدخل «واير ستي» وهو بلا سعر
    assert window.warning.isVisible() or "واير ستي" in window.warning.text()

    window.panel11.stay.setValue(0)
    window.recalculate()
    assert window.warning.text() == "" or not window.warning.isVisible()


def test_waste_field_disabled_when_length_already_includes_it(window):
    """ق-٢: تفعيل «الطول يشمل الزيادة» يُعطّل حقل النسبة."""
    window.panel11.waste_included.setChecked(True)
    assert not window.panel11.waste_pct.isEnabled()
    window.panel11.waste_included.setChecked(False)
    assert window.panel11.waste_pct.isEnabled()


def test_bracket_pattern_only_enabled_for_double_circuit(window):
    """نمط البراكيت خاص بالمزدوجة."""
    window.panel11.circuit.setCurrentIndex(0)   # مفردة
    assert not window.panel11.pattern.isEnabled()
    window.panel11.circuit.setCurrentIndex(1)   # مزدوجة
    assert window.panel11.pattern.isEnabled()


def test_33kv_adopt_matches_engine(window):
    window.panel33.route.setValue(2000)
    window.panel33._adopt_suggestion()
    assert window.panel33.suspension.value() == 27
    assert window.panel33.anchors_mid.value() == 3
    assert window.panel33.anchors_end.value() == 2


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


def test_print_button_writes_pdf_with_header_fields(window, tmp_path):
    """أهمّ اختبار: ما يُدخله المستخدم في الواجهة يصل فعلاً إلى النموذج المطبوع."""
    from printing.iso_form import build_html

    window.panel11.route.setValue(500)
    window.panel11._adopt_suggestion()
    _fill_order(window)

    path = str(tmp_path / "order.pdf")
    assert window.write_order_pdf(path) == path
    assert (tmp_path / "order.pdf").read_bytes().startswith(b"%PDF")

    html = build_html(window.order_panel.order(), window.result)
    assert "أمر عمل رقم 45" in html
    assert "شبكة حي الحسين / كربلاء" in html
    assert "2026/08/19" in html
    assert "عمود 11م مشبك" in html


def test_printed_totals_match_the_screen(window, tmp_path):
    """الكلفة في النموذج المطبوع هي نفسها المعروضة على الشاشة."""
    from printing.iso_form import build_html

    window.panel11.route.setValue(500)
    window.panel11._adopt_suggestion()
    html = build_html(window.order_panel.order(), window.result)
    printed = f"{window.result['الكلفة_الكلية']:,.0f}"
    assert printed in html
    assert printed in window.total_all.text()


def test_pdf_extension_is_added_when_missing(window, tmp_path):
    window.panel11.route.setValue(500)
    window.panel11._adopt_suggestion()
    result = window.write_order_pdf(str(tmp_path / "بلا_امتداد"))
    assert result.endswith(".pdf")
    assert (tmp_path / "بلا_امتداد.pdf").exists()


def test_print_refuses_when_there_are_no_materials(window, tmp_path):
    """مشروع فارغ لا يُنتج أمر عمل — يُرفض صراحةً بدل إخراج نموذج فارغ."""
    window.panel11.route.setValue(0)
    window.panel11.lattice.setValue(0)
    window.panel11.round_.setValue(0)
    window.panel11.stay.setValue(0)
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
