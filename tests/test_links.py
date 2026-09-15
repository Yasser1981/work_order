# -*- coding: utf-8 -*-
"""الرابط بين كمية المادة وكمية أجرها في ملفات الإكسل (ق-٨١).

**العلّة التي يعالجها:** تعديل كمية السلك في الورقة كان يُحدّث كلفة السلك ولا
يمسّ أجر التسليك — فتخرج ورقةٌ نصفها معدَّل ونصفها قديم، ومجموعها لا يصف شيئاً.
"""

import pytest

openpyxl = pytest.importorskip("openpyxl", reason="openpyxl غير مثبَّت")

from datetime import date  # noqa: E402

import printing  # noqa: E402
from engine import load_catalog  # noqa: E402
from engine.equipment import TRANSFORMER_KITS  # noqa: E402
from engine.links import material_drivers, unlinked_drivers  # noqa: E402
from engine.project import compute_project  # noqa: E402
from engine.types import (  # noqa: E402
    Equipment,
    LVNetworkType,
    Network11kV,
    Network33kV,
    NetworkLV,
    Project,
    Segment,
    SupplyForm,
    Underground11kV,
    Underground33kV,
)
from engine.workorder import WorkOrder  # noqa: E402
from printing.amana_sheet import SHEET  # noqa: E402
from printing.spreadsheet import LABOUR_SHEET, ORDER_SHEET  # noqa: E402


def compute(*segments, **project):
    return compute_project(
        Project("م", [Segment("", content) for content in segments], **project),
        load_catalog())


@pytest.fixture(scope="module")
def result():
    return compute(
        Network11kV(route_length_m=750, poles_lattice=9, poles_round=15,
                    stay_rod_sets=2),
        Underground11kV(route_length_m=300, feeder_count=2, straight_boxes=3,
                        end_boxes_internal=1, end_boxes_external=2),
        street_crossing_secondary_m=12, street_crossing_secondary_feeders=2)


@pytest.fixture
def order():
    return WorkOrder(number="148", order_date=date(2026, 9, 15), project_name="تجربة")


EVERY_KIND = (
    Network11kV(route_length_m=750, poles_lattice=9, poles_round=15, stay_rod_sets=2),
    Network11kV(route_length_m=500, poles_lattice=4,
                lattice_supply=SupplyForm.WITH_ACCESSORIES),
    Network33kV(route_length_m=500, poles_suspension=4, anchors_mid=1, anchors_end=2),
    NetworkLV(route_length_m=500, kind=LVNetworkType.BARE_WIRES, poles_lattice=5,
              poles_round=7, consumers=30),
    NetworkLV(route_length_m=400, kind=LVNetworkType.BUNDLED_CABLE, poles_lattice=3),
    Underground11kV(route_length_m=300, feeder_count=2, straight_boxes=3,
                    end_boxes_internal=1),
    Underground33kV(route_length_m=300, straight_boxes=2, end_boxes_internal=1),
    Equipment(transformers={k: 1 for k in list(TRANSFORMER_KITS)[:2]},
              onload_11_mid=2, isolator_33_mid=1),
)


# ═══════════ ١. الإعلان نفسه: لا اسم مادة مخطوء ═══════════


def test_every_declared_driver_names_a_material_that_really_exists():
    """**حارس الأخطاء المطبعية:** اسمٌ مخطوء في الإعلان لا يُربط أبداً — بصمت.

    فلا شيء يفشل، ولا شيء يتغيّر، وتبقى الكمية جامدة إلى الأبد بلا أن ينتبه
    أحد. وهذا الحارس يُسقط ذلك فوراً: كل مادة مُعلَنة يجب أن تكون **موجودة**
    في نتيجة مشروع يستعمل ذلك المقطع.
    """
    for content in EVERY_KIND:
        result = compute(content)
        names = {(m["المادة"], m["الوحدة"]) for m in result["المواد"]}
        for line in result["أجور_العمل"]:
            if line.driver:
                assert line.driver in names, (
                    f"«{line.name}» يعلن مادةً غير موجودة: {line.driver}")


def test_the_declared_drivers_mostly_link_in_a_real_project(result):
    """الإعلان ليس حبراً على ورق: أكثر البنود المعلنة تُربط فعلاً."""
    declared = [line for line in result["أجور_العمل"] if line.driver]
    assert len(material_drivers(result)) == len(declared) > 4


# ═══════════ ٢. ولا يُربط إلا عند التطابق ═══════════


def test_a_shared_material_between_two_labour_items_is_not_linked():
    """الفاصل ON-LOAD مادةٌ واحدة وبندا أجرٍ (منتصف ورأس قابلو) — فلا ربط.

    ولو رُبط لأصبح كلا البندين يقرأ **الكمية الكلية**، فيتضاعف الأجر بلا سبب.
    """
    result = compute(Equipment(onload_11_mid=1, onload_11_head=1))
    assert material_drivers(result) == {}
    reasons = dict(unlinked_drivers(result))
    assert len(reasons) == 2
    assert all("الكمية" in why for why in reasons.values())


def test_an_item_with_two_source_materials_declares_no_driver():
    """صندوق النهاية: داخلي وخارجي في بندِ أجرٍ واحد — فلا مادة واحدة تقوده."""
    result = compute(Underground11kV(route_length_m=300, feeder_count=1,
                                     end_boxes_internal=2, end_boxes_external=3))
    ends = [l for l in result["أجور_العمل"] if "صندوق نهاية" in l.name]
    assert ends and all(line.driver is None for line in ends)


def test_a_chance_match_in_numbers_never_creates_a_link():
    """**الحارس الذي يمنع الربط بالأرقام:** التطابق العددي وحده لا يكفي.

    في مشروع حقيقي كانت كمية «عبور الشوارع الفرعية» 24 وكمية «ترمنل 50 ملم²»
    24 كذلك — مصادفةً. فلو رُبط بالأرقام لغيّر تعديلُ الترمنلات أجرَ العبور.
    """
    result = compute(Network11kV(route_length_m=750, poles_lattice=9, poles_round=15),
                     street_crossing_secondary_m=12, street_crossing_secondary_feeders=2)
    crossing = next(l for l in result["أجور_العمل"] if "عبور" in l.name)
    terminal = next(m for m in result["المواد"] if m["المادة"].startswith("ترمنل"))
    assert crossing.qty == terminal["الكمية"]          # المصادفة قائمة فعلاً
    assert crossing.driver is None                     # ولا ربط


# ═══════════ ٣. ملفّا الإكسل: المعادلة تشير إلى الصفّ الصحيح ═══════════


def _linked(sheet, column: int = 4):
    """الصفوف التي كميتها معادلة، مع نصّها."""
    return {row: sheet.cell(row, column).value
            for row in range(1, sheet.max_row + 1)
            if isinstance(sheet.cell(row, column).value, str)
            and sheet.cell(row, column).value.startswith("=")}


def test_the_iso_labour_quantity_points_at_its_material_row(order, result, tmp_path):
    """**الحارس الأهمّ:** الخلية التي تسمّيها المعادلة هي فعلاً صفّ تلك المادة.

    وخطأ إزاحة واحد يجعل أجر التسليك يقرأ كمية العواميد — رقمٌ معقول المظهر
    وخاطئ تماماً، ولا شيء في الورقة يدلّ عليه.
    """
    path = printing.get("iso").write_xlsx(order, result, str(tmp_path / "إيزو"))
    book = openpyxl.load_workbook(path)
    order_sheet, labour = book[ORDER_SHEET], book[LABOUR_SHEET]

    formulas = _linked(labour)
    assert formulas, "لا كمية مربوطة إطلاقاً"

    lines = result["أجور_العمل"]
    for row, formula in formulas.items():
        assert formula.startswith(f"='{ORDER_SHEET}'!D")
        target = int(formula.rsplit("D", 1)[1])
        line = lines[row - 2]
        assert order_sheet.cell(target, 2).value == line.driver[0]
        assert order_sheet.cell(target, 4).value == line.qty     # لا يتغيّر رقم


def test_the_amana_labour_quantity_points_at_its_material_row(order, result, tmp_path):
    """نظير حارس الإيزو — والورقة هنا واحدة، فالمرجع داخلها."""
    from printing.amana_form import printed_labour_name

    path = printing.get("amana").write_xlsx(order, result, str(tmp_path / "أمانة"))
    sheet = openpyxl.load_workbook(path)[SHEET]

    expected = {printed_labour_name(line.name): line
                for line in result["أجور_العمل"] if line.driver}
    formulas = _linked(sheet)
    assert formulas

    for row, formula in formulas.items():
        line = expected[sheet.cell(row, 2).value]
        target = int(formula.lstrip("=D"))
        assert sheet.cell(target, 2).value == line.driver[0]
        assert sheet.cell(target, 4).value == line.qty


def test_the_unlinked_quantities_stay_plain_numbers(order, tmp_path):
    """ما لا يصحّ ربطه يبقى رقماً — ولا يُفرض عليه مرجعٌ يغيّره."""
    result = compute(Equipment(onload_11_mid=1, onload_11_head=1))
    path = printing.get("iso").write_xlsx(order, result, str(tmp_path / "إيزو"))
    labour = openpyxl.load_workbook(path)[LABOUR_SHEET]
    assert _linked(labour) == {}


def test_the_numbers_themselves_did_not_change(order, result, tmp_path):
    """**شرط المستخدم:** «الحسابات والنتائج الرئيسية لا تُمسّ».

    فكل كمية مربوطة تشير إلى خلية تحمل **الرقم نفسه** الذي كان يُكتب جامداً.
    """
    path = printing.get("iso").write_xlsx(order, result, str(tmp_path / "إيزو"))
    book = openpyxl.load_workbook(path)
    order_sheet, labour = book[ORDER_SHEET], book[LABOUR_SHEET]

    for index, line in enumerate(result["أجور_العمل"]):
        value = labour.cell(index + 2, 4).value
        if isinstance(value, str):
            value = order_sheet.cell(int(value.rsplit("D", 1)[1]), 4).value
        assert value == line.qty
