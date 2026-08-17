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

SPAN_11KV = 25
"""المسافة بين أعمدة 11 ك.ف (م)."""

LATTICE_EVERY = 5
"""كل خامس عمود مشبك في شبكة 11 ك.ف."""

SPAN_33KV = 65
"""المسافة بين أعمدة التعليق 14م (م)."""

ANCHOR_SPAN_33KV = 650
"""المسافة بين الركائز الوسطية (م)."""

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


def count_poles_11kv(route_length_m: float, span: int = SPAN_11KV) -> PoleCount11:
    """يقترح عدد أعمدة 11 ك.ف ونوعها (ق-١٤).

    عمود كل 25 م، وكل خامس عمود مشبك، وطرفا الخط مشبكان إلزاماً. فإن لم يقع العمود
    الأخير على موقع مشبك حُوِّل من مدور إلى مشبك.
    """
    if route_length_m <= 0:
        return PoleCount11(total=0, lattice=0, round_=0, end_converted=False)

    total = _roundup(route_length_m / span) + 1
    positions = set(range(1, total + 1, LATTICE_EVERY))  # 1، 6، 11، …
    end_converted = total not in positions
    positions.add(total)  # طرف الخط مشبك إلزاماً

    lattice = len(positions)
    return PoleCount11(
        total=total,
        lattice=lattice,
        round_=total - lattice,
        end_converted=end_converted,
    )


def count_poles_33kv(
    route_length_m: float,
    span: int = SPAN_33KV,
    anchor_span: int = ANCHOR_SPAN_33KV,
    end_anchors: int = 2,
) -> PoleCount33:
    """يقترح أعمدة وركائز 33 ك.ف (ق-١٤).

    موقع الركيزة يستهلك موقع عمود تعليق فيُخصم من عددها. و`end_anchors` تكون 1 في
    حالة إكمال خط قائم له ركيزة نهاية أصلاً.
    """
    if route_length_m <= 0:
        return PoleCount33(positions=0, suspension=0, mid_anchors=0, end_anchors=0)

    positions = _roundup(route_length_m / span) + 1
    mid_anchors = max(0, _roundup(route_length_m / anchor_span) - 1)
    suspension = max(0, positions - mid_anchors - end_anchors)
    return PoleCount33(
        positions=positions,
        suspension=suspension,
        mid_anchors=mid_anchors,
        end_anchors=end_anchors,
    )


# ──────────────────────────────── كمية السلك ────────────────────────────────


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
    (CircuitType.DOUBLE, BracketPattern.STANDARD, PoleType11.LATTICE): {"1.2": 4, "1.4": 2},
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
        add(MaterialLine(*M_WIRE_11, qty, "مسار 11 ك.ف"))

    # الأعمدة
    if lat:
        add(MaterialLine(*M_POLE_11_LATTICE, lat, "أعمدة 11 ك.ف"))
    if rnd:
        add(MaterialLine(*M_POLE_11_ROUND, rnd, "أعمدة 11 ك.ف"))

    # العوازل — القرصي للشد فيُنصب على المشبك فقط، والدبوسي على كل الأعمدة
    if poles:
        add(MaterialLine(*M_PIN_INSULATOR_11, poles * 3 * n, "أعمدة 11 ك.ف"))
    if lat:
        add(MaterialLine(*M_DISC_INSULATOR_11, lat * 6 * n, "أعمدة 11م مشبك"))
        add(MaterialLine(*M_AL_FITTINGS_11, lat * 6 * n, "أعمدة 11م مشبك"))

    # البراكيت
    b12 = b14 = 0
    for pole_type, count, supply in (
        (PoleType11.LATTICE, lat, net.lattice_supply),
        (PoleType11.ROUND, rnd, net.round_supply),
    ):
        if not count:
            continue
        per_pole = bracket_purchase_11(net.circuit, net.bracket_pattern, pole_type, supply)
        b12 += per_pole.get("1.2", 0) * count
        b14 += per_pole.get("1.4", 0) * count

    b12 += net.extra_bracket_12
    b14 += net.extra_bracket_14
    if b12:
        add(MaterialLine(*M_BRACKET_12, b12, "براكيت أعمدة 11م"))
    if b14:
        add(MaterialLine(*M_BRACKET_14, b14, "براكيت أعمدة 11م"))

    # التأريض — لا يتغيّر بنوع الدائرة
    if poles:
        add(MaterialLine(*M_EARTH_WIRE, poles * EARTH_WIRE_PER_POLE, "تأريض أعمدة 11م"))
        add(MaterialLine(*M_EARTH_TERMINAL, poles * EARTH_TERMINAL_PER_POLE, "تأريض أعمدة 11م"))

    # الكونكريت — يُقرَّب لأعلى على مستوى الجهد، كما في الملف الأصلي
    concrete = lat * CONCRETE_11_LATTICE + rnd * CONCRETE_11_ROUND
    if concrete:
        add(MaterialLine(*M_CONCRETE, _roundup(concrete), "أساسات أعمدة 11م"))

    # ستي رود — 12 م واير لكل طقم على أعمدة 11م
    if net.stay_rod_sets:
        add(MaterialLine(*M_STAY_SET, net.stay_rod_sets, "ستي رود 11م"))
        add(
            MaterialLine(
                *M_STAY_WIRE, net.stay_rod_sets * STAY_WIRE_PER_SET_11M, "ستي رود 11م"
            )
        )

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

    # السلك
    qty = wire_quantity(
        net.route_length_m, net.circuit, net.length_includes_waste, net.waste_pct
    )
    if qty:
        add(MaterialLine(*M_WIRE_33, qty, "مسار 33 ك.ف"))

    # الأعمدة — كل ركيزة عمودان مشبكان 14م
    if poles_total:
        add(MaterialLine(*M_POLE_14, poles_total, "أعمدة وركائز 33 ك.ف"))

    # البراكيت 2م: الحاجة على أعمدة التعليق، والمرفق يُجمع من كل أعمدة 14م ثم يُطرح.
    # هذا يُنتج سلوك «استخدام فائض الركائز على أعمدة التعليق» تلقائياً (ق-١٥).
    need_b2 = susp * (3 if double else 1)
    included_b2 = poles_total if net.pole_supply.includes_bracket else 0
    b2 = max(0, need_b2 - included_b2) + net.extra_bracket_2
    if b2:
        add(MaterialLine(*M_BRACKET_2, b2, "براكيت أعمدة التعليق 14م"))

    # البراكيت 2.5م — لكل ركيزة كاملة (عمودين)
    b25 = anchors * (6 if double else 2) + net.extra_bracket_25
    if b25:
        add(MaterialLine(*M_BRACKET_25, b25, "براكيت الركائز"))

    # العوازل — الدبوسي على أعمدة التعليق والركائز، والقرصي على الركائز فقط
    if susp or anchors:
        add(
            MaterialLine(
                *M_PIN_INSULATOR_33,
                (susp + anchors) * (6 if double else 3),
                "أعمدة وركائز 33 ك.ف",
            )
        )
    if anchors:
        add(MaterialLine(*M_DISC_INSULATOR_33, anchors * (12 if double else 6), "الركائز"))
        add(MaterialLine(*M_AL_FITTINGS_33, anchors * (24 if double else 12), "الركائز"))

    # التأريض
    if poles_total:
        add(MaterialLine(*M_EARTH_WIRE, poles_total * EARTH_WIRE_PER_POLE, "تأريض أعمدة 14م"))
        add(
            MaterialLine(
                *M_EARTH_TERMINAL, poles_total * EARTH_TERMINAL_PER_POLE, "تأريض أعمدة 14م"
            )
        )

    # الكونكريت — تقريب لأعلى مستقل عن كونكريت 11 ك.ف، كما في الملف الأصلي
    concrete = (
        susp * CONCRETE_14_SUSPENSION[net.circuit]
        + net.anchors_mid * CONCRETE_14_MID_ANCHOR[net.circuit]
        + net.anchors_end * CONCRETE_14_END_ANCHOR[net.circuit]
    )
    if concrete:
        add(MaterialLine(*M_CONCRETE, _roundup(concrete), "أساسات أعمدة 33 ك.ف"))

    # شيش التسليح — لا يتغيّر بنوع الدائرة
    rebar = (
        net.anchors_mid * REBAR_PER_MID_ANCHOR + net.anchors_end * REBAR_PER_END_ANCHOR
    ) / REBAR_DIVISOR
    if rebar:
        add(MaterialLine(*M_REBAR, rebar, "تسليح أسس الركائز"))

    # ستي رود — 15 م واير لكل طقم على أعمدة 14م
    if net.stay_rod_sets:
        add(MaterialLine(*M_STAY_SET, net.stay_rod_sets, "ستي رود 14م"))
        add(
            MaterialLine(
                *M_STAY_WIRE, net.stay_rod_sets * STAY_WIRE_PER_SET_14M, "ستي رود 14م"
            )
        )

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

    raw = materials_11kv(project.net11) + materials_33kv(project.net33)
    totals = aggregate(raw)

    materials = []
    materials_cost = 0.0
    for (name, unit), qty in totals.items():
        entry = prices.get(name, {})
        price = entry.get("السعر")
        quantity_only = entry.get("كمية_فقط", False)
        cost = 0.0 if (price is None or quantity_only) else qty * price
        materials_cost += cost
        materials.append(
            {
                "المادة": name,
                "الوحدة": unit,
                "الكمية": qty,
                "سعر الوحدة": price,
                "الكلفة": cost,
                "كمية_فقط": quantity_only,
                "سعر_مفقود": price is None,
            }
        )

    labour = labour_11kv(project.net11, rates) + labour_33kv(project.net33, rates)
    labour_cost = sum(line.cost for line in labour)

    return {
        "raw": raw,
        "المواد": materials,
        "أجور_العمل": labour,
        "كلفة_المواد": materials_cost,
        "كلفة_العمل": labour_cost,
        "الكلفة_الكلية": materials_cost + labour_cost,
        "أسعار_مفقودة": [m["المادة"] for m in materials if m["سعر_مفقود"]],
    }
