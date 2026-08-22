# -*- coding: utf-8 -*-
"""محرك حساب الشبكة الهوائية — 11 ك.ف و33 ك.ف، مفردة ومزدوجة.

المرجع الكامل: docs/مواصفة_الشبكة_الهوائية.md
القرارات الحاكمة: docs/سجل_القرارات.md

مبدأ التصميم: كل دالة تولّد أسطر مواد `MaterialLine` مستقلة، ثم تُجمَّع بمفتاح
(الاسم + الوحدة) — نفس منطق `RAW_تفصيلي` ← `جدول_المواد` في الملف الأصلي. هذا يسمح
لعدة مصادر أن تساهم في المادة نفسها (مثال: سلك النحاس يأتي من أعمدة 11م و14م معاً)،
ويُبقي الباب مفتوحاً لإضافة مصادر لاحقاً — كقسم الضغط الواطئ على أعمدة 11م (ق-١٢).
"""

from __future__ import annotations

import math
from collections import OrderedDict

from .types import (
    BracketPattern,
    CircuitType,
    LabourLine,
    MaterialLine,
    Network11kV,
    Network33kV,
    OverheadProject,
    PoleCount11,
    PoleCount33,
    PoleType11,
    SupplyForm,
)

# ─────────────────────────────── ثوابت المواصفة ───────────────────────────────

PHASES = 3

# المسافات مُدخلات يحدّدها المستخدم (ق-٢٠). القيم الافتراضية تُقرأ من
# data/catalog_*.json تحت «المسافات_الافتراضية» — مصدر واحد لا يُكرَّر في الكود.
SPAN_DEFAULT_KEYS = {
    "11kv_span": "المسافة_بين_الأعمدة_11ك.ف",
    "11kv_tension": "المسافة_بين_أعمدة_الشد_11ك.ف",
    "33kv_span": "المسافة_بين_الأعمدة_33ك.ف",
    "33kv_tension": "المسافة_بين_الركائز_الوسطية_33ك.ف",
}

STAY_WIRE_PER_SET_11M = 12
STAY_WIRE_PER_SET_14M = 15

REBAR_DIVISOR = 130
REBAR_PER_MID_ANCHOR = 4
REBAR_PER_END_ANCHOR = 6

CONCRETE_11_LATTICE = 1.0
CONCRETE_11_ROUND = 0.756
CONCRETE_14_SUSPENSION = {CircuitType.SINGLE: 1.56, CircuitType.DOUBLE: 2.76}
CONCRETE_14_MID_ANCHOR = {CircuitType.SINGLE: 10.31, CircuitType.DOUBLE: 10.31}
CONCRETE_14_END_ANCHOR = {CircuitType.SINGLE: 12.26, CircuitType.DOUBLE: 18.76}

EARTH_WIRE_PER_POLE = 1.5
"""سلك نحاس 50 ملم2 لكل عمود (م) — لا يتغيّر بنوع الدائرة (ق-١٣ في المواصفة)."""

EARTH_TERMINAL_PER_POLE = 1

# أسماء المواد — يجب أن تطابق الملف الأصلي حرفياً ليطابق قالب الإيزو
M_WIRE_11 = ("سلك ألمنيوم 120/20 ملم²", "متر")
M_WIRE_33 = ("سلك ألمنيوم 210/35 ملم²", "متر")
M_POLE_11_LATTICE = ("عمود 11م مشبك", "عدد")
M_POLE_11_ROUND = ("عمود 11م مدوّر", "عدد")
M_POLE_14 = ("عمود مشبك 14م", "عدد")
M_PIN_INSULATOR_11 = ("عازل دبوسي مع السبندل", "عدد")
M_DISC_INSULATOR_11 = ("عازل قرصي مع الملحقات", "سيت")
M_PIN_INSULATOR_33 = ("عازل دبوسي 33 ك.ف مع السبندل", "عدد")
M_DISC_INSULATOR_33 = ("عازل قرصي 33 ك.ف مع الملحقات", "سيت")
M_AL_FITTINGS_11 = ("معدات ربط ألمنيوم – ألمنيوم", "عدد")
M_AL_FITTINGS_33 = ("معدات المنيوم - المنيوم 210 ملم2", "عدد")
M_BRACKET_12 = ("براكيت 1.2 م مع الملحقات", "عدد")
M_BRACKET_14 = ("براكيت 1.4 م مع الملحقات", "عدد")
M_BRACKET_2 = ("براكيت 2 متر", "عدد")
M_BRACKET_25 = ("براكيت 2.5 متر", "عدد")
M_EARTH_WIRE = ("سلك نحاس 50 ملم2", "متر")
M_EARTH_TERMINAL = ("ترمنل 50 ملم²", "عدد")
M_CONCRETE = ("كونكريت أساسات الأعمدة", "متر مكعب")
M_REBAR = ("شيش تسليح", "طن")
M_STAY_SET = ("طقم ستي رود", "سيت")
M_STAY_WIRE = ("واير ستي", "متر")

QUANTITY_ONLY = {M_CONCRETE[0], M_REBAR[0]}
"""مواد تُحسب كمّياً بلا كلفة — كلفتها مضمّنة في أجور النصب (ق-١٧)."""


def _roundup(value: float) -> int:
    """تقريب لأعلى — الزيادة أفضل من النقصان (ق-١٤)."""
    return math.ceil(round(value, 9))


# ────────────────────────── حساب الأعمدة (استرشادي) ──────────────────────────


def poles_per_tension_bay(span: float, tension_span: float) -> int:
    """عدد المسافات بين عمودَي شد متتاليين = ⌊مسافة الشد ÷ المسافة العامة⌋.

    يُقرَّب **لأسفل** عمداً — بعكس بقية الحسابات — لأن التقريب لأسفل هنا يعني أعمدة شد
    **أكثر** ومسافة فعلية بينها **لا تتجاوز** ما طلبه المستخدم. أي أن الاتجاه الآمن
    محفوظ: الزيادة أفضل من النقصان (ق-١٤).

    مثال: مسافة عامة 40 م ومسافة شد 125 م ← ⌊125/40⌋ = 3، أي عمود شد كل 120 م ≤ 125.
    """
    return max(1, math.floor(round(tension_span / span, 9)))


def count_poles_spanned(
    route_length_m: float, span: float, tension_span: float
) -> PoleCount11:
    """يقترح عدد الأعمدة ونوعها بمسافة عامة ومسافة شد (ق-١٤، ق-٢٠).

    عمود كل `span` متراً، وعمود شد (مشبك) كل `tension_span` متراً، وطرفا الخط مشبكان
    إلزاماً. فإن لم يقع العمود الأخير على موقع شد حُوِّل من مدور إلى مشبك.
    """
    if route_length_m <= 0:
        return PoleCount11(total=0, lattice=0, round_=0, end_converted=False)

    total = _roundup(route_length_m / span) + 1
    step = poles_per_tension_bay(span, tension_span)
    positions = set(range(1, total + 1, step))  # 1، 1+step، 1+2×step، …
    end_converted = total not in positions
    positions.add(total)  # طرف الخط عمود شد إلزاماً

    lattice = len(positions)
    return PoleCount11(
        total=total,
        lattice=lattice,
        round_=total - lattice,
        end_converted=end_converted,
    )


count_poles_11kv = count_poles_spanned
"""شبكة 11 ك.ف والضغط الواطئ تتقاسمان الخوارزمية نفسها بمسافات مختلفة."""


def count_poles_33kv(
    route_length_m: float,
    span: float,
    tension_span: float,
    end_anchors: int = 2,
) -> PoleCount33:
    """يقترح أعمدة وركائز 33 ك.ف (ق-١٤، ق-٢٠).

    عمود تعليق كل `span` متراً، وركيزة شد وسطية كل `tension_span` متراً. وموقع
    الركيزة يستهلك موقع عمود تعليق فيُخصم من عددها. و`end_anchors` تكون 1 في حالة
    إكمال خط قائم له ركيزة نهاية أصلاً.
    """
    if route_length_m <= 0:
        return PoleCount33(positions=0, suspension=0, mid_anchors=0, end_anchors=0)

    positions = _roundup(route_length_m / span) + 1
    step = poles_per_tension_bay(span, tension_span)
    # الركائز الوسطية تقع بين الطرفين حصراً — الطرفان ركيزتا بداية ونهاية
    mid_anchors = len(range(1 + step, positions, step))
    suspension = max(0, positions - mid_anchors - end_anchors)
    return PoleCount33(
        positions=positions,
        suspension=suspension,
        mid_anchors=mid_anchors,
        end_anchors=end_anchors,
    )


# ──────────────────────────────── كمية السلك ────────────────────────────────


def resolve_spans(net: Network11kV | Network33kV, catalog: dict) -> tuple[float, float]:
    """يعيد (المسافة العامة، مسافة الشد) للشبكة، بحلّ القيم غير المُدخلة من الافتراضيات.

    المصدر الوحيد للافتراضيات هو ملف البيانات — لا تُكرَّر في الكود (ق-٢٠).
    """
    defaults = catalog["المسافات_الافتراضية"]
    if isinstance(net, Network11kV):
        span_key, tension_key = SPAN_DEFAULT_KEYS["11kv_span"], SPAN_DEFAULT_KEYS["11kv_tension"]
    else:
        span_key, tension_key = SPAN_DEFAULT_KEYS["33kv_span"], SPAN_DEFAULT_KEYS["33kv_tension"]

    span = net.span_m if net.span_m is not None else defaults[span_key]
    tension = net.tension_span_m if net.tension_span_m is not None else defaults[tension_key]
    if span <= 0 or tension <= 0:
        raise ValueError("المسافات يجب أن تكون أكبر من صفر")
    return float(span), float(tension)


def suggest_poles_11kv(net: Network11kV, catalog: dict) -> PoleCount11:
    """الاقتراح الاسترشادي لأعمدة 11 ك.ف بمسافات هذه الشبكة."""
    span, tension = resolve_spans(net, catalog)
    return count_poles_11kv(net.route_length_m, span, tension)


def suggest_poles_33kv(net: Network33kV, catalog: dict, end_anchors: int = 2) -> PoleCount33:
    """الاقتراح الاسترشادي لأعمدة وركائز 33 ك.ف بمسافات هذه الشبكة."""
    span, tension = resolve_spans(net, catalog)
    return count_poles_33kv(net.route_length_m, span, tension, end_anchors)


def wire_quantity(
    route_length_m: float,
    circuit: CircuitType,
    length_includes_waste: bool,
    waste_pct: float,
) -> int:
    """كمية السلك = المسار × 3 أطوار × عدد الدوائر × معامل الزيادة (ق-١، ق-٢)."""
    if route_length_m <= 0:
        return 0
    waste_factor = 1.0 if length_includes_waste else 1.0 + waste_pct
    return _roundup(route_length_m * PHASES * circuit.circuits * waste_factor)


# ──────────────────────────── براكيت شبكة 11 ك.ف ────────────────────────────

# الحاجة الكاملة لكل عمود: (النمط، نوع العمود) ← {مقاس البراكيت: العدد}
BRACKET_NEED_11 = {
    (CircuitType.SINGLE, BracketPattern.STANDARD, PoleType11.ROUND): {"1.2": 1},
    (CircuitType.SINGLE, BracketPattern.STANDARD, PoleType11.LATTICE): {"1.4": 2},
    (CircuitType.DOUBLE, BracketPattern.STANDARD, PoleType11.ROUND): {"1.2": 2, "1.4": 1},
    # العمود المشبك: 6× 1.4م في كلا النمطين (ق-٢١ — يُعدّل ق-٥)
    (CircuitType.DOUBLE, BracketPattern.STANDARD, PoleType11.LATTICE): {"1.4": 6},
    (CircuitType.DOUBLE, BracketPattern.ALTERNATIVE, PoleType11.ROUND): {"1.2": 3},
    (CircuitType.DOUBLE, BracketPattern.ALTERNATIVE, PoleType11.LATTICE): {"1.4": 6},
}

BRACKET_INCLUDED_11 = {PoleType11.ROUND: "1.2", PoleType11.LATTICE: "1.4"}
"""ما يأتي مع العمود «مع الملحقات»: المدور 1.2م والمشبك 1.4م — واحد لكل عمود."""


def bracket_need_11(
    circuit: CircuitType, pattern: BracketPattern, pole: PoleType11
) -> dict[str, int]:
    """الحاجة الكاملة من البراكيت لعمود 11م واحد."""
    # النمط لا معنى له في الشبكة المفردة — تُقرأ دائماً من الجدول القياسي
    key_pattern = pattern if circuit is CircuitType.DOUBLE else BracketPattern.STANDARD
    return dict(BRACKET_NEED_11[(circuit, key_pattern, pole)])


def bracket_purchase_11(
    circuit: CircuitType,
    pattern: BracketPattern,
    pole: PoleType11,
    supply: SupplyForm,
) -> dict[str, int]:
    """البراكيت المطلوب شراؤه لعمود واحد = الحاجة − المرفق (لا يقلّ عن صفر)."""
    need = bracket_need_11(circuit, pattern, pole)
    if supply.includes_bracket:
        size = BRACKET_INCLUDED_11[pole]
        if size in need:
            need[size] = max(0, need[size] - 1)
    return {size: n for size, n in need.items() if n > 0}


# ──────────────────────────── توليد مواد 11 ك.ف ────────────────────────────


def materials_11kv(net: Network11kV) -> list[MaterialLine]:
    """يولّد أسطر مواد شبكة 11 ك.ف الهوائية."""
    lines: list[MaterialLine] = []
    if net.poles_lattice == 0 and net.poles_round == 0 and net.route_length_m <= 0:
        return lines

    add = lines.append
    lat, rnd = net.poles_lattice, net.poles_round
    poles = lat + rnd
    n = net.circuit.circuits

    # السلك
    qty = wire_quantity(
        net.route_length_m, net.circuit, net.length_includes_waste, net.waste_pct
    )
    if qty:
        factor = 1.0 if net.length_includes_waste else 1 + net.waste_pct
        add(MaterialLine(*M_WIRE_11, qty, f"مسار 11 ك.ف: "
                                          f"{net.route_length_m:,.0f} × 3 أطوار × {n} دائرة"
                                          f" × {factor:g} زيادة"))

    # الأعمدة
    if lat:
        add(MaterialLine(*M_POLE_11_LATTICE, lat, f"أعمدة 11 ك.ف: {lat} مشبك"))
    if rnd:
        add(MaterialLine(*M_POLE_11_ROUND, rnd, f"أعمدة 11 ك.ف: {rnd} مدوّر"))

    # العوازل — القرصي للشد فيُنصب على المشبك فقط، والدبوسي على كل الأعمدة
    if lat:
        add(MaterialLine(*M_PIN_INSULATOR_11, lat * 3 * n,
                         f"أعمدة 11م مشبك: {lat} × 3 × {n} دائرة"))
    if rnd:
        add(MaterialLine(*M_PIN_INSULATOR_11, rnd * 3 * n,
                         f"أعمدة 11م مدوّر: {rnd} × 3 × {n} دائرة"))
    if lat:
        add(MaterialLine(*M_DISC_INSULATOR_11, lat * 6 * n,
                         f"أعمدة 11م مشبك (للشد): {lat} × 6 × {n} دائرة"))
        add(MaterialLine(*M_AL_FITTINGS_11, lat * 6 * n,
                         f"أعمدة 11م مشبك: {lat} × 6 × {n} دائرة"))

    # البراكيت — سطر مستقل لكل مصدر، ليبقى تفصيل الرقم النهائي ظاهراً للمدقّق
    sizes = {"1.2": M_BRACKET_12, "1.4": M_BRACKET_14}
    for pole_type, count, supply, label in (
        (PoleType11.LATTICE, lat, net.lattice_supply, "أعمدة 11م مشبك"),
        (PoleType11.ROUND, rnd, net.round_supply, "أعمدة 11م مدوّر"),
    ):
        if not count:
            continue
        need = bracket_need_11(net.circuit, net.bracket_pattern, pole_type)
        purchase = bracket_purchase_11(net.circuit, net.bracket_pattern, pole_type, supply)
        for size, per_pole in purchase.items():
            deduction = ""
            if supply.includes_bracket and BRACKET_INCLUDED_11[pole_type] == size:
                deduction = f" (الحاجة {need[size]} ناقص 1 مرفق مع العمود)"
            add(MaterialLine(*sizes[size], per_pole * count,
                             f"{label}: {count} × {per_pole}{deduction}"))

    if net.extra_bracket_12:
        add(MaterialLine(*M_BRACKET_12, net.extra_bracket_12, "إضافي يُدخله المستخدم"))
    if net.extra_bracket_14:
        add(MaterialLine(*M_BRACKET_14, net.extra_bracket_14, "إضافي يُدخله المستخدم"))

    # التأريض — لا يتغيّر بنوع الدائرة
    if poles:
        add(MaterialLine(*M_EARTH_WIRE, poles * EARTH_WIRE_PER_POLE,
                         f"تأريض أعمدة 11م: {poles} عموداً × {EARTH_WIRE_PER_POLE}"))
        add(MaterialLine(*M_EARTH_TERMINAL, poles * EARTH_TERMINAL_PER_POLE,
                         f"تأريض أعمدة 11م: {poles} عموداً × {EARTH_TERMINAL_PER_POLE}"))

    # الكونكريت — يُقرَّب لأعلى على مستوى الجهد، كما في الملف الأصلي
    concrete = lat * CONCRETE_11_LATTICE + rnd * CONCRETE_11_ROUND
    if concrete:
        add(MaterialLine(*M_CONCRETE, _roundup(concrete),
                         f"أساسات أعمدة 11م: {lat} × {CONCRETE_11_LATTICE:g}"
                         f" + {rnd} × {CONCRETE_11_ROUND:g} = {concrete:,.3f} ← مقرَّب لأعلى"))

    # ستي رود — 12 م واير لكل طقم على أعمدة 11م
    if net.stay_rod_sets:
        add(MaterialLine(*M_STAY_SET, net.stay_rod_sets, f"ستي رود على أعمدة 11م"))
        add(MaterialLine(*M_STAY_WIRE, net.stay_rod_sets * STAY_WIRE_PER_SET_11M,
                         f"ستي رود 11م: {net.stay_rod_sets} × {STAY_WIRE_PER_SET_11M} م"))

    return lines


# ──────────────────────────── توليد مواد 33 ك.ف ────────────────────────────


def materials_33kv(net: Network33kV) -> list[MaterialLine]:
    """يولّد أسطر مواد شبكة 33 ك.ف الهوائية."""
    lines: list[MaterialLine] = []
    susp = net.poles_suspension
    anchors = net.anchors_mid + net.anchors_end
    if susp == 0 and anchors == 0 and net.route_length_m <= 0:
        return lines

    add = lines.append
    double = net.circuit is CircuitType.DOUBLE
    poles_total = susp + anchors * 2

    circ = "مزدوجة" if double else "مفردة"

    # السلك
    qty = wire_quantity(
        net.route_length_m, net.circuit, net.length_includes_waste, net.waste_pct
    )
    if qty:
        factor = 1.0 if net.length_includes_waste else 1 + net.waste_pct
        add(MaterialLine(*M_WIRE_33, qty,
                         f"مسار 33 ك.ف: {net.route_length_m:,.0f} × 3 أطوار"
                         f" × {net.circuit.circuits} دائرة × {factor:g} زيادة"))

    # الأعمدة — كل ركيزة عمودان مشبكان 14م
    if susp:
        add(MaterialLine(*M_POLE_14, susp, f"أعمدة تعليق 14م: {susp}"))
    if anchors:
        add(MaterialLine(*M_POLE_14, anchors * 2,
                         f"الركائز: {anchors} ركيزة × 2 عمود"))

    # البراكيت 2م: الحاجة على أعمدة التعليق، والمرفق يُجمع من كل أعمدة 14م ثم يُطرح.
    # هذا يُنتج سلوك «استخدام فائض الركائز على أعمدة التعليق» تلقائياً (ق-١٥).
    per_susp = 3 if double else 1
    need_b2 = susp * per_susp
    included_b2 = poles_total if net.pole_supply.includes_bracket else 0
    b2 = max(0, need_b2 - included_b2)
    if b2:
        detail = f"أعمدة التعليق ({circ}): {susp} × {per_susp} = {need_b2}"
        if included_b2:
            detail += f"، ناقص {included_b2} مرفقاً مع أعمدة 14م"
        add(MaterialLine(*M_BRACKET_2, b2, detail))
    if net.extra_bracket_2:
        add(MaterialLine(*M_BRACKET_2, net.extra_bracket_2, "إضافي يُدخله المستخدم"))

    # البراكيت 2.5م — لكل ركيزة كاملة (عمودين)
    per_anchor = 6 if double else 2
    if anchors:
        add(MaterialLine(*M_BRACKET_25, anchors * per_anchor,
                         f"الركائز ({circ}): {anchors} ركيزة × {per_anchor}"))
    if net.extra_bracket_25:
        add(MaterialLine(*M_BRACKET_25, net.extra_bracket_25, "إضافي يُدخله المستخدم"))

    # العوازل — الدبوسي على أعمدة التعليق والركائز، والقرصي على الركائز فقط
    pin = 6 if double else 3
    if susp:
        add(MaterialLine(*M_PIN_INSULATOR_33, susp * pin,
                         f"أعمدة تعليق 14م ({circ}): {susp} × {pin}"))
    if anchors:
        add(MaterialLine(*M_PIN_INSULATOR_33, anchors * pin,
                         f"الركائز ({circ}): {anchors} ركيزة × {pin}"))
        add(MaterialLine(*M_DISC_INSULATOR_33, anchors * (12 if double else 6),
                         f"الركائز للشد ({circ}): {anchors} × {12 if double else 6}"))
        add(MaterialLine(*M_AL_FITTINGS_33, anchors * (24 if double else 12),
                         f"الركائز ({circ}): {anchors} × {24 if double else 12}"))

    # التأريض
    if poles_total:
        add(MaterialLine(*M_EARTH_WIRE, poles_total * EARTH_WIRE_PER_POLE,
                         f"تأريض أعمدة 14م: {poles_total} عموداً × {EARTH_WIRE_PER_POLE}"))
        add(MaterialLine(*M_EARTH_TERMINAL, poles_total * EARTH_TERMINAL_PER_POLE,
                         f"تأريض أعمدة 14م: {poles_total} عموداً × {EARTH_TERMINAL_PER_POLE}"))

    # الكونكريت — تقريب لأعلى مستقل عن كونكريت 11 ك.ف، كما في الملف الأصلي
    parts = [
        (susp, CONCRETE_14_SUSPENSION[net.circuit], "تعليق"),
        (net.anchors_mid, CONCRETE_14_MID_ANCHOR[net.circuit], "ركيزة وسطية"),
        (net.anchors_end, CONCRETE_14_END_ANCHOR[net.circuit], "ركيزة بداية ونهاية"),
    ]
    concrete = sum(count * coef for count, coef, _ in parts)
    if concrete:
        terms = " + ".join(f"{c} {label} × {k:g}" for c, k, label in parts if c)
        add(MaterialLine(*M_CONCRETE, _roundup(concrete),
                         f"أساسات 33 ك.ف ({circ}): {terms} = {concrete:,.3f} ← مقرَّب لأعلى"))

    # شيش التسليح — لا يتغيّر بنوع الدائرة
    rebar = (
        net.anchors_mid * REBAR_PER_MID_ANCHOR + net.anchors_end * REBAR_PER_END_ANCHOR
    ) / REBAR_DIVISOR
    if rebar:
        add(MaterialLine(*M_REBAR, rebar,
                         f"تسليح أسس الركائز: ({net.anchors_mid} × {REBAR_PER_MID_ANCHOR}"
                         f" + {net.anchors_end} × {REBAR_PER_END_ANCHOR}) ÷ {REBAR_DIVISOR}"))

    # ستي رود — 15 م واير لكل طقم على أعمدة 14م
    if net.stay_rod_sets:
        add(MaterialLine(*M_STAY_SET, net.stay_rod_sets, "ستي رود على أعمدة 14م"))
        add(MaterialLine(*M_STAY_WIRE, net.stay_rod_sets * STAY_WIRE_PER_SET_14M,
                         f"ستي رود 14م: {net.stay_rod_sets} × {STAY_WIRE_PER_SET_14M} م"))

    return lines


# ──────────────────────────────── أجور العمل ────────────────────────────────


def labour_11kv(net: Network11kV, rates: dict) -> list[LabourLine]:
    """أجور 11 ك.ف — لا تتغيّر بنوع الدائرة عدا التسليك (لأن كمية السلك تتضاعف)."""
    out: list[LabourLine] = []
    qty = wire_quantity(
        net.route_length_m, net.circuit, net.length_includes_waste, net.waste_pct
    )
    if qty:
        out.append(
            LabourLine("تسليك شبكة الضغط العالي", "متر سلك", qty,
                       rates["تسليك شبكة الضغط العالي"]["السعر"])
        )
    if net.poles_lattice:
        out.append(
            LabourLine("نصب عمود مشبك 11م", "عمود", net.poles_lattice,
                       rates["نصب عمود مشبك 11م"]["السعر"])
        )
    if net.poles_round:
        out.append(
            LabourLine("نصب عمود مدور 11م", "عمود", net.poles_round,
                       rates["نصب عمود مدور 11م"]["السعر"])
        )
    if net.stay_rod_sets:
        out.append(
            LabourLine("نصب طاقم ستي", "طاقم", net.stay_rod_sets,
                       rates["نصب طاقم ستي"]["السعر"])
        )
    return out


def labour_33kv(net: Network33kV, rates: dict) -> list[LabourLine]:
    """أجور 33 ك.ف — تختلف بنوع الدائرة في نصب الأعمدة والركائز."""
    out: list[LabourLine] = []
    suffix = "السعر_مزدوجة" if net.circuit is CircuitType.DOUBLE else "السعر_مفردة"

    qty = wire_quantity(
        net.route_length_m, net.circuit, net.length_includes_waste, net.waste_pct
    )
    if qty:
        out.append(
            LabourLine("تسليك شبكة 33 ك.ف 210", "متر سلك", qty,
                       rates["تسليك شبكة 33 ك.ف 210"]["السعر"])
        )
    for label, count in (
        ("نصب عمود مشبك 14م", net.poles_suspension),
        ("نصب ركيزة شد وسطية", net.anchors_mid),
        ("نصب ركيزة شد بداية ونهاية", net.anchors_end),
    ):
        if count:
            unit = rates[label]["الوحدة"]
            out.append(LabourLine(label, unit, count, rates[label][suffix]))
    if net.stay_rod_sets:
        out.append(
            LabourLine("نصب طاقم ستي", "طاقم", net.stay_rod_sets,
                       rates["نصب طاقم ستي"]["السعر"])
        )
    return out


# ──────────────────────────────── التجميع ────────────────────────────────


def aggregate(lines: list[MaterialLine]) -> "OrderedDict[tuple[str, str], float]":
    """يجمع أسطر المواد بمفتاح (الاسم + الوحدة) — نفس منطق SUMIFS في الملف الأصلي."""
    out: "OrderedDict[tuple[str, str], float]" = OrderedDict()
    for line in lines:
        key = (line.name, line.unit)
        out[key] = out.get(key, 0.0) + line.qty
    return out


def compute(project: OverheadProject, catalog: dict) -> dict:
    """يحسب المشروع كاملاً ويعيد المواد والأجور والمجاميع."""
    prices = catalog["المواد"]
    rates = catalog["أجور_العمل"]

    from .lowvoltage import labour_lv, materials_lv

    raw = materials_11kv(project.net11) + materials_33kv(project.net33)
    if project.netlv is not None:
        raw += materials_lv(project.netlv)
    totals = aggregate(raw)

    # تفصيل كل مادة: الأسطر التي ساهمت فيها ومعادلة كل سطر — ليتمكّن المدقّق من
    # تتبّع الرقم النهائي إلى مصادره بدل قبوله كما هو.
    breakdown: dict[tuple[str, str], list[MaterialLine]] = {}
    for line in raw:
        breakdown.setdefault((line.name, line.unit), []).append(line)

    materials = []
    materials_cost = 0.0
    for (name, unit), qty in totals.items():
        entry = prices.get(name, {})
        price = entry.get("السعر")
        quantity_only = entry.get("كمية_فقط", False)
        cost = 0.0 if (price is None or quantity_only) else qty * price
        materials_cost += cost
        contributors = breakdown[(name, unit)]
        materials.append(
            {
                "المادة": name,
                "الوحدة": unit,
                "الكمية": qty,
                "سعر الوحدة": price,
                "الكلفة": cost,
                "كمية_فقط": quantity_only,
                "سعر_مفقود": price is None,
                "تفصيل": [{"الكمية": c.qty, "المصدر": c.source} for c in contributors],
                "مجمَّع": len(contributors) > 1,
            }
        )

    labour = labour_11kv(project.net11, rates) + labour_33kv(project.net33, rates)
    if project.netlv is not None:
        labour += labour_lv(project.netlv, rates)
    labour_cost = sum(line.cost for line in labour)

    return {
        "raw": raw,
        "المواد": materials,
        "أجور_العمل": labour,
        "كلفة_المواد": materials_cost,
        "كلفة_العمل": labour_cost,
        "الكلفة_الكلية": materials_cost + labour_cost,
        "أسعار_مفقودة": [m["المادة"] for m in materials if m["سعر_مفقود"]],
        "أجور_مفقودة": [l.name for l in labour if l.rate_missing],
    }
