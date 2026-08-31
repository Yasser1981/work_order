# -*- coding: utf-8 -*-
"""حارس التغطية: لا مادة من الملف الأصلي تسقط بصمت.

سقطت 19 مادة بين «داخل النطاق» و«المؤجَّل» في ق-١٢ فلم تُنفَّذ ولم تُؤجَّل — منها
المحولة بـ17 مليون دينار. هذا الاختبار يمنع تكرار ذلك: كل مادة من جدول المواد
الـ61 في الملف الأصلي إمّا **يولّدها المحرك**، وإمّا **مذكورة صراحةً** في قائمة
المؤجَّل أو الملغى أدناه. لا خانة ثالثة.

قائمة الـ61 لقطة مجمَّدة من الملف الأصلي — لا تُعدَّل إلا بقرار مسجَّل (ق-٠).
"""

from engine.equipment import TRANSFORMER_KITS, materials_equipment
from engine.lowvoltage import materials_lv
from engine.overhead import materials_11kv, materials_33kv
from engine.types import (
    CircuitType,
    Equipment,
    LVNetworkType,
    Network11kV,
    Network33kV,
    SupplyForm,
    NetworkLV,
    SidewalkType,
    Underground11kV,
    Underground33kV,
)
from engine.underground import (
    materials_underground11,
    materials_underground33,
    street_crossing_pipes,
)

EXCEL_MATERIALS = [
    ("سلك ألمنيوم 120/20 ملم²", "متر"),
    ("سلك ألمنيوم 95 ملم²", "متر"),
    ("قابلو ألمنيوم معلق 3×120+95+16 ملم²", "متر"),
    ("محولة 400 KVA جهد 11/0.4 ك.ف", "عدد"),
    ("قاطع دورة 400 أمبير مع المتسعة", "عدد"),
    ("قاعدة محولة مع الملحقات", "سيت"),
    ("فاصل فيوز 11 ك.ف مع السلك", "سيت"),
    ("قاعدة لنك فيوز مع الملحقات", "عدد"),
    ("قضيب تأريض 1.5 متر مع القفيص", "عدد"),
    ("سلك نحاس 50 ملم²", "متر"),
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
    ("بكرة عازلة ض.و مع الملحقات", "عدد"),
    ("هوك تعليق", "عدد"),
    ("كلامب شد", "عدد"),
    ("عمود 9م مدوّر", "عدد"),
    ("كلامب تعليق", "عدد"),
    ("فاصل هوائي 11 ك.ف ON LOAD", "عدد"),
    ("براكيت 2.1 متر", "عدد"),
    ("كونكريت أساسات الأعمدة", "متر مكعب"),
    ("واير ستي", "متر"),
    ("كونكتر قابلو معلق (ألمنيوم – ألمنيوم)", "عدد"),
    ("قفيص عمود مشبك", "عدد"),
    ("طقم ستي رود", "سيت"),
    ("قابلو 3×150 ملم² جهد 11 ك.ف", "متر"),
    ("صندوق مستقيم 3×150 ملم² جهد 11 ك.ف", "عدد"),
    ("صندوق نهاية داخلي 3×150 ملم² جهد 11 ك.ف", "عدد"),
    ("صندوق نهاية خارجي 3×150 ملم² جهد 11 ك.ف", "عدد"),
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
    ("فاصل هوائي 33 ك.ف ON LOAD", "عدد"),
    ("مانعة صواعق 33 ك.ف", "سيت"),
    ("قابلو 1×185 ملم²", "متر"),
    ("ترمنل 185 ملم²", "عدد"),
    ("معدات ربط المنيوم - المنيوم 210 ملم²", "عدد"),
    ("قابلو 1×400 ملم² جهد 33 ك.ف", "متر"),
    ("صندوق مستقيم 1×400 ملم² جهد 33 ك.ف", "عدد"),
    ("صندوق نهاية داخلي 1×400 ملم² جهد 33 ك.ف", "سيت"),
    ("صندوق نهاية خارجي 1×400 ملم² جهد 33 ك.ف", "سيت"),
]

CANCELLED = {
    ("جهاز إنارة", "عدد"): "ملغى تماماً بطلبك — كان بكمية 2 وسعر صفر (ق-٢٦)",
}

RENAMED = {
    # اسم الملف الأصلي ← الاسم المعتمد عندنا. المادة نفسها لا مادة جديدة (ق-٢٩).
    ("براكيت 2.1 متر", "عدد"): ("قاعدة فاصل هوائي – براكيت جنل 2.1م", "عدد"),
    # توحيد إملاء «ألمنيوم» بألف الهمزة وبالشَرطة الطويلة كنظيرتها بطلبك (ق-٣٧)
    ("معدات ربط المنيوم - المنيوم 210 ملم²", "عدد"):
        ("معدات ربط ألمنيوم – ألمنيوم 210 ملم²", "عدد"),
    # «براكيت» ← «براكيت جنل» بمختلف الأطوال بطلبك (ق-٤١). المادة نفسها والسعر
    # نفسه — التسمية وحدها هي التي اكتملت
    ("براكيت 1.2 م مع الملحقات", "عدد"): ("براكيت جنل 1.2 م مع الملحقات", "عدد"),
    ("براكيت 1.4 م مع الملحقات", "عدد"): ("براكيت جنل 1.4 م مع الملحقات", "عدد"),
    ("براكيت 2 متر", "عدد"): ("براكيت جنل 2 متر", "عدد"),
    ("براكيت 2.5 متر", "عدد"): ("براكيت جنل 2.5 متر", "عدد"),
    # أُضيفت كلمة «نحاس» بطلبك (ق-٥٦)
    ("قضيب تأريض 1.5 متر مع القفيص", "عدد"):
        ("قضيب نحاس تأريض 1.5 متر مع القفيص", "عدد"),
    # «فاصل فيوز» ← «لنك فيوز» بطلبك: المصطلح الأدقّ، ويطابق «قاعدة لنك فيوز
    # مع الملحقات» التي كانت تحمله أصلاً (ق-٤٣)
    ("فاصل فيوز 11 ك.ف مع السلك", "سيت"): ("لنك فيوز 11 ك.ف مع السلك", "سيت"),
    # الوحدة تغيّرت من «سيت» إلى «عدد»: المادة نفسها والسعر نفسه (سعر المفرد)،
    # لكن الكمية صارت تُضرب ×3 لأن السيت ثلاثة صناديق طوراً لكل صندوق (ق-٣٥)
    ("صندوق نهاية داخلي 1×400 ملم² جهد 33 ك.ف", "سيت"):
        ("صندوق نهاية داخلي 1×400 ملم² جهد 33 ك.ف", "عدد"),
    ("صندوق نهاية خارجي 1×400 ملم² جهد 33 ك.ف", "سيت"):
        ("صندوق نهاية خارجي 1×400 ملم² جهد 33 ك.ف", "عدد"),
}

DEFERRED: dict[tuple[str, str], str] = {
    # لم يبقَ مؤجَّل: «أنبوب 8 انج 10 بار» كان آخرها، ورُبط بالمحرك في ق-٤٥
    # (عدد الأنابيب = ⌈طول الشارع ÷ 6⌉).
}


def all_materials_the_engine_can_produce() -> set[tuple[str, str]]:
    """كل مادة قد يولّدها المحرك في أي تركيبة مدخلات."""
    from engine import load_catalog

    catalog = load_catalog()
    produced: set[tuple[str, str]] = set()

    n11 = Network11kV(
        route_length_m=100, poles_lattice=1, poles_round=1,
        stay_rod_sets=1, extra_bracket_12=1, extra_bracket_14=1,
    )
    n33 = Network33kV(
        route_length_m=100, poles_suspension=1, anchors_mid=1, anchors_end=1,
        stay_rod_sets=1, extra_bracket_2=1, extra_bracket_25=1,
    )
    # شكل التوريد يغيّر **اسم المادة** بعد ق-٥٦، فلا بدّ من المرور بالشكلين
    for circuit in CircuitType:
        n11.circuit = n33.circuit = circuit
        for supply in SupplyForm:
            n11.lattice_supply = n11.round_supply = supply
            for line in materials_11kv(n11):
                produced.add((line.name, line.unit))
        for line in materials_33kv(n33):
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
        transformers={k: 1 for k in TRANSFORMER_KITS},
        onload_11_mid=1, onload_11_head=1,
        isolator_33_mid=1, isolator_33_head=1, lattice_cages=1,
    )
    for line in materials_equipment(equipment):
        produced.add((line.name, line.unit))

    for sidewalk in SidewalkType:
        ug11 = Underground11kV(
            route_length_m=100, feeder_count=1, sidewalk_type=sidewalk,
            straight_boxes=1, end_boxes_internal=1, end_boxes_external=1,
        )
        for line in materials_underground11(ug11, catalog):
            produced.add((line.name, line.unit))

    for circuit in CircuitType:
        ug33 = Underground33kV(
            route_length_m=100, circuit=circuit,
            straight_boxes=1, end_boxes_internal=1, end_boxes_external=1,
        )
        for line in materials_underground33(ug33, catalog):
            produced.add((line.name, line.unit))

    # عبور الشوارع بند على مستوى المشروع لا داخل مقطع (ق-٣٠)، وأنبوبه مادة
    # لا يولّدها أي مقطع — فلولا هذا السطر لفات الحارسَ (ق-٤٥)
    for line in street_crossing_pipes(30, 1, "عبور الشوارع الفرعية"):
        produced.add((line.name, line.unit))

    return produced


def test_renamed_materials_map_onto_something_the_engine_produces():
    """إعادة التسمية ليست إخفاءً: الاسم الجديد موجود فعلاً، والقديم لم يعد."""
    produced = all_materials_the_engine_can_produce()
    for excel_name, our_name in RENAMED.items():
        assert our_name in produced, f"الاسم الجديد غير مولَّد: {our_name}"
        assert excel_name not in produced, f"الاسم القديم ما زال يُولَّد: {excel_name}"


def test_the_excel_snapshot_is_the_full_61_rows():
    assert len(EXCEL_MATERIALS) == 61
    assert len(set(EXCEL_MATERIALS)) == 61


def test_every_excel_material_is_implemented_or_explicitly_set_aside():
    produced = all_materials_the_engine_can_produce()
    orphans = [
        m for m in EXCEL_MATERIALS
        if RENAMED.get(m, m) not in produced
        and m not in DEFERRED
        and m not in CANCELLED
    ]
    assert not orphans, (
        "مواد سقطت بين النطاق والمؤجَّل — نفّذها أو أدرجها صراحةً في DEFERRED:\n"
        + "\n".join(f"  {n} ({u})" for n, u in orphans)
    )


def test_deferred_materials_are_really_not_produced():
    """العكس أيضاً محروس: مادة مؤجَّلة لا تتسلّل إلى المخرجات."""
    produced = all_materials_the_engine_can_produce()
    leaked = [
        m for m in list(DEFERRED) + list(CANCELLED)
        if RENAMED.get(m, m) in produced
    ]
    assert not leaked, f"مادة مؤجَّلة أو ملغاة يولّدها المحرك: {leaked}"


def test_engine_extras_beyond_the_excel_table_are_known():
    """ما يولّده المحرك ولا صف له في الملف الأصلي — كلاهما مقصود ومسجَّل."""
    produced = all_materials_the_engine_can_produce()
    extras = produced - set(EXCEL_MATERIALS) - set(RENAMED.values())
    assert extras == {
        # RAW يحسبه في الملف الأصلي لكن بلا صف في جدول المواد — خلل مسجَّل
        ("شيش تسليح", "طن"),
        # مادة جديدة أضافها المستخدم (ق-٢٢)
        ("كونكتر ربط مشتركين", "عدد"),
        # سعتان جديدتان لا يعرفهما الملف الأصلي (ق-٢٦)
        ("محولة 250 KVA جهد 11/0.4 ك.ف", "عدد"),
        ("قاطع دورة 250 أمبير مع المتسعة", "عدد"),
        ("محولة 630 KVA جهد 11/0.4 ك.ف", "عدد"),
        # جهد تحويلي 33/0.4 ك.ف لا يعرفه الملف الأصلي إطلاقاً (ق-٣٧)،
        # والسعات الثلاث كلها متاحة به (ق-٣٨)
        ("محولة 250 KVA جهد 33/0.4 ك.ف", "عدد"),
        ("محولة 400 KVA جهد 33/0.4 ك.ف", "عدد"),
        ("محولة 630 KVA جهد 33/0.4 ك.ف", "عدد"),
        ("لنك فيوز 33 ك.ف مع السلك", "سيت"),
        # الملف الأصلي أغفل معدات ربط الفاصل الهوائي 33 ك.ف كلياً (ق-٢٦ و ق-٣٧)
        ("معدات ربط ألمنيوم – نحاس 210 ملم²", "عدد"),
        # العمود مورَّداً بملحقاته مادة أخرى باسم آخر (ق-٥٦)
        ("عمود 11م مشبك مع الملحقات", "عدد"),
        ("عمود 11م مدوّر مع الملحقات", "عدد"),
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
