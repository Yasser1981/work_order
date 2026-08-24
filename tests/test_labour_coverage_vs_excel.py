# -*- coding: utf-8 -*-
"""حارس التغطية لبنود الأجور — نظير `test_coverage_vs_excel.py` للمواد.

**لماذا وُجد:** حارس المواد كان يفحص جدول المواد الـ61 وحده، فلا شيء يحرس بنود
الأجور. وثغرتان وقعتا فعلاً بلا أن يمنعهما شيء: مجموعة المحولة (ق-٢٣، مواد) وبند
المقرنص المرمري (ق-٣٣، أجر) — كلتاهما اكتُشفت بمراجعة يدوية لا باختبار.

**القاعدة:** كل بند من بنود الأجور الـ29 في الملف الأصلي يجب أن يقع في **واحدة**
من أربع خانات، لا خامسة:

1. **يولّده المحرك** باسمه نفسه
2. **أُعيدت تسميته** — مذكور في `RENAMED` مع الاسم الجديد
3. **اندمج** مع بند آخر — مذكور في `MERGED` (بنود إكسل متعدّدة ← بند واحد عندنا)
4. **ملغى صراحةً** — مذكور في `CANCELLED` مع سببه

قائمة الـ29 لقطة مجمَّدة من `كلفة_العمل` في الملف الأصلي — لا تُعدَّل إلا بقرار
مسجَّل (ق-٠).
"""

from engine import load_catalog
from engine.equipment import TransformerSize
from engine.project import compute_project
from engine.types import (
    CircuitType,
    Equipment,
    LVNetworkType,
    Network11kV,
    Network33kV,
    NetworkLV,
    Project,
    Segment,
    SidewalkType,
    Underground11kV,
    Underground33kV,
)

EXCEL_LABOUR = [
    "نصب المحولة",
    "تسليك شبكة الضغط العالي",
    "نصب طاقم ستي",
    "نصب عمود مشبك 11م",
    "نصب عمود مدور 11م",
    "نصب عمود مشبك 9م",
    "نصب عمود مدور 9م",
    "نصب الفاصل الهوائي ON-LOAD",
    "تسليك شبكة الضغط الواطئ (أسلاك)",
    "تسليك شبكة الضغط الواطئ (قابلو معلق مبروم)",
    "ربط المستهلكين",
    "كلفة إعادة ورفع مقرنص مرمري",
    "كلفة الاعمال المدنية للشبكة الأرضية",
    "كلفة عبور الشوارع الفرعية",
    "كلفة عبور الشوارع الرئيسية – حفر مخفي",
    "نصب عمود مشبك تعليق 14م (مزدوج)",
    "نصب ركيزة وسطية (مزدوج)",
    "نصب ركيزة بداية ونهاية (مزدوج)",
    "نصب عمود مشبك تعليق 14م (مفرد)",
    "نصب ركيزة وسطية (مفرد)",
    "نصب ركيزة بداية ونهاية (مفرد)",
    "تسليك شبكة 33 ك.ف 210",
    "نصب فاصل هوائي 33 ك.ف",
    "كلفة مد قابلو 1×400 ملم²",
    "كلفة مد قابلو 3×150 ملم²",
    "كلفة نصب صندوق مستقيم 1×400 ملم²",
    "كلفة نصب صندوق نهاية 1×400 ملم²",
    "كلفة نصب صندوق مستقيم 3×150 ملم²",
    "كلفة نصب صندوق نهاية 3×150 ملم²",
]

RENAMED = {
    "نصب الفاصل الهوائي ON-LOAD": "نصب الفاصل ON-LOAD",
    "كلفة عبور الشوارع الفرعية": "عبور الشوارع الفرعية",
    "كلفة عبور الشوارع الرئيسية – حفر مخفي": "عبور الشوارع الرئيسية – حفر مخفي",
}

MERGED = {
    # الملف الأصلي يفصل بنداً لكل نوع دائرة لأن الصيغة لا تعرف السعر المتغيّر.
    # عندنا بند واحد وسعره يتبع نوع الدائرة (السعر_مفردة/السعر_مزدوجة) — والبندان
    # يبقيان منفصلين في المخرجات حين يختلف الأجر فعلاً (ق-٢٤: aggregate_labour).
    "نصب عمود مشبك تعليق 14م (مزدوج)": "نصب عمود مشبك تعليق 14م",
    "نصب عمود مشبك تعليق 14م (مفرد)": "نصب عمود مشبك تعليق 14م",
    "نصب ركيزة وسطية (مزدوج)": "نصب ركيزة شد وسطية عمود 14م",
    "نصب ركيزة وسطية (مفرد)": "نصب ركيزة شد وسطية عمود 14م",
    "نصب ركيزة بداية ونهاية (مزدوج)": "نصب ركيزة شد بداية ونهاية عمود 14م",
    "نصب ركيزة بداية ونهاية (مفرد)": "نصب ركيزة شد بداية ونهاية عمود 14م",
}

DYNAMIC_PREFIX = {
    # اسم البند عندنا يحمل نوع الرصيف وعدد المغذيات، فيتغيّر بتغيّرهما (ق-٣٠)
    "كلفة الاعمال المدنية للشبكة الأرضية": "الأعمال المدنية — ",
}

CANCELLED = {
    "كلفة إعادة ورفع مقرنص مرمري":
        "لا يُضاف — تعرفة الأعمال المدنية مبنية أصلاً على نوع الرصيف (ق-٣٣)",
}


def all_labour_the_engine_can_produce() -> set[str]:
    """كل بند أجر قد يولّده المحرك في أي تركيبة مدخلات.

    يمرّ عبر `compute_project` لا `labour_of` وحدها، لأن عبور الشوارع بند على
    مستوى المشروع لا داخل مقطع (ق-٣٠) — ولو فحصنا المقاطع وحدها لفاتنا.
    """
    catalog = load_catalog()
    segments = []

    for circuit in CircuitType:
        segments.append(Segment("", Network11kV(
            route_length_m=100, circuit=circuit,
            poles_lattice=1, poles_round=1, stay_rod_sets=1)))
        segments.append(Segment("", Network33kV(
            route_length_m=100, circuit=circuit, poles_suspension=1,
            anchors_mid=1, anchors_end=1, stay_rod_sets=1)))
        segments.append(Segment("", Underground33kV(
            route_length_m=100, circuit=circuit, straight_boxes=1,
            end_boxes_internal=1, end_boxes_external=1)))

    for kind in LVNetworkType:
        segments.append(Segment("", NetworkLV(
            route_length_m=100, kind=kind, poles_lattice=1,
            poles_round=1, consumers=1)))

    segments.append(Segment("", Equipment(
        transformers={s: 1 for s in TransformerSize},
        onload_11_mid=1, onload_11_head=1,
        isolator_33_mid=1, isolator_33_head=1, lattice_cages=1)))

    for sidewalk in SidewalkType:
        segments.append(Segment("", Underground11kV(
            route_length_m=100, feeder_count=1, sidewalk_type=sidewalk,
            straight_boxes=1, end_boxes_internal=1, end_boxes_external=1)))

    project = Project(
        segments=segments,
        street_crossing_secondary_m=10,
        street_crossing_main_m=10,
    )
    return {line.name for line in compute_project(project, catalog)["أجور_العمل"]}


def _is_covered(excel_name: str, produced: set[str]) -> bool:
    """هل البند مغطّى بأي من الخانات الأربع؟"""
    if excel_name in CANCELLED:
        return True
    if excel_name in produced:
        return True
    if RENAMED.get(excel_name) in produced:
        return True
    if MERGED.get(excel_name) in produced:
        return True
    prefix = DYNAMIC_PREFIX.get(excel_name)
    return bool(prefix) and any(name.startswith(prefix) for name in produced)


# ═══════════════════ الحارس نفسه ═══════════════════


def test_the_excel_snapshot_is_the_full_29_rows():
    assert len(EXCEL_LABOUR) == 29
    assert len(set(EXCEL_LABOUR)) == 29


def test_every_excel_labour_item_is_implemented_or_explicitly_set_aside():
    """الحارس الأساسي: لا بند أجر يسقط بصمت بين النطاق والمؤجَّل."""
    produced = all_labour_the_engine_can_produce()
    orphans = [name for name in EXCEL_LABOUR if not _is_covered(name, produced)]
    assert not orphans, (
        "بنود أجور سقطت — نفّذها أو أدرجها صراحةً في RENAMED/MERGED/CANCELLED:\n"
        + "\n".join(f"  {name}" for name in orphans)
    )


def test_cancelled_labour_items_are_really_not_produced():
    """العكس محروس أيضاً: بند ملغى لا يتسلّل إلى المخرجات."""
    produced = all_labour_the_engine_can_produce()
    leaked = [name for name in CANCELLED if name in produced]
    assert not leaked, f"بند أجر ملغى يولّده المحرك: {leaked}"


def test_renamed_and_merged_targets_actually_exist():
    """إعادة التسمية والدمج ليسا إخفاءً — الاسم الجديد مولَّد فعلاً."""
    produced = all_labour_the_engine_can_produce()
    for excel_name, our_name in {**RENAMED, **MERGED}.items():
        assert our_name in produced, (
            f"«{excel_name}» يشير إلى «{our_name}» وهو غير مولَّد إطلاقاً"
        )


def test_engine_extras_beyond_the_excel_sheet_are_known():
    """ما يولّده المحرك ولا نظير له في الملف الأصلي — كله مقصود ومسجَّل."""
    produced = all_labour_the_engine_can_produce()
    mapped = set(EXCEL_LABOUR) | set(RENAMED.values()) | set(MERGED.values())
    extras = {
        name for name in produced
        if name not in mapped
        and not name.startswith(DYNAMIC_PREFIX["كلفة الاعمال المدنية للشبكة الأرضية"])
    }
    assert extras == set(), f"بنود أجور جديدة غير مسجَّلة: {extras}"


# ═══════════════════ حارس الانهيار: كل بند له سعر في نسخة الأسعار ═══════════════════


def test_every_produced_labour_item_has_a_row_in_the_catalog():
    """حارس انهيار: بند أجر باسم غير موجود في نسخة الأسعار يُسقط الحساب بـ KeyError.

    الأعمال المدنية استثناء مقصود — اسمها ديناميكي وسعرها يأتي من جدول التعرفة
    لا من قسم «أجور_العمل».
    """
    rates = load_catalog()["أجور_العمل"]
    civil_prefix = DYNAMIC_PREFIX["كلفة الاعمال المدنية للشبكة الأرضية"]
    for name in sorted(all_labour_the_engine_can_produce()):
        if name.startswith(civil_prefix):
            continue
        assert name in rates, f"بند أجر بلا صف في نسخة الأسعار: {name}"


def test_no_orphan_rates_left_unused_in_the_catalog():
    """العكس: كل بند في نسخة الأسعار يستخدمه المحرك فعلاً — لا أسعار ميتة."""
    rates = set(load_catalog()["أجور_العمل"])
    produced = all_labour_the_engine_can_produce()
    unused = rates - produced
    assert unused == set(), f"أسعار أجور لا يستخدمها المحرك: {unused}"
