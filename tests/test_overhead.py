# -*- coding: utf-8 -*-
"""اختبارات محرك الشبكة الهوائية.

كل اختبار يشير إلى بند المواصفة أو القرار الذي يتحقّق منه، ليبقى الرابط بين الرقم
ومصدره واضحاً عند أي مراجعة مستقبلية.
"""

import math

import pytest

from engine import load_catalog
from engine.overhead import (
    aggregate,
    bracket_purchase_11,
    compute,
    count_poles_11kv,
    count_poles_33kv,
    labour_33kv,
    materials_11kv,
    materials_33kv,
    wire_quantity,
)
from engine.types import (
    BracketPattern,
    CircuitType,
    Network11kV,
    Network33kV,
    OverheadProject,
    PoleType11,
    SupplyForm,
)

SINGLE, DOUBLE = CircuitType.SINGLE, CircuitType.DOUBLE
WITH, WITHOUT = SupplyForm.WITH_ACCESSORIES, SupplyForm.WITHOUT_ACCESSORIES
STD, ALT = BracketPattern.STANDARD, BracketPattern.ALTERNATIVE
LAT, RND = PoleType11.LATTICE, PoleType11.ROUND


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def qty_of(lines, name):
    return aggregate(lines).get((name, _unit_of(lines, name)), 0)


def _unit_of(lines, name):
    for line in lines:
        if line.name == name:
            return line.unit
    return ""


# ═════════════════════════ ١. حساب الأعمدة — 11 ك.ف ═════════════════════════
# المواصفة ٢.٢ — ق-١٤


@pytest.mark.parametrize(
    "length,total,lattice,round_,converted",
    [
        (500, 21, 5, 16, False),   # النهاية (21) تقع على موقع مشبك أصلاً
        (600, 25, 6, 19, True),    # النهاية (25) حُوِّلت من مدور إلى مشبك
        (1000, 41, 9, 32, False),  # النهاية (41) تقع على موقع مشبك أصلاً
    ],
)
def test_pole_count_11kv(length, total, lattice, round_, converted):
    result = count_poles_11kv(length)
    assert result.total == total
    assert result.lattice == lattice
    assert result.round_ == round_
    assert result.end_converted is converted
    assert result.lattice + result.round_ == result.total


def test_pole_count_11kv_rounds_up():
    """510 م: يُقرَّب لأعلى — الزيادة أفضل من النقصان (ق-١٤)."""
    assert count_poles_11kv(510).total == 22  # ceil(510/25)=21 مسافة + 1


def test_pole_count_11kv_zero_length():
    result = count_poles_11kv(0)
    assert (result.total, result.lattice, result.round_) == (0, 0, 0)


# ═════════════════════════ ٢. حساب الأعمدة — 33 ك.ف ═════════════════════════
# المواصفة ٣.٢ — ق-١٤


@pytest.mark.parametrize(
    "length,positions,mid,susp,poles_total",
    [
        (650, 11, 0, 9, 13),    # 650 = 650 بالضبط ← لا ركيزة وسطية
        (700, 12, 1, 9, 15),
        (2000, 32, 3, 27, 37),
    ],
)
def test_pole_count_33kv(length, positions, mid, susp, poles_total):
    result = count_poles_33kv(length)
    assert result.positions == positions
    assert result.mid_anchors == mid
    assert result.end_anchors == 2
    assert result.suspension == susp
    assert result.poles_total == poles_total


def test_pole_count_33kv_line_extension():
    """إكمال خط قائم: ركيزة بداية ونهاية واحدة بدل اثنتين."""
    result = count_poles_33kv(2000, end_anchors=1)
    assert result.end_anchors == 1
    assert result.suspension == 32 - 3 - 1


def test_pole_count_33kv_no_negative_suspension():
    """خط قصير جداً: عدد أعمدة التعليق لا يصير سالباً."""
    assert count_poles_33kv(30).suspension >= 0


# ═══════════════════════════ ٣. كمية السلك ═══════════════════════════
# المواصفة ١ — ق-١، ق-٢


def test_wire_single_circuit():
    """500 م × 3 أطوار × 1 دائرة × 1.1 = 1,650 م — يطابق الملف الأصلي."""
    assert wire_quantity(500, SINGLE, False, 0.10) == 1650


def test_wire_double_circuit():
    """الدائرة المزدوجة تضاعف الكمية: ×6 بدل ×3."""
    assert wire_quantity(500, DOUBLE, False, 0.10) == 3300


def test_wire_waste_already_included():
    """إذا كان الطول المُدخل يشمل الزيادة فلا تُضاف نسبة (ق-٢)."""
    assert wire_quantity(500, SINGLE, True, 0.10) == 1500


def test_wire_custom_waste_pct():
    """نسبة الزيادة قابلة للتعديل."""
    assert wire_quantity(500, SINGLE, False, 0.05) == 1575


def test_wire_rounds_up():
    assert wire_quantity(333, SINGLE, False, 0.10) == math.ceil(333 * 3 * 1.1)


# ══════════════════════ ٤. البراكيت — 11 ك.ف (12 حالة) ══════════════════════
# المواصفة ٢.٤ — ق-٥، ق-١٣


@pytest.mark.parametrize(
    "circuit,pattern,pole,supply,expected",
    [
        # الشبكة المفردة
        (SINGLE, STD, RND, WITH,    {}),
        (SINGLE, STD, RND, WITHOUT, {"1.2": 1}),
        (SINGLE, STD, LAT, WITH,    {"1.4": 1}),   # مؤكَّد صراحةً في كلام صاحب العمل
        (SINGLE, STD, LAT, WITHOUT, {"1.4": 2}),
        # الشبكة المزدوجة — النمط القياسي
        (DOUBLE, STD, RND, WITH,    {"1.2": 1, "1.4": 1}),
        (DOUBLE, STD, RND, WITHOUT, {"1.2": 2, "1.4": 1}),
        (DOUBLE, STD, LAT, WITH,    {"1.2": 4, "1.4": 1}),
        (DOUBLE, STD, LAT, WITHOUT, {"1.2": 4, "1.4": 2}),
        # الشبكة المزدوجة — النمط البديل
        (DOUBLE, ALT, RND, WITH,    {"1.2": 2}),
        (DOUBLE, ALT, RND, WITHOUT, {"1.2": 3}),
        (DOUBLE, ALT, LAT, WITH,    {"1.4": 5}),
        (DOUBLE, ALT, LAT, WITHOUT, {"1.4": 6}),
    ],
)
def test_bracket_purchase_11(circuit, pattern, pole, supply, expected):
    assert bracket_purchase_11(circuit, pattern, pole, supply) == expected


def test_bracket_pattern_ignored_for_single_circuit():
    """نمط البراكيت خاص بالمزدوجة — لا أثر له في المفردة."""
    assert bracket_purchase_11(SINGLE, STD, LAT, WITHOUT) == bracket_purchase_11(
        SINGLE, ALT, LAT, WITHOUT
    )


def test_extra_brackets_added_11kv():
    """البراكيت الإضافي يُضاف للمواد ولا يؤثر على الأجور (ق-٩)."""
    base = Network11kV(poles_lattice=10, lattice_supply=WITHOUT)
    with_extra = Network11kV(
        poles_lattice=10, lattice_supply=WITHOUT, extra_bracket_14=7
    )
    assert (
        qty_of(materials_11kv(with_extra), "براكيت 1.4 م مع الملحقات")
        - qty_of(materials_11kv(base), "براكيت 1.4 م مع الملحقات")
        == 7
    )


# ══════════════════════════ ٥. العوازل — 11 ك.ف ══════════════════════════
# المواصفة ٢.٣ — ق-٤


def test_insulators_11kv_single():
    """الدبوسي على كل الأعمدة، والقرصي على المشبك فقط."""
    lines = materials_11kv(Network11kV(poles_lattice=5, poles_round=20, circuit=SINGLE))
    assert qty_of(lines, "عازل دبوسي مع السبندل") == (5 + 20) * 3   # = 75
    assert qty_of(lines, "عازل قرصي مع الملحقات") == 5 * 6          # = 30
    assert qty_of(lines, "معدات ربط ألمنيوم – ألمنيوم") == 5 * 6    # = 30


def test_insulators_11kv_matches_original_excel():
    """يطابق الملف الأصلي في الحالة المفردة (5 مشبك + 20 مدور)."""
    lines = materials_11kv(Network11kV(poles_lattice=5, poles_round=20, circuit=SINGLE))
    assert qty_of(lines, "عازل دبوسي مع السبندل") == 75
    assert qty_of(lines, "عازل قرصي مع الملحقات") == 30


def test_insulators_11kv_double_is_exactly_twice():
    single = materials_11kv(Network11kV(poles_lattice=5, poles_round=20, circuit=SINGLE))
    double = materials_11kv(Network11kV(poles_lattice=5, poles_round=20, circuit=DOUBLE))
    for name in (
        "عازل دبوسي مع السبندل",
        "عازل قرصي مع الملحقات",
        "معدات ربط ألمنيوم – ألمنيوم",
    ):
        assert qty_of(double, name) == 2 * qty_of(single, name)


def test_round_pole_never_gets_disc_insulator():
    """العمود المدور لا يأخذ عازلاً قرصياً في أي حالة — القرصي للشد."""
    for circuit in (SINGLE, DOUBLE):
        lines = materials_11kv(Network11kV(poles_round=30, circuit=circuit))
        assert qty_of(lines, "عازل قرصي مع الملحقات") == 0
        assert qty_of(lines, "عازل دبوسي مع السبندل") > 0


# ═══════════════════ ٦. تجميع البراكيت 2م وخصم الفائض ═══════════════════
# المواصفة ٣.٣ — ق-١٥


@pytest.mark.parametrize(
    "circuit,supply,expected",
    [
        (SINGLE, WITH,    0),   # الحاجة 30 والمرفق 40 ← فائض 10 مُهمَل
        (SINGLE, WITHOUT, 30),
        (DOUBLE, WITH,    50),  # الحاجة 90 والمرفق 40 ← استُهلك الفائض بالكامل
        (DOUBLE, WITHOUT, 90),
    ],
)
def test_bracket_2m_pooling(circuit, supply, expected):
    net = Network33kV(
        poles_suspension=30, anchors_mid=3, anchors_end=2,
        circuit=circuit, pole_supply=supply,
    )
    assert qty_of(materials_33kv(net), "براكيت 2 متر") == expected


def test_bracket_2m_pooling_saves_ten_brackets():
    """بلا تجميع لكان الشراء 60 بدل 50 — أي فرق 10 براكيتات."""
    net = Network33kV(
        poles_suspension=30, anchors_mid=3, anchors_end=2,
        circuit=DOUBLE, pole_supply=WITH,
    )
    pooled = qty_of(materials_33kv(net), "براكيت 2 متر")
    naive = 30 * 3 - 30  # الحاجة ناقص المرفق مع أعمدة التعليق وحدها
    assert naive - pooled == 10


# ══════════════════ ٧. البراكيت والعوازل والمعدات — 33 ك.ف ══════════════════
# المواصفة ٣.٣ — ق-٦، ق-٧


@pytest.mark.parametrize(
    "circuit,b25,pin,disc,fittings",
    [
        (SINGLE, 10, 105, 30, 60),
        (DOUBLE, 30, 210, 60, 120),
    ],
)
def test_33kv_anchor_items(circuit, b25, pin, disc, fittings):
    """30 عمود تعليق و5 ركائز — أرقام جدول التصحيح في المواصفة ١٠."""
    net = Network33kV(poles_suspension=30, anchors_mid=3, anchors_end=2, circuit=circuit)
    lines = materials_33kv(net)
    assert qty_of(lines, "براكيت 2.5 متر") == b25
    assert qty_of(lines, "عازل دبوسي 33 ك.ف مع السبندل") == pin
    assert qty_of(lines, "عازل قرصي 33 ك.ف مع الملحقات") == disc
    assert qty_of(lines, "معدات المنيوم - المنيوم 210 ملم2") == fittings


def test_suspension_pole_gets_no_disc_insulator():
    """عمود التعليق يأخذ دبوسياً فقط — القرصي للركائز."""
    net = Network33kV(poles_suspension=30, circuit=SINGLE)
    lines = materials_33kv(net)
    assert qty_of(lines, "عازل قرصي 33 ك.ف مع الملحقات") == 0
    assert qty_of(lines, "عازل دبوسي 33 ك.ف مع السبندل") == 30 * 3


def test_anchor_is_two_poles():
    """كل ركيزة عمودان مشبكان 14م."""
    net = Network33kV(poles_suspension=30, anchors_mid=3, anchors_end=2)
    assert qty_of(materials_33kv(net), "عمود مشبك 14م") == 30 + (3 + 2) * 2


# ═══════════════════════ ٨. الكونكريت وشيش التسليح ═══════════════════════
# المواصفة ٢.٥، ٣.٤ — ق-١٦، ق-١٧


def test_concrete_11kv_matches_original():
    """5 مشبك + 20 مدور = 5×1.0 + 20×0.756 = 20.12 ← يُقرَّب إلى 21."""
    lines = materials_11kv(Network11kV(poles_lattice=5, poles_round=20))
    assert qty_of(lines, "كونكريت أساسات الأعمدة") == 21


def test_concrete_11kv_same_for_both_circuits():
    """كونكريت أعمدة 11م لا يتغيّر بنوع الدائرة (ق-٤)."""
    a = materials_11kv(Network11kV(poles_lattice=5, poles_round=20, circuit=SINGLE))
    b = materials_11kv(Network11kV(poles_lattice=5, poles_round=20, circuit=DOUBLE))
    assert qty_of(a, "كونكريت أساسات الأعمدة") == qty_of(b, "كونكريت أساسات الأعمدة")


def test_mid_anchor_concrete_identical_both_circuits():
    """ت-٢ مغلق: كونكريت الركيزة الوسطية 10.31 في الحالتين — مؤكَّد (ق-١٦)."""
    a = materials_33kv(Network33kV(anchors_mid=3, circuit=SINGLE))
    b = materials_33kv(Network33kV(anchors_mid=3, circuit=DOUBLE))
    assert qty_of(a, "كونكريت أساسات الأعمدة") == qty_of(b, "كونكريت أساسات الأعمدة")
    assert qty_of(a, "كونكريت أساسات الأعمدة") == math.ceil(3 * 10.31)


def test_concrete_rounded_up_separately_per_voltage():
    """التقريب على مستوى كل جهد على حدة، كما في الملف الأصلي."""
    project = OverheadProject(
        net11=Network11kV(poles_lattice=5, poles_round=20),      # 20.12 ← 21
        net33=Network33kV(poles_suspension=1, circuit=SINGLE),   #  1.56 ←  2
    )
    total = aggregate(materials_11kv(project.net11) + materials_33kv(project.net33))
    assert total[("كونكريت أساسات الأعمدة", "متر مكعب")] == 21 + 2


def test_rebar_independent_of_circuit_type():
    a = materials_33kv(Network33kV(anchors_mid=3, anchors_end=2, circuit=SINGLE))
    b = materials_33kv(Network33kV(anchors_mid=3, anchors_end=2, circuit=DOUBLE))
    expected = (3 * 4 + 2 * 6) / 130
    assert qty_of(a, "شيش تسليح") == pytest.approx(expected)
    assert qty_of(b, "شيش تسليح") == pytest.approx(expected)


def test_concrete_and_rebar_have_no_material_cost(catalog):
    """كمية فقط — الكلفة مضمّنة في أجور النصب (ق-١٧)."""
    project = OverheadProject(
        net11=Network11kV(poles_lattice=5, poles_round=20),
        net33=Network33kV(anchors_mid=3, anchors_end=2),
    )
    result = compute(project, catalog)
    for row in result["المواد"]:
        if row["المادة"] in ("كونكريت أساسات الأعمدة", "شيش تسليح"):
            assert row["الكمية"] > 0
            assert row["الكلفة"] == 0
            assert row["كمية_فقط"] is True


# ═════════════════════════ ٩. التأريض وستي رود ═════════════════════════
# المواصفة ٢.٥، ٥ — ق-١٨


def test_earthing_independent_of_circuit_type():
    a = materials_11kv(Network11kV(poles_lattice=5, poles_round=20, circuit=SINGLE))
    b = materials_11kv(Network11kV(poles_lattice=5, poles_round=20, circuit=DOUBLE))
    for name in ("سلك نحاس 50 ملم2", "ترمنل 50 ملم²"):
        assert qty_of(a, name) == qty_of(b, name)


def test_earthing_matches_original_excel():
    """25 عموداً × 1.5 = 37.5 م نحاس و25 ترمنل."""
    lines = materials_11kv(Network11kV(poles_lattice=5, poles_round=20))
    assert qty_of(lines, "سلك نحاس 50 ملم2") == 37.5
    assert qty_of(lines, "ترمنل 50 ملم²") == 25


def test_stay_wire_12m_for_11m_poles():
    lines = materials_11kv(Network11kV(poles_lattice=1, stay_rod_sets=4))
    assert qty_of(lines, "واير ستي") == 4 * 12
    assert qty_of(lines, "طقم ستي رود") == 4


def test_stay_wire_15m_for_14m_poles():
    lines = materials_33kv(Network33kV(poles_suspension=1, stay_rod_sets=4))
    assert qty_of(lines, "واير ستي") == 4 * 15


def test_stay_wire_both_voltages_aggregate():
    """ق-١٨: المُدخلان ينتجان أطوالاً مختلفة وتُجمَّع في مادة واحدة."""
    project = OverheadProject(
        net11=Network11kV(poles_lattice=1, stay_rod_sets=2),
        net33=Network33kV(poles_suspension=1, stay_rod_sets=3),
    )
    totals = aggregate(materials_11kv(project.net11) + materials_33kv(project.net33))
    assert totals[("واير ستي", "متر")] == 2 * 12 + 3 * 15  # = 69
    assert totals[("طقم ستي رود", "سيت")] == 5


# ═══════════════════════════ ١٠. أجور العمل ═══════════════════════════
# المواصفة ٢.٦، ٣.٦ — ق-١٦


def test_11kv_labour_unchanged_by_circuit_except_stringing(catalog):
    from engine.overhead import labour_11kv

    rates = catalog["أجور_العمل"]
    single = {l.name: l.cost for l in labour_11kv(
        Network11kV(route_length_m=500, poles_lattice=5, poles_round=20, circuit=SINGLE), rates)}
    double = {l.name: l.cost for l in labour_11kv(
        Network11kV(route_length_m=500, poles_lattice=5, poles_round=20, circuit=DOUBLE), rates)}

    assert single["نصب عمود مشبك 11م"] == double["نصب عمود مشبك 11م"]
    assert single["نصب عمود مدور 11م"] == double["نصب عمود مدور 11م"]
    assert double["تسليك شبكة الضغط العالي"] == 2 * single["تسليك شبكة الضغط العالي"]


def test_11kv_labour_matches_original_excel(catalog):
    """يطابق الملف الأصلي: 1,237,500 + 1,075,000 + 3,800,000."""
    from engine.overhead import labour_11kv

    lines = labour_11kv(
        Network11kV(route_length_m=500, poles_lattice=5, poles_round=20), catalog["أجور_العمل"]
    )
    costs = {l.name: l.cost for l in lines}
    assert costs["تسليك شبكة الضغط العالي"] == 1_237_500
    assert costs["نصب عمود مشبك 11م"] == 1_075_000
    assert costs["نصب عمود مدور 11م"] == 3_800_000


def test_33kv_labour_uses_circuit_specific_rates(catalog):
    rates = catalog["أجور_العمل"]
    net = Network33kV(poles_suspension=30, anchors_mid=3, anchors_end=2)
    net.circuit = SINGLE
    single = {l.name: l.cost for l in labour_33kv(net, rates)}
    net.circuit = DOUBLE
    double = {l.name: l.cost for l in labour_33kv(net, rates)}

    assert single["نصب عمود مشبك 14م"] == 30 * 260_000
    assert double["نصب عمود مشبك 14م"] == 30 * 450_000
    assert single["نصب ركيزة شد وسطية"] == 3 * 2_050_000
    assert double["نصب ركيزة شد وسطية"] == 3 * 2_075_000   # ت-٣ مغلق: فرق 1.2% مؤكَّد
    assert single["نصب ركيزة شد بداية ونهاية"] == 2 * 2_200_000
    assert double["نصب ركيزة شد بداية ونهاية"] == 2 * 3_250_000


# ═══════════════════════ ١١. التكامل والحالات الحدّية ═══════════════════════


def test_empty_project_is_zero(catalog):
    result = compute(OverheadProject(), catalog)
    assert result["المواد"] == []
    assert result["الكلفة_الكلية"] == 0


def test_missing_price_is_reported_not_silently_zero(catalog):
    """واير ستي بلا سعر — يُبلَّغ عنه صراحةً ولا يُحسب صفراً بصمت."""
    project = OverheadProject(net11=Network11kV(poles_lattice=1, stay_rod_sets=2))
    result = compute(project, catalog)
    assert "واير ستي" in result["أسعار_مفقودة"]


def test_materials_aggregate_across_voltages():
    """سلك النحاس يأتي من الجهدين ويُجمَّع في سطر واحد."""
    project = OverheadProject(
        net11=Network11kV(poles_lattice=5, poles_round=20),   # 25 عموداً
        net33=Network33kV(poles_suspension=10),               # 10 أعمدة
    )
    totals = aggregate(materials_11kv(project.net11) + materials_33kv(project.net33))
    assert totals[("سلك نحاس 50 ملم2", "متر")] == (25 + 10) * 1.5


def test_double_circuit_11kv_costs_more_than_single(catalog):
    """ق-٣: الدائرة المزدوجة في 11 ك.ف تُحسب فعلياً — وهو ما كان مفقوداً أصلاً."""
    base = dict(route_length_m=500, poles_lattice=5, poles_round=20)
    single = compute(OverheadProject(net11=Network11kV(**base, circuit=SINGLE)), catalog)
    double = compute(OverheadProject(net11=Network11kV(**base, circuit=DOUBLE)), catalog)
    assert double["كلفة_المواد"] > single["كلفة_المواد"]
    assert double["كلفة_العمل"] > single["كلفة_العمل"]
