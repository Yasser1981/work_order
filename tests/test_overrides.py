# -*- coding: utf-8 -*-
"""التعديل اليدوي على الكميات — طبقةٌ فوق الحساب لا داخله (ق-٨٢).

**شرط المستخدم الذي تحرسه هذه الاختبارات:** «أهمّ شيء الحسابات والنتائج الرئيسية
لا تُمسّ ويمكن العودة إليها». فالحارس الأول هنا ليس أن التعديل يعمل، بل أن
**إلغاءه يعيد كل رقم كما كان** — وأن غيابه يعني غياب الطبقة تماماً.
"""

import pytest

pytest.importorskip("PyQt6", reason="PyQt6 غير مثبَّت")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QMessageBox  # noqa: E402

from engine import load_catalog  # noqa: E402
from engine.overrides import ambiguous_labour, apply, key_of, summary  # noqa: E402
from engine.project import compute_project  # noqa: E402
from engine.types import (  # noqa: E402
    CircuitType,
    Network33kV,
    Network11kV,
    Project,
    Segment,
    Underground11kV,
)
from ui.main_window import MainWindow  # noqa: E402


def compute(*contents, **project):
    return compute_project(
        Project("م", [Segment("", content) for content in contents], **project),
        load_catalog())


@pytest.fixture(scope="module")
def base():
    return compute(Network11kV(route_length_m=750, poles_lattice=9, poles_round=15),
                   Underground11kV(route_length_m=300, feeder_count=2))


def material(result, needle: str) -> dict:
    return next(row for row in result["المواد"] if needle in row["المادة"])


def labour(result, needle: str):
    return next(line for line in result["أجور_العمل"] if needle in line.name)


def wire_key(result) -> str:
    row = material(result, "سلك ألمنيوم")
    return key_of(row["المادة"], row["الوحدة"])


# ═════════ ١. غياب التعديل = غياب الطبقة ═════════


def test_with_no_overrides_the_result_is_the_very_same_object(base):
    """ليست نسخةً مطابقة بل **الكائن نفسه** — فلا طبقة تمرّ عليها النتيجة أصلاً."""
    assert apply(base) is base
    assert apply(base, {}, {}) is base
    assert apply(base, {"لا شيء": None}) is base


def test_the_engine_result_is_never_mutated(base):
    """الأصل يبقى كما هو بعد التعديل — وعليه يقوم التراجع كله."""
    before = material(base, "سلك ألمنيوم")["الكمية"]
    apply(base, {wire_key(base): 9_999})
    assert material(base, "سلك ألمنيوم")["الكمية"] == before


# ═════════ ٢. ما يتبع تعديل الكمية ═════════


def test_editing_a_material_moves_its_cost_and_the_totals(base):
    edited = apply(base, {wire_key(base): 3_000})
    row = material(edited, "سلك ألمنيوم")

    assert row["الكمية"] == 3_000
    assert row["الكمية_المحسوبة"] == material(base, "سلك ألمنيوم")["الكمية"]
    assert row["الكلفة"] == 3_000 * row["سعر الوحدة"]
    assert edited["كلفة_المواد"] > base["كلفة_المواد"]
    assert edited["الكلفة_الكلية"] == edited["كلفة_المواد"] + edited["كلفة_العمل"]


def test_editing_a_material_carries_its_labour_with_it(base):
    """**جوهر ق-٨١ داخل البرنامج:** أجر التسليك يتبع أمتار السلك.

    ولولا ذلك لصحّح المستخدم الكمية وبقي الأجر على حاله — وهي العلّة نفسها
    التي اشتكى منها في الإكسل.
    """
    edited = apply(base, {wire_key(base): 3_000})
    line = labour(edited, "تسليك")

    assert line.qty == 3_000
    assert line.manual is True
    assert line.computed_qty == labour(base, "تسليك").qty
    assert line.cost == 3_000 * line.rate


def test_an_explicit_labour_edit_beats_what_came_from_its_material(base):
    """من عدّل بنداً بعينه أراده بذاته، فلا يُطمَس بتعديلٍ انتقل إليه."""
    line = labour(base, "تسليك")
    edited = apply(base, {wire_key(base): 3_000},
                   {key_of(line.name, line.unit): 2_000})
    assert labour(edited, "تسليك").qty == 2_000
    assert material(edited, "سلك ألمنيوم")["الكمية"] == 3_000


def test_an_unlinked_labour_item_is_untouched_by_a_material_edit(base):
    """الحفر لا مادة تقوده، فلا يتحرّك بتعديل مادة (ق-٨١)."""
    before = labour(base, "حفر الخندق")
    after = labour(apply(base, {wire_key(base): 3_000}), "حفر الخندق")
    assert (after.qty, after.manual) == (before.qty, False)


def test_a_value_equal_to_the_computed_one_is_not_a_change(base):
    """كتابة الرقم المحسوب نفسه لا تُعدّ تعديلاً — فلا وسمٌ بلا سبب."""
    computed = material(base, "سلك ألمنيوم")["الكمية"]
    edited = apply(base, {wire_key(base): computed})
    assert summary(edited)["العدد"] == 0


def test_zero_is_a_real_edit_not_an_empty_one(base):
    """صفرٌ مكتوب تعديلٌ مقصود: «هذه المادة لا تُصرف»."""
    edited = apply(base, {wire_key(base): 0})
    assert material(edited, "سلك ألمنيوم")["الكمية"] == 0
    assert material(edited, "سلك ألمنيوم")["الكلفة"] == 0
    assert summary(edited)["العدد"] >= 1


# ═════════ ٣. الالتباس يُرفض ولا يُخمَّن ═════════


def test_two_labour_items_sharing_a_name_refuse_the_edit():
    """بندان باسم واحد وسعرين (ق-٢٤) — لا يُعرف أيّهما قُصد، فلا يُعدَّل رجماً."""
    result = compute(
        Network33kV(route_length_m=500, poles_suspension=4, circuit=CircuitType.SINGLE),
        Network33kV(route_length_m=500, poles_suspension=3, circuit=CircuitType.DOUBLE),
    )
    blocked = ambiguous_labour(result)
    assert blocked, "لم يتكرّر أي اسم — الاختبار لا يفحص شيئاً"

    key = next(iter(blocked))
    assert apply(result, {}, {key: 99})["أجور_العمل"] == result["أجور_العمل"]


# ═════════ ٤. الواجهة: الإذن، والتراجع، والأثر الظاهر ═════════


@pytest.fixture
def window(qapp, monkeypatch):
    monkeypatch.setattr(MainWindow, "_confirm", staticmethod(lambda *a: True))
    win = MainWindow(load_catalog())
    win.segments.load(Project("م", [
        Segment("أ", Network11kV(route_length_m=750, poles_lattice=9)),
    ]))
    return win


def _row_of(window, needle: str) -> int:
    return next(r for r, row in enumerate(window._rows) if needle in row["المادة"])


def test_editing_is_locked_until_it_is_explicitly_allowed(window):
    """الجدول يُقرأ أكثر ممّا يُكتب، فلا تتغيّر كمية بنقرة سهو."""
    row = _row_of(window, "سلك ألمنيوم")
    cell = window.materials.item(row, window.EDIT_COLUMN)
    assert not cell.flags() & Qt.ItemFlag.ItemIsEditable

    window.action_manual.setChecked(True)
    cell = window.materials.item(_row_of(window, "سلك ألمنيوم"), window.EDIT_COLUMN)
    assert cell.flags() & Qt.ItemFlag.ItemIsEditable


def test_refusing_the_permission_leaves_everything_locked(qapp, monkeypatch):
    monkeypatch.setattr(MainWindow, "_confirm", staticmethod(lambda *a: False))
    win = MainWindow(load_catalog())
    win.action_manual.setChecked(True)
    assert win.manual_mode is False
    assert win.action_manual.isChecked() is False


def test_typing_a_quantity_changes_the_totals_and_marks_the_row(window):
    before = window.result["الكلفة_الكلية"]
    window.action_manual.setChecked(True)
    row = _row_of(window, "سلك ألمنيوم")
    window.materials.item(row, window.EDIT_COLUMN).setText("3000")

    assert window.result["الكلفة_الكلية"] != before
    assert window.result["تعديلات_يدوية"]["العدد"] == 2      # المادة وأجرها
    assert window.manual_note.text()
    assert window.dirty is True


def test_clearing_the_cell_returns_the_computed_number(window):
    """التراجع الجزئي: إفراغ الخانة يعيد رقم المحرك لهذا السطر وحده."""
    before = window.result["الكلفة_الكلية"]
    window.action_manual.setChecked(True)
    row = _row_of(window, "سلك ألمنيوم")

    window.materials.item(row, window.EDIT_COLUMN).setText("3000")
    window.materials.item(_row_of(window, "سلك ألمنيوم"),
                          window.EDIT_COLUMN).setText("")

    assert window.material_overrides == {}
    assert window.result["الكلفة_الكلية"] == before


def test_clearing_them_all_returns_every_number(window):
    """**الحارس الذي طلبه المستخدم صراحةً:** العودة الكاملة إلى الحساب."""
    before = {row["المادة"]: row["الكمية"] for row in window.result["المواد"]}
    total = window.result["الكلفة_الكلية"]

    window.action_manual.setChecked(True)
    window.materials.item(_row_of(window, "سلك ألمنيوم"),
                          window.EDIT_COLUMN).setText("3000")
    window.materials.item(_row_of(window, "عمود 11م مشبك"),
                          window.EDIT_COLUMN).setText("12")

    window.clear_overrides()
    assert {row["المادة"]: row["الكمية"] for row in window.result["المواد"]} == before
    assert window.result["الكلفة_الكلية"] == total
    assert window.result.get("تعديلات_يدوية", {"العدد": 0})["العدد"] == 0


def test_closing_the_editing_mode_keeps_the_edits(window):
    """الإذن مفتاح تحرير لا مفتاح تشغيل — إغلاقه لا يمحو ما كُتب."""
    window.action_manual.setChecked(True)
    window.materials.item(_row_of(window, "سلك ألمنيوم"),
                          window.EDIT_COLUMN).setText("3000")
    window.action_manual.setChecked(False)

    assert window.manual_mode is False
    assert window.material_overrides            # التعديل باقٍ
    assert window.result["تعديلات_يدوية"]["العدد"] == 2


def test_a_nonsense_entry_is_refused_and_the_number_stands(window, monkeypatch):
    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(a[2])))
    window.action_manual.setChecked(True)
    window.materials.item(_row_of(window, "سلك ألمنيوم"),
                          window.EDIT_COLUMN).setText("عشرة")

    assert warned and window.material_overrides == {}


def test_a_negative_quantity_is_refused(window, monkeypatch):
    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(a[2])))
    window.action_manual.setChecked(True)
    window.materials.item(_row_of(window, "سلك ألمنيوم"),
                          window.EDIT_COLUMN).setText("-5")

    assert warned and window.material_overrides == {}


def test_the_computed_number_stays_on_screen_beside_the_manual_one(window):
    """الرقمان يُقرآن معاً — فلا يُظنّ اليدويُّ حساباً."""
    window.action_manual.setChecked(True)
    row = _row_of(window, "سلك ألمنيوم")
    computed = window._rows[row]["الكمية"]
    window.materials.item(row, window.EDIT_COLUMN).setText("3000")

    row = _row_of(window, "سلك ألمنيوم")
    assert window.materials.item(row, 2).text() == f"{computed:,.0f}"
    assert window.materials.item(row, window.EDIT_COLUMN).text() == "3,000"


def test_the_edits_survive_a_save_and_reopen(window, tmp_path):
    window.action_manual.setChecked(True)
    window.materials.item(_row_of(window, "سلك ألمنيوم"),
                          window.EDIT_COLUMN).setText("3000")
    total = window.result["الكلفة_الكلية"]
    path = window.save_to(tmp_path / "أمر")

    other = MainWindow(load_catalog())
    other.load_from(path)
    assert other.material_overrides == window.material_overrides
    assert other.result["الكلفة_الكلية"] == total


def test_a_reopened_order_can_still_be_reverted(window, tmp_path, monkeypatch):
    """**التراجع بعد شهور:** المحسوب يُعاد توليده من المُدخَلات لا من الملف."""
    computed_total = window.result["الكلفة_الكلية"]
    window.action_manual.setChecked(True)
    window.materials.item(_row_of(window, "سلك ألمنيوم"),
                          window.EDIT_COLUMN).setText("3000")
    path = window.save_to(tmp_path / "أمر")

    other = MainWindow(load_catalog())
    other.load_from(path)
    other.clear_overrides()
    assert other.result["الكلفة_الكلية"] == computed_total


def test_a_new_order_starts_with_no_edits(window, tmp_path):
    window.action_manual.setChecked(True)
    window.materials.item(_row_of(window, "سلك ألمنيوم"),
                          window.EDIT_COLUMN).setText("3000")
    window.new_order()
    assert window.material_overrides == {} and window.labour_overrides == {}


# ═════════ ٥. الأثر في الأوراق ═════════


def test_the_audit_sheet_names_what_was_edited(base):
    import printing
    from engine.workorder import WorkOrder

    edited = apply(base, {wire_key(base): 3_000})
    html = printing.get("audit").build_html(WorkOrder(number="1"), edited)

    assert "معدَّلة يدوياً" in html
    assert "سلك ألمنيوم 120/20 ملم²" in html
    assert "✎ يدوي" in html                      # ووسمٌ على سطر الأجر نفسه


def test_the_official_forms_carry_no_such_mark(base):
    """شكل النموذجين معتمَد، ولا يُزاد عليه بلا طلب (ق-٠)."""
    import printing
    from engine.workorder import WorkOrder

    edited = apply(base, {wire_key(base): 3_000})
    for key in ("iso", "amana"):
        html = printing.get(key).build_html(WorkOrder(number="1"), edited)
        assert "يدوي" not in html and "معدَّلة يدوياً" not in html, key


def test_the_edited_quantity_is_the_one_that_gets_printed(base):
    """الورقة تحمل الرقم المعدَّل — وإلا فما فائدة التعديل قبل التصدير."""
    import printing
    from engine.workorder import WorkOrder

    edited = apply(base, {wire_key(base): 3_000})
    html = printing.get("iso").build_html(WorkOrder(number="1"), edited)
    assert "3,000" in html


def _labour_row(window, needle: str) -> int:
    return next(r for r in range(window.labour.rowCount())
                if needle in window.labour.item(r, 0).text())


def test_a_labour_quantity_can_be_edited_on_its_own(window):
    """البند الذي لا مادة تقوده (الحفر مثلاً) لا يُصحَّح إلا من جدوله."""
    window.segments.load(Project("م", [
        Segment("أ", Underground11kV(route_length_m=300, feeder_count=2)),
    ]))
    window.action_manual.setChecked(True)

    row = _labour_row(window, "حفر الخندق")
    before = window.result["كلفة_العمل"]
    window.labour.item(row, window.LABOUR_EDIT_COLUMN).setText("450")

    line = next(l for l in window.result["أجور_العمل"] if "حفر الخندق" in l.name)
    assert line.qty == 450 and line.manual is True
    assert line.computed_qty == 300
    assert window.result["كلفة_العمل"] > before
    assert window.labour_overrides


def test_clearing_them_all_clears_the_labour_edits_too(window):
    """**وإلا بقي تعديل أجرٍ عالقاً بعد «إلغاء الكل»** — وهو أخفى ما يُنسى."""
    window.segments.load(Project("م", [
        Segment("أ", Underground11kV(route_length_m=300, feeder_count=2)),
    ]))
    total = window.result["الكلفة_الكلية"]
    window.action_manual.setChecked(True)
    window.labour.item(_labour_row(window, "حفر الخندق"),
                       window.LABOUR_EDIT_COLUMN).setText("450")

    window.clear_overrides()
    assert window.labour_overrides == {}
    assert window.result["الكلفة_الكلية"] == total
