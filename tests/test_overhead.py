# -*- coding: utf-8 -*-
"""اختبارات محرك الشبكة الهوائية.

كل اختبار يشير إلى بند المواصفة أو القرار الذي يتحقّق منه، ليبقى الرابط بين الرقم
ومصدره واضحاً عند أي مراجعة مستقبلية.
"""

import math

import copy

import pytest

from engine import load_catalog
from engine.overhead import (
    aggregate,
    bracket_need_11,
    bracket_purchase_11,
    compute,
    count_poles_11kv,
    count_poles_33kv,
    labour_33kv,
    poles_per_tension_bay,
    resolve_spans,
    suggest_poles_11kv,
    suggest_poles_33kv,
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
def test_pole_count_11kv_default_spans(length, total, lattice, round_, converted):
    """بالمسافات الافتراضية (25 و125) — يجب أن تبقى النتائج كما اعتُمدت قبل ق-٢٠."""
    result = count_poles_11kv(length, span=25, tension_span=125)
    assert result.total == total
    assert result.lattice == lattice
    assert result.round_ == round_
    assert result.end_converted is converted
    assert result.lattice + result.round_ == result.total


def test_pole_count_11kv_rounds_up():
    """510 م: يُقرَّب لأعلى — الزيادة أفضل من النقصان (ق-١٤)."""
    assert count_poles_11kv(510, 25, 125).total == 22  # ceil(510/25)=21 مسافة + 1


def test_pole_count_11kv_zero_length():
    result = count_poles_11kv(0, 25, 125)
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
def test_pole_count_33kv_default_spans(length, positions, mid, susp, poles_total):
    """بالمسافات الافتراضية (65 و650) — يجب أن تبقى النتائج كما اعتُمدت قبل ق-٢٠."""
    result = count_poles_33kv(length, span=65, tension_span=650)
    assert result.positions == positions
    assert result.mid_anchors == mid
    assert result.end_anchors == 2
    assert result.suspension == susp
    assert result.poles_total == poles_total


def test_pole_count_33kv_line_extension():
    """إكمال خط قائم: ركيزة بداية ونهاية واحدة بدل اثنتين."""
    result = count_poles_33kv(2000, 65, 650, end_anchors=1)
    assert result.end_anchors == 1
    assert result.suspension == 32 - 3 - 1


def test_pole_count_33kv_no_negative_suspension():
    """خط قصير جداً: عدد أعمدة التعليق لا يصير سالباً."""
    assert count_poles_33kv(30, 65, 650).suspension >= 0


# ═══════════════ ٢أ. المسافات مُدخلات يحدّدها المستخدم (ق-٢٠) ═══════════════


def test_tension_bay_uses_floor_so_tension_span_is_never_exceeded():
    """⌊مسافة الشد ÷ المسافة العامة⌋ — التقريب لأسفل يضمن ألا تتجاوز المسافة الفعلية."""
    assert poles_per_tension_bay(25, 125) == 5    # 5 × 25 = 125 بالضبط
    assert poles_per_tension_bay(40, 125) == 3    # 3 × 40 = 120 ≤ 125
    assert poles_per_tension_bay(65, 650) == 10   # 10 × 65 = 650 بالضبط
    assert poles_per_tension_bay(30, 100) == 3    # 3 × 30 =  90 ≤ 100


def test_tension_bay_never_zero():
    """لو كانت مسافة الشد أقصر من المسافة العامة ← كل عمود عمود شد."""
    assert poles_per_tension_bay(50, 20) == 1


@pytest.mark.parametrize(
    "span,tension_span,total,lattice,round_",
    [
        (25, 125, 41, 9, 32),   # الافتراضي
        (40, 125, 26, 10, 16),  # مسافة أوسع، مسافة الشد ثابتة ← أعمدة شد أكثر نسبياً
        (25, 250, 41, 5, 36),   # مسافة الشد أوسع ← أعمدة شد أقل
        (50, 200, 21, 6, 15),
    ],
)
def test_user_spans_change_pole_mix(span, tension_span, total, lattice, round_):
    """خط 1000 م بمسافات مختلفة يحدّدها المستخدم."""
    result = count_poles_11kv(1000, span, tension_span)
    assert (result.total, result.lattice, result.round_) == (total, lattice, round_)


def test_actual_tension_spacing_never_exceeds_requested():
    """تحقّق شامل: المسافة الفعلية بين أعمدة الشد ≤ ما طلبه المستخدم."""
    for span in (20, 25, 30, 35, 40, 50, 65):
        for tension_span in (100, 125, 150, 200, 250, 650):
            if tension_span < span:
                continue
            step = poles_per_tension_bay(span, tension_span)
            assert step * span <= tension_span + 1e-9


def test_ends_are_always_tension_regardless_of_spans():
    """القاعدة الثابتة: طرفا الخط عمودا شد مهما كانت المسافات (ق-٢٠)."""
    for span in (20, 25, 33, 40, 60):
        for tension_span in (100, 125, 175, 300):
            r = count_poles_11kv(777, span, tension_span)
            # الطرفان مشبكان ⇒ لا يمكن أن يقلّ عدد المشبك عن 2 في خط فيه أكثر من عمود
            assert r.lattice >= 2
            assert r.lattice + r.round_ == r.total


def test_spans_resolve_from_catalog_when_not_given(catalog):
    """المسافة غير المُدخلة تُقرأ من ملف البيانات — مصدر واحد لا يُكرَّر (ق-٢٠)."""
    net = Network11kV(route_length_m=1000)
    assert resolve_spans(net, catalog) == (25.0, 125.0)
    assert suggest_poles_11kv(net, catalog).lattice == 9


def test_user_spans_override_catalog_defaults(catalog):
    net = Network11kV(route_length_m=1000, span_m=40, tension_span_m=125)
    assert resolve_spans(net, catalog) == (40.0, 125.0)
    assert suggest_poles_11kv(net, catalog).lattice == 10


def test_33kv_spans_resolve_and_override(catalog):
    net = Network33kV(route_length_m=2000)
    assert resolve_spans(net, catalog) == (65.0, 650.0)
    assert suggest_poles_33kv(net, catalog).mid_anchors == 3

    net.tension_span_m = 400
    assert suggest_poles_33kv(net, catalog).mid_anchors == 5


def test_invalid_span_is_rejected_not_silently_accepted(catalog):
    """المسافة صفر أو سالبة تُرفض صراحةً بدل أن تنتج قسمة على صفر."""
    for bad in (0, -25):
        with pytest.raises(ValueError):
            resolve_spans(Network11kV(route_length_m=500, span_m=bad), catalog)


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
        # «مع الملحقات» = **براكيت واحد** من مقاس العمود يُخصم من الحاجة
        # (ق-٥، وأعاد المستخدم تثبيته نصّاً في ق-٦٠ فأُلغي ق-٥٦/أ).
        (SINGLE, STD, RND, WITH,    {}),                    # الحاجة 1 ناقص 1
        (SINGLE, STD, LAT, WITH,    {"1.4": 1}),            # الحاجة 2 ناقص 1
        (DOUBLE, STD, RND, WITH,    {"1.2": 1, "1.4": 1}),  # 1.4 لا يُخصم منه
        (DOUBLE, STD, LAT, WITH,    {"1.4": 5}),            # الحاجة 6 ناقص 1
        (DOUBLE, ALT, RND, WITH,    {"1.2": 2}),
        (DOUBLE, ALT, LAT, WITH,    {"1.4": 5}),
        # «بدون ملحقات» = الحاجة كاملة
        (SINGLE, STD, RND, WITHOUT, {"1.2": 1}),
        (SINGLE, STD, LAT, WITHOUT, {"1.4": 2}),
        (DOUBLE, STD, RND, WITHOUT, {"1.2": 2, "1.4": 1}),
        # المشبك 6× 1.4م في كلا النمطين (ق-٢١)
        (DOUBLE, STD, LAT, WITHOUT, {"1.4": 6}),
        (DOUBLE, ALT, RND, WITHOUT, {"1.2": 3}),
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
        qty_of(materials_11kv(with_extra), "براكيت جنل 1.4 م مع الملحقات")
        - qty_of(materials_11kv(base), "براكيت جنل 1.4 م مع الملحقات")
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
        # عمود 14م «مع الملحقات» يأتي معه براكيت 2م **واحد** لا البراكيت كلها،
        # بخلاف عمود 11م (ق-٥٩ يصحّح تعميم ق-٥٨/ج ويُبقي تجميع ق-١٥).
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
    assert qty_of(materials_33kv(net), "براكيت جنل 2 متر") == expected


def test_the_bare_pole_price_is_derived_from_the_kitted_one(catalog):
    """السعر المثبَّت هو سعر العمود مع ملحقاته، والعاري = ذاك ناقص براكيته (ق-٥٨).

    الاشتقاق يُحسب عند التحميل لا يُخزَّن، فلا ينفصل الرقمان عند تحديث الأسعار:
    تُحدَّث قيمة واحدة ويتبعها المشتقّ.
    """
    prices = catalog["المواد"]
    for bare, kitted, bracket in (
        ("عمود 11م مشبك", "عمود 11م مشبك مع الملحقات", "براكيت جنل 1.4 م مع الملحقات"),
        ("عمود 11م مدوّر", "عمود 11م مدوّر مع الملحقات", "براكيت جنل 1.2 م مع الملحقات"),
        ("عمود مشبك 14م", "عمود مشبك 14م مع الملحقات", "براكيت جنل 2 متر"),
    ):
        assert prices[bare]["السعر"] == (
            prices[kitted]["السعر"] - prices[bracket]["السعر"]
        ), bare
        assert "مشتقّ" in prices[bare]["سبب"]


def test_a_derived_price_follows_its_source(catalog):
    """حارس: تغيير سعر الأصل يغيّر المشتقّ — وهو كلّ الغرض من الاشتقاق."""
    import copy

    from engine import _resolve_derived_prices

    edited = copy.deepcopy(catalog)
    edited["المواد"]["عمود 11م مشبك مع الملحقات"]["السعر"] = 2_000_000
    _resolve_derived_prices(edited)
    bracket = edited["المواد"]["براكيت جنل 1.4 م مع الملحقات"]["السعر"]
    assert edited["المواد"]["عمود 11م مشبك"]["السعر"] == 2_000_000 - bracket


def test_a_derived_price_with_a_missing_source_is_reported_not_guessed(catalog):
    """طرفٌ ناقص ← `None` فيُبلَّغ عنه، لا رقم مخمَّن."""
    import copy

    from engine import _resolve_derived_prices

    edited = copy.deepcopy(catalog)
    edited["المواد"]["براكيت جنل 1.4 م مع الملحقات"]["السعر"] = None
    _resolve_derived_prices(edited)
    assert edited["المواد"]["عمود 11م مشبك"]["السعر"] is None


def test_bracket_2m_pooling_saves_ten_brackets():
    """بلا تجميع لكان الشراء 60 بدل 50 — أي فرق 10 براكيتات."""
    net = Network33kV(
        poles_suspension=30, anchors_mid=3, anchors_end=2,
        circuit=DOUBLE, pole_supply=WITH,
    )
    pooled = qty_of(materials_33kv(net), "براكيت جنل 2 متر")
    naive = 30 * 3 - 30  # الحاجة ناقص المرفق مع أعمدة التعليق وحدها
    assert naive - pooled == 10


def test_poles_14m_with_accessories_change_name_but_keep_their_brackets():
    """ق-٥٩: الاسم وحده يتغيّر «مع الملحقات» — والبراكيت تُشترى بعد خصم المرفق.

    هذا حارسٌ على الخطأ الذي وقعتُ فيه في ق-٥٨/ج: تعميم قاعدة 11م (تُرفَق
    البراكيت كلها) على 14م. المرفق مع عمود 14م براكيت 2م **واحد** لا غير،
    وبراكيت الركائز 2.5م تُشترى كاملةً في الحالتين.
    """
    net = Network33kV(
        poles_suspension=30, anchors_mid=3, anchors_end=2,
        circuit=DOUBLE, pole_supply=WITH, extra_bracket_2=5,
    )
    lines = materials_33kv(net)
    assert qty_of(lines, "براكيت جنل 2 متر") == 50 + 5      # المُجمَّع + الإضافي
    assert qty_of(lines, "براكيت جنل 2.5 متر") == 30        # الركائز كاملةً
    assert qty_of(lines, "عمود مشبك 14م مع الملحقات") == 30 + 10
    assert qty_of(lines, "عمود مشبك 14م") == 0


def test_poles_14m_without_accessories_bring_no_bracket_at_all():
    """«بدون ملحقات» ← العمود عارٍ، فتُشترى البراكيت كلها (ق-٥٩)."""
    net = Network33kV(
        poles_suspension=30, anchors_mid=3, anchors_end=2,
        circuit=DOUBLE, pole_supply=WITHOUT,
    )
    lines = materials_33kv(net)
    assert qty_of(lines, "براكيت جنل 2 متر") == 90          # 30 × 3 بلا خصم
    assert qty_of(lines, "براكيت جنل 2.5 متر") == 30
    assert qty_of(lines, "عمود مشبك 14م") == 30 + 10
    assert qty_of(lines, "عمود مشبك 14م مع الملحقات") == 0


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
    assert qty_of(lines, "براكيت جنل 2.5 متر") == b25
    assert qty_of(lines, "عازل دبوسي 33 ك.ف مع السبندل") == pin
    assert qty_of(lines, "عازل قرصي 33 ك.ف مع الملحقات") == disc
    assert qty_of(lines, "معدات ربط ألمنيوم – ألمنيوم 210 ملم²") == fittings


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
    """شيش التسليح لا يتغيّر بنوع الدائرة — ويُقرَّب لأقرب عُشر طن لأعلى (ق-٣٢)."""
    a = materials_33kv(Network33kV(anchors_mid=3, anchors_end=2, circuit=SINGLE))
    b = materials_33kv(Network33kV(anchors_mid=3, anchors_end=2, circuit=DOUBLE))
    raw = (3 * 4 + 2 * 6) / 130           # 0.1846...
    expected = 0.2                        # مقرَّب لأعلى لأقرب عُشر
    assert qty_of(a, "شيش تسليح") == pytest.approx(expected)
    assert qty_of(b, "شيش تسليح") == pytest.approx(expected)
    assert raw < expected                 # التقريب فعلياً لأعلى لا تطابقاً صدفة


def test_rebar_rounds_up_to_the_nearest_tenth_of_a_ton():
    """0.18 ← 0.2 — المثال الذي طلب المستخدم تطبيقه حرفياً (ق-٣٢)."""
    lines = materials_33kv(Network33kV(anchors_mid=1, anchors_end=1))
    raw = (1 * 4 + 1 * 6) / 130           # = 0.0769...
    assert qty_of(lines, "شيش تسليح") == pytest.approx(0.1)
    assert raw < 0.1


def test_rebar_exact_tenth_is_not_bumped_up_further():
    """قيمة تقع بالضبط على عُشر لا تُقرَّب إلى العُشر التالي."""
    from engine.overhead import REBAR_DIVISOR, _roundup

    exact = 0.2
    assert _roundup(exact, decimals=1) == pytest.approx(0.2)


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
    for name in ("سلك نحاس 50 ملم²", "ترمنل 50 ملم²"):
        assert qty_of(a, name) == qty_of(b, name)


def test_earthing_matches_original_excel():
    """25 عموداً × 1.5 = 37.5 م نحاس و25 ترمنل."""
    lines = materials_11kv(Network11kV(poles_lattice=5, poles_round=20))
    assert qty_of(lines, "سلك نحاس 50 ملم²") == 37.5
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

    assert single["نصب عمود مشبك تعليق 14م"] == 30 * 260_000
    assert double["نصب عمود مشبك تعليق 14م"] == 30 * 450_000
    assert single["نصب ركيزة شد وسطية عمود 14م"] == 3 * 2_050_000
    assert double["نصب ركيزة شد وسطية عمود 14م"] == 3 * 2_075_000   # ت-٣ مغلق: فرق 1.2% مؤكَّد
    assert single["نصب ركيزة شد بداية ونهاية عمود 14م"] == 2 * 2_200_000
    assert double["نصب ركيزة شد بداية ونهاية عمود 14م"] == 2 * 3_250_000


# ═══════════════════════ ١١. التكامل والحالات الحدّية ═══════════════════════


def test_empty_project_is_zero(catalog):
    result = compute(OverheadProject(), catalog)
    assert result["المواد"] == []
    assert result["الكلفة_الكلية"] == 0


def test_missing_price_is_reported_not_silently_zero(catalog):
    """المادة بلا سعر يُبلَّغ عنها صراحةً ولا تُحسب صفراً بصمت.

    تُختبر الآلية بسعر **مُحقون** لا بمادة حقيقية: بعد ق-٣٦ صارت كل المواد
    مسعّرة، فربط الاختبار بمادة بعينها يجعله يفشل مع كل تحديث أسعار.
    """
    catalog = copy.deepcopy(catalog)
    catalog["المواد"]["عمود 11م مشبك"]["السعر"] = None

    result = compute(OverheadProject(net11=Network11kV(poles_lattice=1)), catalog)
    assert "عمود 11م مشبك" in result["أسعار_مفقودة"]
    row = next(r for r in result["المواد"] if r["المادة"] == "عمود 11م مشبك")
    assert row["الكمية"] == 1
    assert row["الكلفة"] == 0          # لا تُحتسب، لكنها مُبلَّغ عنها


def test_stay_wire_is_quantity_only_not_missing(catalog):
    """واير ستي: سعره مضمَّن في «طقم ستي رود» — كمية فقط لا سعر مفقود (ق-٣٦)."""
    result = compute(
        OverheadProject(net11=Network11kV(poles_lattice=1, stay_rod_sets=2)), catalog
    )
    assert "واير ستي" not in result["أسعار_مفقودة"]
    row = next(r for r in result["المواد"] if r["المادة"] == "واير ستي")
    assert row["الكمية"] == 24         # 2 طقم × 12 م
    assert row["كمية_فقط"] is True
    assert row["الكلفة"] == 0


def test_materials_aggregate_across_voltages():
    """سلك النحاس يأتي من الجهدين ويُجمَّع في سطر واحد."""
    project = OverheadProject(
        net11=Network11kV(poles_lattice=5, poles_round=20),   # 25 عموداً
        net33=Network33kV(poles_suspension=10),               # 10 أعمدة
    )
    totals = aggregate(materials_11kv(project.net11) + materials_33kv(project.net33))
    assert totals[("سلك نحاس 50 ملم²", "متر")] == (25 + 10) * 1.5


def test_double_circuit_11kv_costs_more_than_single(catalog):
    """ق-٣: الدائرة المزدوجة في 11 ك.ف تُحسب فعلياً — وهو ما كان مفقوداً أصلاً."""
    base = dict(route_length_m=500, poles_lattice=5, poles_round=20)
    single = compute(OverheadProject(net11=Network11kV(**base, circuit=SINGLE)), catalog)
    double = compute(OverheadProject(net11=Network11kV(**base, circuit=DOUBLE)), catalog)
    assert double["كلفة_المواد"] > single["كلفة_المواد"]
    assert double["كلفة_العمل"] > single["كلفة_العمل"]


# ═══════════════ ١٢. تتبّع مصدر الرقم (تدقيق الكميات) ═══════════════


def test_every_material_carries_its_breakdown(catalog):
    """كل مادة تحمل تفصيل مصادرها، ومجموع التفصيل يساوي الكمية بالضبط."""
    project = OverheadProject(
        net11=Network11kV(route_length_m=500, poles_lattice=5, poles_round=16),
        net33=Network33kV(route_length_m=2000, poles_suspension=27, anchors_mid=3,
                          anchors_end=2, circuit=DOUBLE),
    )
    result = compute(project, catalog)
    assert result["المواد"]
    for row in result["المواد"]:
        assert row["تفصيل"], f"{row['المادة']} بلا تفصيل"
        assert sum(p["الكمية"] for p in row["تفصيل"]) == pytest.approx(row["الكمية"])
        assert all(p["المصدر"] for p in row["تفصيل"])


def test_bracket_breakdown_separates_each_contributor(catalog):
    """البراكيت 1.4 يأتي من ثلاثة مصادر — يجب أن تظهر منفصلة لا مجموعة."""
    net = Network11kV(
        poles_lattice=5, poles_round=16, circuit=DOUBLE,
        lattice_supply=WITH, round_supply=WITH, extra_bracket_14=3,
    )
    result = compute(OverheadProject(net11=net), catalog)
    row = next(r for r in result["المواد"] if r["المادة"] == "براكيت جنل 1.4 م مع الملحقات")
    assert row["مجمَّع"] is True
    assert len(row["تفصيل"]) == 3
    # مشبك 5×5=25 (الحاجة 6 ناقص 1) + مدوّر 16×1 + إضافي 3
    assert {p["الكمية"] for p in row["تفصيل"]} == {25, 16, 3}
    assert any("إضافي" in p["المصدر"] for p in row["تفصيل"])
    assert any("مشبك" in p["المصدر"] for p in row["تفصيل"])
    assert any("مدوّر" in p["المصدر"] for p in row["تفصيل"])


@pytest.mark.parametrize(
    "supply,b14,b12",
    [
        # أرقام **صادق عليها المستخدم نصّاً** في ق-٦٣ بعد تدقيق الحالة معه:
        # «في حالة 9 أعمدة مشبكة (عمود مشبك مع الملحقات)، وإضافة 4 براكيت جنل
        #  1.4م يدوي، يصبح المجموع … 13 … وفي حالة (عمود مشبك) يصبح المجموع 22».
        (WITH,    13, 0),      # 9 × (2 − 1) + 4  ·  والمدوّر: 1 − 1 = صفر
        (WITHOUT, 22, 32),     # 9 × 2 + 4        ·  والمدوّر: 32 × 1
    ],
)
def test_the_trial_work_order_case(catalog, supply, b14, b12):
    """حالة أمر عملك التجريبي بعينها: 9 مشبك + 32 مدوّر، مفردة، +4 إضافي.

    **هذا الاختبار يُلغي ق-٥٦/أ ويُثبّت ق-٦٠.** كان يطالب بـ4 (البراكيت كلها
    مرفقة)، وصحّحتَ ذلك في ق-٦٠ ثم صادقتَ على الرقمين صراحةً في ق-٦٣.

    ولاحظ أن **العمود المدوّر يختفي «مع الملحقات»** (حاجته 1 والمرفق 1) — وهو
    ما أوقع اللبس أصلاً، إذ اختفى صفّ كامل من الجدول.
    """
    net = Network11kV(
        poles_lattice=9, poles_round=32,
        lattice_supply=supply, round_supply=supply, extra_bracket_14=4,
    )
    result = compute(OverheadProject(net11=net), catalog)
    quantities = {r["المادة"]: r["الكمية"] for r in result["المواد"]}
    assert quantities["براكيت جنل 1.4 م مع الملحقات"] == b14
    assert quantities.get("براكيت جنل 1.2 م مع الملحقات", 0) == b12

    row = next(r for r in result["المواد"] if r["المادة"] == "براكيت جنل 1.4 م مع الملحقات")
    assert any("إضافي" in p["المصدر"] for p in row["تفصيل"])


def test_a_round_pole_in_a_double_circuit_still_needs_brackets(catalog):
    """بنصّك: «ولا ننسى إضافة براكيت جنل إضافي لكل عمود مدوّر في المزدوجة».

    المرفق 1.2م واحد، والحاجة 2× 1.2م + 1× 1.4م ← يبقى 1.2م واحد و1.4م واحد.
    والخصم من مقاس العمود وحده، فلا يُمسّ 1.4م.
    """
    net = Network11kV(poles_round=32, circuit=DOUBLE, round_supply=WITH)
    result = compute(OverheadProject(net11=net), catalog)
    qty = {r["المادة"]: r["الكمية"] for r in result["المواد"]}
    assert qty["براكيت جنل 1.2 م مع الملحقات"] == 32
    assert qty["براكيت جنل 1.4 م مع الملحقات"] == 32


def test_the_pole_name_carries_its_supply_form(catalog):
    """«مع الملحقات» مادة أخرى باسم آخر (ق-٥٦)."""
    with_kit = compute(OverheadProject(net11=Network11kV(
        poles_lattice=9, poles_round=32, lattice_supply=WITH, round_supply=WITH)), catalog)
    without = compute(OverheadProject(net11=Network11kV(
        poles_lattice=9, poles_round=32,
        lattice_supply=WITHOUT, round_supply=WITHOUT)), catalog)

    assert {r["المادة"] for r in with_kit["المواد"] if "عمود 11م" in r["المادة"]} == {
        "عمود 11م مشبك مع الملحقات", "عمود 11م مدوّر مع الملحقات"
    }
    assert {r["المادة"] for r in without["المواد"] if "عمود 11م" in r["المادة"]} == {
        "عمود 11م مشبك", "عمود 11م مدوّر"
    }


def test_shared_material_breakdown_names_both_voltages(catalog):
    """سلك النحاس يأتي من الجهدين — التفصيل يبيّن نصيب كل جهد."""
    project = OverheadProject(
        net11=Network11kV(poles_lattice=5, poles_round=16),
        net33=Network33kV(poles_suspension=27, anchors_mid=3, anchors_end=2),
    )
    result = compute(project, catalog)
    row = next(r for r in result["المواد"] if r["المادة"] == "سلك نحاس 50 ملم²")
    sources = [p["المصدر"] for p in row["تفصيل"]]
    assert any("11م" in s for s in sources)
    assert any("14م" in s for s in sources)
    assert sum(p["الكمية"] for p in row["تفصيل"]) == row["الكمية"]


def test_single_source_material_is_not_marked_aggregated(catalog):
    net = Network11kV(route_length_m=500)
    result = compute(OverheadProject(net11=net), catalog)
    row = next(r for r in result["المواد"] if r["المادة"] == "سلك ألمنيوم 120/20 ملم²")
    assert row["مجمَّع"] is False
    assert len(row["تفصيل"]) == 1


def test_rounded_concrete_breakdown_shows_the_unrounded_value(catalog):
    """الكونكريت مقرَّب لأعلى — التفصيل يعرض القيمة قبل التقريب لتفسير الفرق."""
    net = Network11kV(poles_lattice=5, poles_round=16)   # 5 + 12.096 = 17.096 ← 18
    result = compute(OverheadProject(net11=net), catalog)
    row = next(r for r in result["المواد"] if r["المادة"] == "كونكريت أساسات الأعمدة")
    assert row["الكمية"] == 18
    assert "17.096" in row["تفصيل"][0]["المصدر"]
    assert "مقرَّب لأعلى" in row["تفصيل"][0]["المصدر"]


def test_lattice_pole_uses_six_14m_brackets_in_both_double_patterns():
    """ق-٢١: العمود المشبك 6× 1.4م في المزدوجة بكلا النمطين — لا فرق بينهما."""
    for pattern in (STD, ALT):
        assert bracket_need_11(DOUBLE, pattern, LAT) == {"1.4": 6}
        assert bracket_purchase_11(DOUBLE, pattern, LAT, WITHOUT) == {"1.4": 6}
        assert bracket_purchase_11(DOUBLE, pattern, LAT, WITH) == {"1.4": 5}  # ق-٦٠


def test_lattice_pole_needs_no_12m_bracket_in_double_circuit():
    """لم يعد العمود المشبك يستهلك براكيت 1.2م إطلاقاً (ق-٢١)."""
    for pattern in (STD, ALT):
        for supply in (WITH, WITHOUT):
            assert "1.2" not in bracket_purchase_11(DOUBLE, pattern, LAT, supply)


def test_round_pole_brackets_are_unchanged_by_decision_21():
    """ق-٢١ يمسّ المشبك وحده — المدوّر يبقى كما اعتُمد في ق-٥."""
    assert bracket_need_11(DOUBLE, STD, RND) == {"1.2": 2, "1.4": 1}
    assert bracket_need_11(DOUBLE, ALT, RND) == {"1.2": 3}
    assert bracket_need_11(SINGLE, STD, RND) == {"1.2": 1}


def test_single_circuit_lattice_is_unchanged_by_decision_21():
    """ق-٢١ يخصّ المزدوجة وحدها — المفردة تبقى 2× 1.4م."""
    assert bracket_need_11(SINGLE, STD, LAT) == {"1.4": 2}
