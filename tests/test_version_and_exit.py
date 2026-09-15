# -*- coding: utf-8 -*-
"""رقم الإصدار، وتأكيد الحذف، والتنبيه قبل الخروج بلا حفظ (ق-٨٠).

ثلاثة اقتراحات من المستخدم، يجمعها غرضٌ واحد: **ألّا يضيع عمل بصمت**، وألّا
يُسأل المستخدم سؤالاً بلا معنى فيعتاد تخطّي الأسئلة.
"""

import io
import re

import pytest

pytest.importorskip("PyQt6", reason="PyQt6 غير مثبَّت")

from pathlib import Path  # noqa: E402

from PyQt6.QtWidgets import QMessageBox  # noqa: E402

from engine import load_catalog  # noqa: E402
from engine.types import Network11kV, Project, Segment, SegmentKind  # noqa: E402
from engine.version import RELEASED, VERSION  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

CHANGELOG = Path(__file__).resolve().parent.parent / "docs" / "الإصدارات.md"


@pytest.fixture
def window(qapp):
    return MainWindow(load_catalog())


# ═════════════ ١. رقم الإصدار ═════════════


def test_the_version_matches_the_newest_entry_in_the_changelog():
    """**الحارس الذي يمنع رقماً بلا محتوى:** الرقم هنا = أحدث فقرة في السجلّ.

    فلا يُرفع رقم بلا أن يُكتب ما فيه، ولا يُكتب إصدار بلا أن يُرفع رقمه.
    """
    head = re.search(r"^## (\S+) — (\S+)$", io.open(CHANGELOG, encoding="utf-8").read(),
                     re.MULTILINE)
    assert head, "لا فقرة إصدار في docs/الإصدارات.md"
    assert head.group(1) == VERSION
    assert head.group(2) == RELEASED


def test_the_version_reads_like_a_version():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION), VERSION


def test_the_window_title_shows_the_version(window):
    assert VERSION in window.windowTitle()


def test_the_saved_file_records_the_program_version(window, tmp_path):
    """أثرٌ يجيب سؤال «بأي إصدار أُنتج هذا الملف؟» عند مراجعته بعد شهور."""
    import json

    path = window.save_to(tmp_path / "أمر")
    assert json.loads(path.read_text(encoding="utf-8"))["إصدار_البرنامج"] == VERSION


def test_an_old_file_without_the_version_still_opens(window, tmp_path):
    """**حارس التوافق:** الحقل للأثر لا للقراءة — فملف قديم بلا هذا الحقل يُفتح.

    ولولا هذا الحارس لأمكن أن يصير الحقل شرطاً للفتح، فتتعذّر قراءة كل ملف
    حُفظ قبل اليوم.
    """
    import json

    window.segments.load(Project("م", [Segment("أ", Network11kV(poles_lattice=3))]))
    path = window.save_to(tmp_path / "قديم")
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["إصدار_البرنامج"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    other = MainWindow(load_catalog())
    other.load_from(path)
    assert other.project().segments[0].content.poles_lattice == 3


def test_the_audit_sheet_carries_the_version_but_the_official_forms_do_not(qapp):
    """الأثر على الورقة الداخلية وحدها — ولا يُضاف سطر إلى نموذج معتمَد (ق-٠)."""
    import printing
    from engine.project import compute_project
    from engine.workorder import WorkOrder

    result = compute_project(
        Project("م", [Segment("أ", Network11kV(route_length_m=500, poles_lattice=3))]),
        load_catalog())
    order = WorkOrder(number="1")

    assert VERSION in printing.get("audit").build_html(order, result)
    for key in ("iso", "amana"):
        assert VERSION not in printing.get(key).build_html(order, result), key


# ═════════════ ٢. حذف المقطع: سؤالٌ حين يكون للسؤال معنى ═════════════


def test_an_untouched_segment_is_removed_without_a_question(window, monkeypatch):
    """سؤالٌ عمّا لا شيء فيه يُفقد السؤالَ معناه فيُنقَر بلا قراءة."""
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: asked.append(1)))

    window.add_segment(SegmentKind.HV11)
    window.segments.list.setCurrentRow(0)
    assert window.segments.is_empty(0)

    window.segments._remove_segment()
    assert asked == []
    assert window.project().segments == []


def test_a_filled_segment_asks_before_it_disappears(window, monkeypatch):
    asked = []

    def question(parent, title, text, *args, **kwargs):
        asked.append(text)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))

    editor = window.add_segment(SegmentKind.HV11)
    editor.route.setValue(500)
    editor.lattice.setValue(9)
    window.segments.list.setCurrentRow(0)
    assert not window.segments.is_empty(0)

    window.segments._remove_segment()
    assert asked, "حُذف مقطع ممتلئ بلا سؤال"
    assert len(window.project().segments) == 1        # «لا» تُبقيه


def test_the_question_says_how_much_work_is_at_stake(window, monkeypatch):
    """«تُفقَد معطياته» لا تُقدِّر الخسارة — أما «12 بند مواد» فرقمٌ يُقرَّر عليه."""
    texts = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda parent, title, text, *a, **k: (texts.append(text),
                                              QMessageBox.StandardButton.No)[1]))

    editor = window.add_segment(SegmentKind.HV11)
    editor.route.setValue(500)
    editor.lattice.setValue(9)
    window.segments.list.setCurrentRow(0)
    window.segments._remove_segment()

    assert "المواد" in texts[0] and "الأجور" in texts[0]
    assert re.search(r"\d+ بن(ود|داً) من المواد", texts[0]), texts[0]


def test_emptiness_is_judged_against_a_fresh_segment_of_the_same_kind(window):
    """أي حقل يُضاف مستقبلاً يدخل الفحص تلقائياً — لا قائمة حقول مكتوبة."""
    editor = window.add_segment(SegmentKind.UG11)
    window.segments.list.setCurrentRow(0)
    assert window.segments.is_empty(0)

    editor.end_internal.setValue(1)          # حقلٌ واحد يكفي لجعله «ممتلئاً»
    assert not window.segments.is_empty(0)


# ═════════════ ٣. الخروج بلا حفظ ═════════════


def test_a_fresh_window_is_not_dirty(window):
    assert window.dirty is False


def test_editing_marks_the_order_dirty(window):
    window.order_panel.number.setText("45")
    assert window.dirty is True
    assert window.windowTitle().startswith("•")


def test_editing_a_segment_marks_it_dirty_too(window):
    window.add_segment(SegmentKind.HV11)
    assert window.dirty is True


def test_saving_clears_the_flag(window, tmp_path):
    window.order_panel.number.setText("45")
    window.save_to(tmp_path / "أمر")
    assert window.dirty is False
    assert not window.windowTitle().startswith("•")


def test_opening_a_file_clears_the_flag(window, tmp_path):
    window.segments.load(Project("م", [Segment("أ", Network11kV(poles_lattice=3))]))
    path = window.save_to(tmp_path / "أمر")

    other = MainWindow(load_catalog())
    other.load_from(path)
    assert other.dirty is False


def test_switching_the_price_version_counts_as_an_edit(window, monkeypatch):
    """اسم النسخة يُحفظ في الملف، فتغييره يجعل الشاشة تخالف القرص."""
    monkeypatch.setattr("ui.main_window.load_catalog", lambda *a: window.catalog)
    window.switch_version(window.version)
    assert window.dirty is True


def _close(window, answer):
    """يغلق النافذة بجواب محدَّد، ويعيد ما إذا قُبل الإغلاق."""
    from PyQt6.QtGui import QCloseEvent

    event = QCloseEvent()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: answer))
        window.closeEvent(event)
    return event.isAccepted()


def test_closing_a_clean_window_asks_nothing(window, monkeypatch):
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: asked.append(1)))
    from PyQt6.QtGui import QCloseEvent

    event = QCloseEvent()
    window.closeEvent(event)
    assert asked == []
    assert event.isAccepted()


def test_closing_with_unsaved_work_asks_first(window):
    window.order_panel.number.setText("45")
    assert _close(window, QMessageBox.StandardButton.Discard) is True


def test_cancel_keeps_the_program_open(window):
    """**الحارس الأهمّ في هذا الباب:** «إلغاء» لا تُغلق شيئاً."""
    window.order_panel.number.setText("45")
    assert _close(window, QMessageBox.StandardButton.Cancel) is False
    assert window.dirty is True


def test_choosing_save_writes_the_file_then_closes(window, tmp_path, monkeypatch):
    window.segments.load(Project("م", [Segment("أ", Network11kV(poles_lattice=3))]))
    path = tmp_path / "أمر.wo"
    monkeypatch.setattr("ui.main_window.QFileDialog.getSaveFileName",
                        staticmethod(lambda *a, **k: (str(path), "")))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    assert _close(window, QMessageBox.StandardButton.Save) is True
    assert path.exists()
    assert window.dirty is False


def test_a_cancelled_save_does_not_close_the_program(window, monkeypatch):
    """أخطر حالة: طلب الحفظ ثم أُلغي حواره — فالخروج حينها يضيّع ما طُلب حفظه."""
    window.segments.load(Project("م", [Segment("أ", Network11kV(poles_lattice=3))]))
    monkeypatch.setattr("ui.main_window.QFileDialog.getSaveFileName",
                        staticmethod(lambda *a, **k: ("", "")))

    assert _close(window, QMessageBox.StandardButton.Save) is False
    assert window.dirty is True


@pytest.mark.parametrize("count,expected", [
    (1, "بند المواد واحد"), (2, "بندان من المواد"),
    (5, "5 بنود من المواد"), (12, "12 بنداً من المواد"), (0, ""),
])
def test_the_count_reads_as_proper_arabic(count, expected):
    """«3 بند مواد» ركيك — والرسالة تُقرأ في لحظة قرارٍ لا رجعة فيه."""
    from ui.segments_panel import _items

    assert _items(count, "المواد") == expected
