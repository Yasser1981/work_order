# -*- coding: utf-8 -*-
"""اختبارات التجهيزات على الأعمدة — المحولة والفواصل والقفيص (ق-٢٣).

الأرقام المرجعية مأخوذة من `RAW_تفصيلي` في الملف الأصلي:
المحولة الصفوف 5–19، الفاصل هوائي 11 ك.ف ON LOAD 43–47، وعلى رأس القابلو 48–57،
والفاصل الهوائي 33 ك.ف 85–92.
"""

import pytest

from engine import load_catalog
from engine.equipment import (
    CABLE_HEAD_M,
    CABLE_MID_NETWORK_M,
    ISOLATOR_KITS,
    TRANSFORMER_KITS,
    IsolatorPosition,
    IsolatorVoltage,
    TransformerSize,
    TransformerVoltage,
    transformer_kit,
    isolator_kit,
    labour_equipment,
    materials_equipment,
)
from engine.overhead import aggregate, compute
from engine.types import Equipment, OverheadProject


@pytest.fixture
def catalog():
    return load_catalog()


def qty(lines, name):
    return sum(l.qty for l in lines if l.name == name)


# ═══════════════════ المحولة ═══════════════════

KVA400 = TransformerSize.KVA400
KV11 = TransformerVoltage.KV11
KV33 = TransformerVoltage.KV33


def test_transformer_kit_matches_the_original_file():
    """14 مادة — الملف الأصلي 15، وجهاز الإنارة ملغى منها (ق-٢٦)."""
    lines = materials_equipment(Equipment(transformers={(KV11, KVA400): 1}))
    expected = {
        "محولة 400 KVA جهد 11/0.4 ك.ف": 1,
        "قاطع دورة 400 أمبير مع المتسعة": 2,
        "قاعدة محولة مع الملحقات": 1,
        "لنك فيوز 11 ك.ف مع السلك": 1,
        "قاعدة لنك فيوز مع الملحقات": 1,
        "قضيب نحاس تأريض 1.5 متر مع القفيص": 3,
        "سلك نحاس 50 ملم²": 15,
        "قابلو نحاس 1×50 ملم²": 25,
        "قابلو نحاس 1×150 ملم²": 80,
        "مانعة صواعق 11 KV": 1,
        "قاعدة مانعة صواعق مع الملحقات": 1,
        "معدات ربط ألمنيوم – نحاس": 13,    # ثابتة لكل محولة (ق-٥٦)
        "ترمنل 50 ملم²": 15,                # ثابت لا يتبع المخارج (ق-٤٣، ق-٥٦)
        "ترمنل 150 ملم²": 24,               # 12 لكل مخرج × مخرجين (ق-٤٣)
    }
    assert {l.name: l.qty for l in lines} == expected


def test_the_lighting_unit_is_gone_from_every_kit_and_from_the_prices():
    """جهاز الإنارة ملغى تماماً — لا مادةً ولا صفّاً في نسخة الأسعار (ق-٢٦)."""
    from engine import load_catalog

    for size in TransformerSize:
        assert not any("إنارة" in n for (n, _u), _q in transformer_kit(size))
    assert "جهاز إنارة" not in load_catalog()["المواد"]


EXPECTED_OUTPUTS = {
    TransformerSize.KVA250: (2, 250),
    TransformerSize.KVA400: (2, 400),
    TransformerSize.KVA630: (4, 400),   # استثناء: أربعة مخارج بقاطع 400 لا 630
}


def test_the_breaker_follows_the_number_of_outputs_not_the_rating():
    """250 و400 مخرجان بسعتهما، و630 أربعة مخارج بقاطع 400 أمبير (ق-٢٧)."""
    for size, (outputs, amps) in EXPECTED_OUTPUTS.items():
        kit = dict(transformer_kit(size))
        assert kit[(f"محولة {size.value} KVA جهد 11/0.4 ك.ف", "عدد")] == 1
        assert kit[(f"قاطع دورة {amps} أمبير مع المتسعة", "عدد")] == outputs
        assert sum(1 for (n, _u) in kit if "قاطع" in n) == 1   # ولا قاطع رئيسي


def test_no_630_amp_breaker_exists_anywhere(catalog):
    """المحولة 630 KVA جهد 11/0.4 ك.ف لا تستخدم قاطع 630 أمبير — فلا وجود له مادةً ولا سعراً."""
    for size in TransformerSize:
        assert not any("630 أمبير" in n for (n, _u), _q in transformer_kit(size))
    assert "قاطع دورة 630 أمبير مع المتسعة" not in catalog["المواد"]


def test_the_lv_cable_length_follows_the_number_of_outputs():
    """40 م لكل مخرج: مخرجان ← 80 م، وأربعة ← 160 م (ق-٢٧)."""
    for size, (outputs, _amps) in EXPECTED_OUTPUTS.items():
        kit = dict(transformer_kit(size))
        assert kit[("قابلو نحاس 1×150 ملم²", "متر")] == outputs * 40


def test_everything_else_is_shared_across_ratings():
    """ما لا يتبع السعة ولا المخارج: تسع مواد لا تتغيّر كمّاً بين السعات الثلاث.

    الثلاثة التابعة للمخارج (القابلو وترمنله ومعدات ربطه) مستثناة — تتغيّر في
    السعة 630 وحدها لأن مخارجها أربعة (ق-٤٣).
    """
    kits = {s: dict(transformer_kit(s)) for s in TransformerSize}
    shared = set.intersection(*(set(k) for k in kits.values()))
    shared -= {
        ("قابلو نحاس 1×150 ملم²", "متر"),
        ("ترمنل 150 ملم²", "عدد"),
        ("معدات ربط ألمنيوم – نحاس", "عدد"),
    }
    assert len(shared) == 9
    for material in shared:
        assert len({k[material] for k in kits.values()}) == 1


def test_two_items_follow_the_outputs_not_the_rating():
    """القابلو وترمنله يتبعان عدد المخارج (ق-٤٣). ومعدات الربط خرجت منهما (ق-٥٦)."""
    for size, (outputs, _amps) in EXPECTED_OUTPUTS.items():
        kit = dict(transformer_kit(size))
        assert kit[("قابلو نحاس 1×150 ملم²", "متر")] == outputs * 40
        assert kit[("ترمنل 150 ملم²", "عدد")] == outputs * 12


def test_the_fixed_items_do_not_follow_the_outputs():
    """ترمنل 50 = 15 ومعدات الربط = 13 لكل محولة مهما بلغت مخارجها (ق-٥٦)."""
    for size in TransformerSize:
        kit = dict(transformer_kit(size))
        assert kit[("ترمنل 50 ملم²", "عدد")] == 15
        assert kit[("معدات ربط ألمنيوم – نحاس", "عدد")] == 13


def test_the_630_no_longer_lags_behind_its_cable():
    """كان الشذوذ: قابلو 630 تضاعف في ق-٢٧ وترمنله بقي 30. زال بـ ق-٤٣."""
    small = dict(transformer_kit(TransformerSize.KVA400))
    big = dict(transformer_kit(TransformerSize.KVA630))
    cable = ("قابلو نحاس 1×150 ملم²", "متر")
    lug = ("ترمنل 150 ملم²", "عدد")
    assert big[cable] / small[cable] == big[lug] / small[lug] == 2


def test_1000_kva_is_not_an_overhead_option():
    """سعة 1000 KVA أرضية فقط — لا تُستخدم في الشبكة الهوائية (ق-٢٦)."""
    assert [s.value for s in TransformerSize] == [250, 400, 630]


def test_every_rating_is_priced_after_the_update(catalog):
    """السعات الثلاث كلها مسعّرة بعد ق-٣٦ — لم تعد 250 و630 معلَّقتين."""
    prices = catalog["المواد"]
    assert prices["محولة 250 KVA جهد 11/0.4 ك.ف"]["السعر"] == 14_000_000
    assert prices["محولة 400 KVA جهد 11/0.4 ك.ف"]["السعر"] == 17_000_000
    assert prices["محولة 630 KVA جهد 11/0.4 ك.ف"]["السعر"] == 28_000_000
    assert prices["قاطع دورة 250 أمبير مع المتسعة"]["السعر"] == 425_000


def test_transformer_quantities_scale_linearly():
    lines = materials_equipment(Equipment(transformers={(KV11, KVA400): 3}))
    assert qty(lines, "محولة 400 KVA جهد 11/0.4 ك.ف") == 3
    assert qty(lines, "قابلو نحاس 1×150 ملم²") == 240   # 3 × مخرجين × 40
    assert qty(lines, "ترمنل 150 ملم²") == 72           # 3 × مخرجين × 12


def test_mixed_ratings_share_the_common_accessories():
    """محولتان بسعتين مختلفتين: المحولة والقاطع منفصلان، والملحقات تُجمَّع."""
    lines = materials_equipment(
        Equipment(
            transformers={(KV11, TransformerSize.KVA250): 2, (KV11, KVA400): 1}
        )
    )
    assert qty(lines, "محولة 250 KVA جهد 11/0.4 ك.ف") == 2
    assert qty(lines, "محولة 400 KVA جهد 11/0.4 ك.ف") == 1
    assert qty(lines, "قاطع دورة 250 أمبير مع المتسعة") == 4
    assert qty(lines, "قاطع دورة 400 أمبير مع المتسعة") == 2
    assert qty(lines, "قاعدة محولة مع الملحقات") == 3          # ملحق مشترك


def test_transformer_accessories_have_no_separate_labour(catalog):
    """أجر واحد للمحولة يشمل ملحقاتها كلها — بكل السعات معاً."""
    labour = labour_equipment(
        Equipment(transformers={(KV11, TransformerSize.KVA250): 1, (KV11, KVA400): 1}),
        catalog["أجور_العمل"],
    )
    assert [l.name for l in labour] == ["نصب المحولة"]
    assert labour[0].qty == 2
    assert labour[0].cost == 700_000


# ═══════════════════ جهد المحولة التحويلي 33/0.4 ك.ف (ق-٣٧) ═══════════════════


def test_the_33kv_transformer_swaps_only_the_arrester_and_the_fuse():
    """الجهد يغيّر مانعة الصواعق وفاصل الفيوز — لا شيء غيرهما.

    قاطع الدورة يبقى 400 أمبير لأن الضغط الواطئ 0.4 ك.ف في الحالتين، وقاعدة
    مانعة الصواعق واحدة مهما اختلف الجهد — بنصّ تعليماتك.
    """
    kit11 = dict(transformer_kit(KVA400, KV11))
    kit33 = dict(transformer_kit(KVA400, KV33))

    assert set(kit11) - set(kit33) == {
        ("محولة 400 KVA جهد 11/0.4 ك.ف", "عدد"),
        ("مانعة صواعق 11 KV", "سيت"),
        ("لنك فيوز 11 ك.ف مع السلك", "سيت"),
    }
    assert set(kit33) - set(kit11) == {
        ("محولة 400 KVA جهد 33/0.4 ك.ف", "عدد"),
        ("مانعة صواعق 33 ك.ف", "سيت"),
        ("لنك فيوز 33 ك.ف مع السلك", "سيت"),
    }
    # ما بقي متطابق كمّاً لا اسماً فقط
    for material in set(kit11) & set(kit33):
        assert kit11[material] == kit33[material], material

    assert kit33[("قاطع دورة 400 أمبير مع المتسعة", "عدد")] == 2
    assert kit33[("قاعدة مانعة صواعق مع الملحقات", "عدد")] == 1


def test_the_630_exception_survives_the_voltage_change():
    """630 بجهد 33/0.4: أربعة مخارج بقاطع 400 أمبير و160 م قابلو — كما في 11 (ق-٢٧)."""
    kit = dict(transformer_kit(TransformerSize.KVA630, KV33))
    assert kit[("قاطع دورة 400 أمبير مع المتسعة", "عدد")] == 4
    assert kit[("قابلو نحاس 1×150 ملم²", "متر")] == 160


def test_250_kva_exists_at_both_voltages():
    """السعة 250 متاحة بجهد 33/0.4 أيضاً — ولو نادراً، بتصحيحك في ق-٣٨.

    كانت مستبعَدة في ق-٣٧ بناءً على فهمي، فأصلحتَه: «يمكنك إضافة سعة 250 KVA
    للمحولات جهد 33/0.4 ك.ف، لا بأس من ذلك فهي متوفّرة ولو بصورة نادرة».
    """
    kit = dict(transformer_kit(TransformerSize.KVA250, KV33))
    assert kit[("محولة 250 KVA جهد 33/0.4 ك.ف", "عدد")] == 1
    assert kit[("قاطع دورة 250 أمبير مع المتسعة", "عدد")] == 2   # يتبع السعة لا الجهد
    assert kit[("مانعة صواعق 33 ك.ف", "سيت")] == 1
    assert kit[("لنك فيوز 33 ك.ف مع السلك", "سيت")] == 1
    assert len(TRANSFORMER_KITS) == 6   # ثلاث سعات × جهدين


def test_the_33kv_250_is_priced(catalog):
    assert catalog["المواد"]["محولة 250 KVA جهد 33/0.4 ك.ف"]["السعر"] == 16_500_000


def test_both_voltages_share_the_one_labour_line(catalog):
    """أجر «نصب المحولة» واحد للجهدين معاً — العمل نفسه."""
    labour = labour_equipment(
        Equipment(transformers={(KV11, KVA400): 1, (KV33, KVA400): 2}),
        catalog["أجور_العمل"],
    )
    assert [l.name for l in labour] == ["نصب المحولة"]
    assert labour[0].qty == 3


def test_the_two_voltages_do_not_merge_into_one_material():
    """محولة 400 بجهدين: مادتان منفصلتان، والملحقات المشتركة تُجمَّع."""
    lines = materials_equipment(
        Equipment(transformers={(KV11, KVA400): 1, (KV33, KVA400): 1})
    )
    assert qty(lines, "محولة 400 KVA جهد 11/0.4 ك.ف") == 1
    assert qty(lines, "محولة 400 KVA جهد 33/0.4 ك.ف") == 1
    assert qty(lines, "قاعدة محولة مع الملحقات") == 2       # مشترك
    assert qty(lines, "قاعدة مانعة صواعق مع الملحقات") == 2  # واحدة لكل محولة
    assert qty(lines, "مانعة صواعق 11 KV") == 1
    assert qty(lines, "مانعة صواعق 33 ك.ف") == 1


def test_an_unkeyed_transformer_is_rejected_not_silently_dropped():
    """مفتاح بالسعة وحدها (بلا جهد) يرفع خطأ — إهماله يخفي ملايين الدنانير (ق-٣٧)."""
    with pytest.raises(KeyError):
        materials_equipment(Equipment(transformers={KVA400: 1}))


# ═══════════════════ الفاصل هوائي 11 ك.ف ON LOAD: مصفوفة الجهد × الموقع ═══════════════════


def test_11kv_mid_network_has_no_arrester_and_full_cable():
    lines = materials_equipment(Equipment(onload_11_mid=1))
    assert {l.name: l.qty for l in lines} == {
        "فاصل هوائي 11 ك.ف ON LOAD": 1,
        "قابلو نحاس 1×150 ملم²": 30,        # موصول من جهتيه (ق-٥٠)
        "ترمنل 150 ملم²": 6,
        "قاعدة فاصل هوائي – براكيت جنل 2.1م": 1,
        "معدات ربط ألمنيوم – نحاس": 6,       # 3 أطوار × جهتين
    }


def test_11kv_cable_head_adds_the_arrester_and_halves_the_cable():
    """رأس القابلو: مانعة كاملة بتأريضها، ونصفُ القابلو ونصفُ المعدات (ق-٢٥، ق-٥٠)."""
    lines = materials_equipment(Equipment(onload_11_head=1))
    assert {l.name: l.qty for l in lines} == {
        "فاصل هوائي 11 ك.ف ON LOAD": 1,
        "قابلو نحاس 1×150 ملم²": 15,        # نصف الـ30 — جهة واحدة
        "ترمنل 150 ملم²": 6,                # لطرفَي القابلو، لا يتبع الطول
        "قاعدة فاصل هوائي – براكيت جنل 2.1م": 1,
        "معدات ربط ألمنيوم – نحاس": 3,       # 3 أطوار × جهة واحدة (ق-٥٠)
        "مانعة صواعق 11 KV": 1,
        "قاعدة مانعة صواعق مع الملحقات": 1,
        "قضيب نحاس تأريض 1.5 متر مع القفيص": 1,
        "قابلو نحاس 1×50 ملم²": 15,
        "ترمنل 50 ملم²": 1,
    }


def test_33kv_mid_network_uses_the_185_cable_and_no_arrester():
    """حالة لا وجود لها في الملف الأصلي أصلاً — أُضيفت بـ ق-٢٥."""
    lines = materials_equipment(Equipment(isolator_33_mid=1))
    assert {l.name: l.qty for l in lines} == {
        "فاصل هوائي 33 ك.ف ON LOAD": 1,
        "قابلو 1×185 ملم²": 30,
        "ترمنل 185 ملم²": 6,
        "قاعدة فاصل هوائي – براكيت جنل 2.1م": 1,
        # 210 ملم² لا العادية — السلك المتّصل 210/35 (ق-٣٧)
        "معدات ربط ألمنيوم – نحاس 210 ملم²": 6,
    }


def test_33kv_cable_head_matches_the_original_file_except_the_cable():
    """رأس القابلو 33 ك.ف: نصف القابلو ونصف المعدات (ت-٦ ثم ق-٥٠)."""
    lines = materials_equipment(Equipment(isolator_33_head=1))
    assert {l.name: l.qty for l in lines} == {
        "فاصل هوائي 33 ك.ف ON LOAD": 1,
        "قابلو 1×185 ملم²": 15,
        "ترمنل 185 ملم²": 6,
        "قاعدة فاصل هوائي – براكيت جنل 2.1م": 1,
        "معدات ربط ألمنيوم – نحاس 210 ملم²": 3,
        "مانعة صواعق 33 ك.ف": 1,
        "قاعدة مانعة صواعق مع الملحقات": 1,
        "قضيب نحاس تأريض 1.5 متر مع القفيص": 1,
        "قابلو نحاس 1×50 ملم²": 15,
        "ترمنل 50 ملم²": 1,
    }


def test_the_cable_head_halves_both_the_cable_and_the_fittings():
    """القابلو والمعدات ينصفان معاً على رأس القابلو — جهة واحدة لا جهتان (ق-٥٠)."""
    from engine.equipment import ISOLATOR_PARTS

    assert CABLE_HEAD_M * 2 == CABLE_MID_NETWORK_M == 30
    for voltage in IsolatorVoltage:
        kits = {p: dict(isolator_kit(voltage, p)) for p in IsolatorPosition}
        cable = ISOLATOR_PARTS[voltage]["cable"]
        fittings = ISOLATOR_PARTS[voltage]["fittings"]
        for material in (cable, fittings):
            assert kits[IsolatorPosition.CABLE_HEAD][material] * 2 == \
                kits[IsolatorPosition.MID_NETWORK][material], material


def test_the_lugs_do_not_follow_the_cable_length():
    """ترمنل القابلو 6 في الموقعين — لطرفَي القابلو، والطول لا يغيّر الأطراف."""
    from engine.equipment import ISOLATOR_PARTS

    for voltage in IsolatorVoltage:
        lug = ISOLATOR_PARTS[voltage]["lug"]
        for position in IsolatorPosition:
            assert dict(isolator_kit(voltage, position))[lug] == 6


def test_only_the_cable_head_carries_an_arrester():
    for voltage in IsolatorVoltage:
        mid = {name for (name, _u), _q in isolator_kit(voltage, IsolatorPosition.MID_NETWORK)}
        head = {name for (name, _u), _q in isolator_kit(voltage, IsolatorPosition.CABLE_HEAD)}
        assert not any("مانعة" in n for n in mid)
        assert any("مانعة صواعق" in n for n in head)
        # ولا مانعة بلا تأريض
        assert "قضيب نحاس تأريض 1.5 متر مع القفيص" in head


def test_each_voltage_uses_its_own_cable():
    """11 ك.ف قابلو نحاس 1×150، و33 ك.ف قابلو 1×185 — لا تبادل بينهما."""
    for position in IsolatorPosition:
        kv11 = {n for (n, _u), _q in isolator_kit(IsolatorVoltage.KV11, position)}
        kv33 = {n for (n, _u), _q in isolator_kit(IsolatorVoltage.KV33, position)}
        assert "قابلو نحاس 1×150 ملم²" in kv11 and "قابلو 1×185 ملم²" not in kv11
        assert "قابلو 1×185 ملم²" in kv33 and "قابلو نحاس 1×150 ملم²" not in kv33


def test_the_two_positions_share_one_priced_material_and_one_labour_item(catalog):
    """الموقع لا يغيّر المادة ولا الأجر — لكن المصدر يميّزهما للتتبّع."""
    eq = Equipment(onload_11_mid=2, onload_11_head=3)
    lines = materials_equipment(eq)
    assert qty(lines, "فاصل هوائي 11 ك.ف ON LOAD") == 5

    sources = [l.source for l in lines if l.name == "فاصل هوائي 11 ك.ف ON LOAD"]
    assert sources == [
        "فاصل 11 ك.ف — منتصف الشبكة: 2 × 1",
        "فاصل 11 ك.ف — على رأس القابلو: 3 × 1",
    ]

    labour = labour_equipment(eq, catalog["أجور_العمل"])
    assert [(l.name, l.qty) for l in labour] == [("نصب الفاصل ON-LOAD", 5)]


def test_the_two_voltages_have_separate_labour_items(catalog):
    eq = Equipment(onload_11_mid=1, isolator_33_head=2)
    labour = labour_equipment(eq, catalog["أجور_العمل"])
    assert [(l.name, l.qty, l.cost) for l in labour] == [
        ("نصب الفاصل ON-LOAD", 1, 90_000),
        ("نصب فاصل هوائي 33 ك.ف", 2, 180_000),
    ]


# ═══════════════════ قفيص العمود المشبك ═══════════════════


def test_lattice_cage_is_quantity_only_with_no_kit_and_no_labour(catalog):
    eq = Equipment(lattice_cages=7)
    lines = materials_equipment(eq)
    assert {l.name: l.qty for l in lines} == {"قفيص عمود مشبك": 7}
    assert labour_equipment(eq, catalog["أجور_العمل"]) == []


# ═══════════════════ التكامل مع المشروع ═══════════════════


def test_empty_equipment_generates_nothing(catalog):
    assert materials_equipment(Equipment()) == []
    assert labour_equipment(Equipment(), catalog["أجور_العمل"]) == []
    assert not Equipment()
    assert Equipment(lattice_cages=1)


def test_project_defaults_to_no_equipment(catalog):
    """المشروع بلا تجهيزات ما لم تُدخَل صراحةً — لا محولة تسلّلت إلى التخمين."""
    result = compute(OverheadProject(), catalog)
    assert result["المواد"] == []
    assert result["الكلفة_الكلية"] == 0


def test_equipment_merges_into_project_totals(catalog):
    """المادة المشتركة تُجمَّع من كل مصادرها ويبقى تفصيلها ظاهراً."""
    from engine.types import Network11kV

    project = OverheadProject(
        net11=Network11kV(route_length_m=500, poles_lattice=5, poles_round=20),
        equipment=Equipment(transformers={(KV11, KVA400): 1}),
    )
    result = compute(project, catalog)
    earth = next(m for m in result["المواد"] if m["المادة"] == "سلك نحاس 50 ملم²")

    # 25 عموداً × 1.5 م = 37.5 من الأعمدة، و15 م من المحولة
    assert earth["الكمية"] == 53          # 52.5 مقرَّبة لأعلى متر (ق-٥٦)
    assert earth["مجمَّع"] is True
    # مصدران + سطر التقريب: التقريب يُعرض ولا يُخفى (ق-٥٦)
    assert len(earth["تفصيل"]) == 3
    assert {p["الكمية"] for p in earth["تفصيل"][:2]} == {37.5, 15}
    assert "تقريب 52.5" in earth["تفصيل"][-1]["المصدر"]


def test_every_equipment_material_has_an_entry_in_the_catalog(catalog):
    """حارس: كل مادة يولّدها المحرك لها صف في نسخة الأسعار — بسعر أو بتنبيه."""
    eq = Equipment(
        transformers={k: 1 for k in TRANSFORMER_KITS},
        onload_11_mid=1, onload_11_head=1,
        isolator_33_mid=1, isolator_33_head=1, lattice_cages=1,
    )
    prices = catalog["المواد"]
    for (name, unit), _qty in aggregate(materials_equipment(eq)).items():
        assert name in prices, f"مادة بلا صف في نسخة الأسعار: {name}"
        assert prices[name]["الوحدة"] == unit, f"وحدة مختلفة: {name}"


def test_no_equipment_material_is_left_unpriced(catalog):
    """بعد تحديث الأسعار (ق-٣٦) لم تبقَ مادة تجهيزات بلا سعر."""
    result = compute(
        OverheadProject(equipment=Equipment(
            transformers={k: 1 for k in TRANSFORMER_KITS},
            onload_11_mid=1, onload_11_head=1,
            isolator_33_mid=1, isolator_33_head=1, lattice_cages=1)),
        catalog,
    )
    assert result["أسعار_مفقودة"] == []


def test_transformer_cost_is_the_heaviest_single_line(catalog):
    """المحولة وحدها 17 مليوناً — رقم يستحق أن يُثبَّت باختبار."""
    result = compute(
        OverheadProject(equipment=Equipment(transformers={(KV11, KVA400): 1})), catalog
    )
    transformer = next(m for m in result["المواد"] if m["المادة"] == "محولة 400 KVA جهد 11/0.4 ك.ف")
    assert transformer["الكلفة"] == 17_000_000
    # قاطع الدورة 400 نزل من 1,145,000 إلى 650,000 وقاعدة المانعة صعدت إلى 150,000 (ق-٣٦)،
    # ثم نزلت المجموعة بـ ق-٤٣ (ترمنل 150: 30←24)، ثم صعدت بـ ق-٥٦
    # (معدات: 8←13 وترمنل 50: 8←15)
    assert result["كلفة_المواد"] == 22_634_000
    assert result["كلفة_العمل"] == 350_000
