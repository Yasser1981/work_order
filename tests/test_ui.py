# -*- coding: utf-8 -*-
"""اختبارات الواجهة — تتأكّد أن الواجهة تعكس المحرك بلا انحراف.

تعمل بلا شاشة عبر QT_QPA_PLATFORM=offscreen (يُضبط في conftest.py).
"""

import pytest

pytest.importorskip("PyQt6", reason="PyQt6 غير مثبَّت")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from engine import load_catalog  # noqa: E402
from engine.overhead import compute, suggest_poles_11kv  # noqa: E402
from engine.types import OverheadProject  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
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
