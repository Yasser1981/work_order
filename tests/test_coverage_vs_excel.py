# -*- coding: utf-8 -*-
"""حارس التغطية: لا مادة من الملف الأصلي تسقط بصمت.

سقطت 19 مادة بين «داخل النطاق» و«المؤجَّل» في ق-١٢ فلم تُنفَّذ ولم تُؤجَّل — منها
المحولة بـ17 مليون دينار. هذا الاختبار يمنع تكرار ذلك: كل مادة من جدول المواد
الـ61 في الملف الأصلي إمّا **يولّدها المحرك**، وإمّا **مذكورة صراحةً** في قائمة
المؤجَّل أو الملغى أدناه. لا خانة ثالثة.

قائمة الـ61 لقطة مجمَّدة من الملف الأصلي — لا تُعدَّل إلا بقرار مسجَّل (ق-٠).
"""

from engine.equipment import materials_equipment
from engine.lowvoltage import materials_lv
from engine.overhead import materials_11kv, materials_33kv
from engine.types import (
    CircuitType,
    Equipment,
    LVNetworkType,
    Network11kV,
    Network33kV,
    NetworkLV,
)

EXCEL_MATERIALS = [
    ("سلك ألمنيوم 120/20 ملم²", "متر"),
    ("سلك ألمنيوم 95 ملم²", "متر"),
    ("قابلو ألمنيوم معلق 3×120+95+16 ملم²", "متر"),
    ("محولة 400 KVA", "عدد"),
    ("قاطع دورة 400 أمبير مع المتسعة", "عدد"),
    ("قاعدة محولة 2.4 متر", "سيت"),
    ("لنك فيوز 15 KV مع سلك فيوز 40 أمبير", "سيت"),
    ("قاعدة لنك فيوز 2.4 متر", "عدد"),
    ("قضيب تأريض 1.5 متر مع القفيص", "عدد"),
    ("سلك نحاس 50 ملم2", "متر"),
    ("قابلو نحاس 1×50 ملم²", "متر"),
    ("قابلو نحاس 1×150 ملم²", "متر"),
    ("مانعة صواعق 11 KV", "سيت"),
    ("قاعدة مانعة صواعق مع الملحقات", "عدد"),
    ("معدات ربط ألمنيوم – نحاس", "عدد"),
    ("ترمنل 50 ملم²", "عدد"),
    ("ترمنل 150 ملم²", "عدد"),
    ("جهاز إنارة", "عدد"),
    ("عمود 11م مشبك", "عدد"),
    ("عازل دبوسي مع السبندل", "عدد"),
    ("عازل قرصي مع الملحقات", "سيت"),
    ("معدات ربط ألمنيوم – ألمنيوم", "عدد"),
    ("عمود 11م مدوّر", "عدد"),
    ("عمود 9م مشبك", "عدد"),
    ("بوكس كلامب (أسلاك)", "عدد"),
    ("هوك تعليق (قابلو)", "عدد"),
    ("كلامب شد (قابلو)", "عدد"),
    ("عمود 9م مدوّر", "عدد"),
    ("كلامب تعليق (قابلو)", "عدد"),
    ("فاصل ON-LOAD", "عدد"),
    ("براكيت 2.1 متر", "عدد"),
    ("كونكريت أساسات الأعمدة", "متر مكعب"),
    ("واير ستي", "متر"),
    ("كونكتر قابلو معلق (ألمنيوم – ألمنيوم)", "عدد"),
    ("قفيص عمود مشبك", "عدد"),
    ("طقم ستي رود", "سيت"),
    ("قابلو 3×150 ملم2 جهد 11 ك.ف", "متر"),
    ("صندوق مستقيم 3×150 ملم2 جهد 11 ك.ف", "عدد"),
    ("صندوق نهاية داخلي 3×150 ملم2 جهد 11 ك.ف", "عدد"),
    ("صندوق نهاية خارجي 3×150 ملم2 جهد 11 ك.ف", "عدد"),
    ("براكيت 1.2 م مع الملحقات", "عدد"),
    ("براكيت 1.4 م مع الملحقات", "عدد"),
    ("أنبوب 8 انج 10 بار", "روطة"),
    ("شتايكر 50×50×5 سم", "عدد"),
    ("رمل نهري", "متر مكعب"),
    ("شريط تحذير", "لفة"),
    ("سلك ألمنيوم 210/35 ملم²", "متر"),
    ("عمود مشبك 14م", "عدد"),
    ("براكيت 2 متر", "عدد"),
    ("براكيت 2.5 متر", "عدد"),
    ("عازل قرصي 33 ك.ف مع الملحقات", "سيت"),
    ("عازل دبوسي 33 ك.ف مع السبندل", "عدد"),
    ("فاصل هوائي 33 ك.ف", "عدد"),
    ("مانعة صواعق 33 ك.ف", "سيت"),
    ("قابلو 1×185 ملم2", "متر"),
    ("ترمنل 185 ملم2", "عدد"),
    ("معدات المنيوم - المنيوم 210 ملم2", "عدد"),
    ("قابلو 1×400 ملم2 جهد 33 ك.ف", "متر"),
    ("صندوق مستقيم 1×400 ملم2 جهد 33 ك.ف", "عدد"),
    ("صندوق نهاية داخلي 1×400 ملم2 جهد 33 ك.ف", "سيت"),
    ("صندوق نهاية خارجي 1×400 ملم2 جهد 33 ك.ف", "سيت"),
]

CANCELLED = {
    ("براكيت 2.1 متر", "عدد"): "ملغى تماماً — الفاصل ON-LOAD لا يحتاجه (ق-١٩)",
}

DEFERRED = {
    ("قابلو 3×150 ملم2 جهد 11 ك.ف", "متر"): "الشبكة الأرضية (ق-١٢)",
    ("صندوق مستقيم 3×150 ملم2 جهد 11 ك.ف", "عدد"): "الشبكة الأرضية (ق-١٢)",
    ("صندوق نهاية داخلي 3×150 ملم2 جهد 11 ك.ف", "عدد"): "الشبكة الأرضية (ق-١٢)",
    ("صندوق نهاية خارجي 3×150 ملم2 جهد 11 ك.ف", "عدد"): "الشبكة الأرضية (ق-١٢)",
    ("قابلو 1×400 ملم2 جهد 33 ك.ف", "متر"): "الشبكة الأرضية (ق-١٢)",
    ("صندوق مستقيم 1×400 ملم2 جهد 33 ك.ف", "عدد"): "الشبكة الأرضية (ق-١٢)",
    ("صندوق نهاية داخلي 1×400 ملم2 جهد 33 ك.ف", "سيت"): "الشبكة الأرضية (ق-١٢)",
    ("صندوق نهاية خارجي 1×400 ملم2 جهد 33 ك.ف", "سيت"): "الشبكة الأرضية (ق-١٢)",
    ("أنبوب 8 انج 10 بار", "روطة"): "عبور الشوارع (ق-١٢)",
    ("شتايكر 50×50×5 سم", "عدد"): "مواد الخندق (ق-١٢)",
    ("رمل نهري", "متر مكعب"): "مواد الخندق (ق-١٢)",
    ("شريط تحذير", "لفة"): "مواد الخندق (ق-١٢)",
}


def all_materials_the_engine_can_produce() -> set[tuple[str, str]]:
    """كل مادة قد يولّدها المحرك في أي تركيبة مدخلات."""
    produced: set[tuple[str, str]] = set()

    n11 = Network11kV(
        route_length_m=100, poles_lattice=1, poles_round=1,
        stay_rod_sets=1, extra_bracket_12=1, extra_bracket_14=1,
    )
    n33 = Network33kV(
        route_length_m=100, poles_suspension=1, anchors_mid=1, anchors_end=1,
        stay_rod_sets=1, extra_bracket_2=1, extra_bracket_25=1,
    )
    for circuit in CircuitType:
        n11.circuit = n33.circuit = circuit
        for line in materials_11kv(n11) + materials_33kv(n33):
            produced.add((line.name, line.unit))

    for kind in LVNetworkType:
        lv = NetworkLV(
            route_length_m=100, kind=kind, poles_lattice=1, poles_round=1,
            consumers=1, on_hv_poles=True, hv_kind=kind,
            hv_poles_lattice=1, hv_poles_round=1,
        )
        for line in materials_lv(lv):
            produced.add((line.name, line.unit))

    equipment = Equipment(
        transformers=1, onload_11_mid=1, onload_11_head=1,
        isolator_33_mid=1, isolator_33_head=1, lattice_cages=1,
    )
    for line in materials_equipment(equipment):
        produced.add((line.name, line.unit))

    return produced


def test_the_excel_snapshot_is_the_full_61_rows():
    assert len(EXCEL_MATERIALS) == 61
    assert len(set(EXCEL_MATERIALS)) == 61


def test_every_excel_material_is_implemented_or_explicitly_set_aside():
    produced = all_materials_the_engine_can_produce()
    orphans = [
        m for m in EXCEL_MATERIALS
        if m not in produced and m not in DEFERRED and m not in CANCELLED
    ]
    assert not orphans, (
        "مواد سقطت بين النطاق والمؤجَّل — نفّذها أو أدرجها صراحةً في DEFERRED:\n"
        + "\n".join(f"  {n} ({u})" for n, u in orphans)
    )


def test_deferred_materials_are_really_not_produced():
    """العكس أيضاً محروس: مادة مؤجَّلة لا تتسلّل إلى المخرجات."""
    produced = all_materials_the_engine_can_produce()
    leaked = [m for m in list(DEFERRED) + list(CANCELLED) if m in produced]
    assert not leaked, f"مادة مؤجَّلة أو ملغاة يولّدها المحرك: {leaked}"


def test_engine_extras_beyond_the_excel_table_are_known():
    """ما يولّده المحرك ولا صف له في الملف الأصلي — كلاهما مقصود ومسجَّل."""
    produced = all_materials_the_engine_can_produce()
    extras = produced - set(EXCEL_MATERIALS)
    assert extras == {
        # RAW يحسبه في الملف الأصلي لكن بلا صف في جدول المواد — خلل مسجَّل
        ("شيش تسليح", "طن"),
        # مادة جديدة أضافها المستخدم (ق-٢٢)
        ("كونكتر ربط مشتركين", "عدد"),
    }


def test_every_produced_material_is_priced_or_flagged():
    """حارس مالي: لا مادة بلا صف في نسخة الأسعار."""
    from engine import load_catalog

    prices = load_catalog()["المواد"]
    for name, unit in sorted(all_materials_the_engine_can_produce()):
        assert name in prices, f"مادة بلا صف في نسخة الأسعار: {name}"
        assert prices[name]["الوحدة"] == unit, (
            f"وحدة مختلفة بين المحرك ونسخة الأسعار: {name}"
        )
