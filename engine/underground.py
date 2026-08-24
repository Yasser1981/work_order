# -*- coding: utf-8 -*-
"""محرك حساب شبكة القابلوات الأرضية — 11 ك.ف (ق-٣٠) و33 ك.ف (ق-٣١).

**الفرق الجوهري بين الجهدين:** قابلو 11 ك.ف ثلاثي القلب — كابل واحد يحمل
الأطوار الثلاثة، فـ«عدد المغذيات» = عدد الكابلات مباشرة. وقابلو 33 ك.ف أحادي
القلب — كل مغذٍّ (دائرة) يحتاج **ثلاثة كابلات منفصلة**، طور لكل كابل. لذلك
33 ك.ف يُدخَل بـ`circuit` (مفردة/مزدوجة) لا بعدد مغذيات مباشر، ويُشتقّ عدد
الكابلات الفعلي داخلياً (×3).

القاعدة الحاكمة، بتأكيد المستخدم صراحةً:

**طول المسار وحده** يحدّد الأعمال المدنية (حفر الخندق وإعادة المسار) وموادّ
الخندق — خندق واحد بصرف النظر عن عدد المغذيات المارّة فيه.

**طول المسار × عدد المغذيات** يحدّد كمية القابلو نفسه وأجر مدّه — كل مغذٍّ
يحتاج طوله الكامل من القابلو.

**الصندوق المستقيم يُحسب لكل مغذٍّ على حدة** لا من إجمالي كمية القابلو، لأنه
يصل طرفَي نفس القابلو لا بين مغذيات مختلفة. هذا **الرقم الصحيح فعلياً** لا تقريباً
أضمن: كل مغذٍّ كابل مستقل يحتاج `⌈طوله ÷ طول البكرة⌉ − 1` صندوقاً بمعزل عن غيره،
فمجموع المغذيات هو المجموع الحقيقي لا حدّاً أعلى له. (تنبيه: هذا المجموع قد يقع
**فوق أو تحت** ما يُنتجه حساب «الكمية المجمَّعة» الذي يستخدمه الملف الأصلي حين
يقترح B16 — لكن حساب الملف الأصلي هو غير الصحيح أصلاً، لأنه يخلط أطوال مغذيات
مستقلة في معادلة واحدة كأنها كابل متّصل. المقارنة بين الاثنين ليست معياراً؛
الصحّة الفيزيائية للمغذٍّ المستقل هي المعيار.)

**عبور الشوارع رقم إجمالي للمشروع كله لا لكل مقطع** — يُحسب في `compute_project`
مباشرة من حقلي `Project`، لا من هذا الملف.

المرجع: ق-٣٠ في docs/سجل_القرارات.md
"""

from __future__ import annotations

import math

from .overhead import _roundup
from .types import (
    CircuitType,
    LabourLine,
    MaterialLine,
    SidewalkType,
    Underground11kV,
    Underground33kV,
)

# ─────────────────────────────── أسماء المواد ───────────────────────────────
# تطابق الملف الأصلي حرفياً

M_CABLE_11 = ("قابلو 3×150 ملم² جهد 11 ك.ف", "متر")
M_BOX_STRAIGHT_11 = ("صندوق مستقيم 3×150 ملم² جهد 11 ك.ف", "عدد")
M_BOX_END_INTERNAL_11 = ("صندوق نهاية داخلي 3×150 ملم² جهد 11 ك.ف", "عدد")
M_BOX_END_EXTERNAL_11 = ("صندوق نهاية خارجي 3×150 ملم² جهد 11 ك.ف", "عدد")
M_STAKER = ("شتايكر 50×50×5 سم", "عدد")
M_RIVER_SAND = ("رمل نهري", "متر مكعب")
M_WARNING_TAPE = ("شريط تحذير", "لفة")

QUANTITY_ONLY = {M_STAKER[0], M_RIVER_SAND[0], M_WARNING_TAPE[0]}
"""موادّ الخندق: كمية بلا كلفة — كلفتها ضمن أجر التنفيذ (بتأكيد المستخدم، ق-٣٠)."""

STAKER_DIVISOR_M = 0.5
"""شتايكر كل نصف متر من طول المسار. تفصيل الخندق العريض (أكثر من 3 مغذيات
يحتاج شتايكرتين متجاورتين) مؤجَّل بطلب المستخدم — انظر قائمة التذكير."""

SAND_LENGTH_FACTOR = 0.6
SAND_WIDTH_FACTOR = 0.4
"""رمل نهري (م³) = طول المسار × 0.6 × 0.4. قد تتغيّر للخنادق العريضة — مؤجَّل."""

WARNING_TAPE_ROLL_M = 90
"""طول لفة شريط التحذير الواحدة (م)."""

DRUM_LENGTH_DEFAULT_KEY = "طول_بكرة_القابلو_11ك.ف"


def resolve_drum_length(net: Underground11kV, catalog: dict) -> float:
    """طول بكرة القابلو — من المُدخل إن وُجد، وإلا من الافتراضيات (ق-٢٠)."""
    if net.drum_length_m is not None:
        return net.drum_length_m
    return catalog["المسافات_الافتراضية"][DRUM_LENGTH_DEFAULT_KEY]


def cable_quantity(net: Underground11kV) -> float:
    """كمية القابلو = طول المسار × عدد المغذيات × عامل الزيادة."""
    if net.route_length_m <= 0:
        return 0
    waste = 1.0 if net.length_includes_waste else 1.0 + net.waste_pct
    return _roundup(net.route_length_m * net.feeder_count * waste)


def suggest_straight_boxes(route_length_m: float, feeder_count: int, drum_length_m: float) -> int:
    """صندوق مستقيم لكل مغذٍّ على حدة — الحساب الصحيح فيزيائياً، لا تقريباً (ق-٣٠).

    كل مغذٍّ كابل مستقل بطوله الكامل يحتاج ⌈الطول ÷ طول البكرة⌉ − 1 صندوقاً
    بمعزل عن بقية المغذيات، فإن جاء أقصر من بكرة واحدة فلا صندوق له إطلاقاً.
    المجموع النهائي هو مجموع هذه الاحتياجات المستقلة — لا مجموعاً مُقرَّباً مرّة
    واحدة على الكمية الكلية كما يفعل الملف الأصلي.
    """
    if route_length_m <= 0 or feeder_count <= 0 or drum_length_m <= 0:
        return 0
    per_feeder = max(0, math.ceil(round(route_length_m / drum_length_m, 9)) - 1)
    return feeder_count * per_feeder


def _civil_tariff_lookup(sidewalk_type: SidewalkType, count: int, catalog: dict) -> float | None:
    """تعرفة الأعمال المدنية للمتر — بحسب نوع الرصيف وعدد الوحدات معاً.

    `None` إن كان العدد خارج الجدول (أكثر من 5) — يُبلَّغ عنه بدل أن يُخمَّن رقم
    قد يكون خاطئاً في الاتجاهين. مشتركة بين 11 و33 ك.ف — الجدول واحد (ق-٣١).
    """
    tariff = catalog["تعرفة_الأعمال_المدنية"]
    return tariff.get(sidewalk_type.value, {}).get(str(count))


def civil_works_rate(net: Underground11kV, catalog: dict) -> float | None:
    """تعرفة الأعمال المدنية لمقطع 11 ك.ف — بعدد المغذيات (= عدد الكابلات)."""
    return _civil_tariff_lookup(net.sidewalk_type, net.feeder_count, catalog)


def civil_works_rate_33(net: Underground33kV, catalog: dict) -> float | None:
    """تعرفة الأعمال المدنية لمقطع 33 ك.ف — بعدد **الدوائر** لا عدد الكابلات.

    المغذي الواحد (بكابلاته الثلاثة معاً في خندق واحد) يُعامَل معاملة مغذٍّ واحد
    مماثل لـ11 ك.ف — بتأكيد المستخدم صراحةً (ق-٣١). نفس الجدول بالضبط.
    """
    return _civil_tariff_lookup(net.sidewalk_type, net.circuit.circuits, catalog)


def materials_underground11(net: Underground11kV) -> list[MaterialLine]:
    """يولّد أسطر مواد مقطع الشبكة الأرضية 11 ك.ف."""
    lines: list[MaterialLine] = []
    add = lines.append

    qty = cable_quantity(net)
    if qty:
        waste = 1.0 if net.length_includes_waste else 1.0 + net.waste_pct
        add(
            MaterialLine(
                *M_CABLE_11,
                qty,
                f"قابلو 11 ك.ف: {net.route_length_m:,.0f} × {net.feeder_count} مغذٍّ"
                f" × {waste:g} زيادة",
            )
        )

    if net.straight_boxes:
        add(
            MaterialLine(
                *M_BOX_STRAIGHT_11,
                net.straight_boxes,
                f"صناديق مستقيمة: {net.straight_boxes}",
            )
        )
    if net.end_boxes_internal:
        add(
            MaterialLine(
                *M_BOX_END_INTERNAL_11,
                net.end_boxes_internal,
                f"صناديق نهاية داخلية: {net.end_boxes_internal}",
            )
        )
    if net.end_boxes_external:
        add(
            MaterialLine(
                *M_BOX_END_EXTERNAL_11,
                net.end_boxes_external,
                f"صناديق نهاية خارجية: {net.end_boxes_external}",
            )
        )

    if net.route_length_m > 0:
        staker = _roundup(net.route_length_m / STAKER_DIVISOR_M)
        add(
            MaterialLine(
                *M_STAKER,
                staker,
                f"خندق بطول {net.route_length_m:,.0f} م ÷ {STAKER_DIVISOR_M:g} م",
            )
        )
        sand = _roundup(net.route_length_m * SAND_LENGTH_FACTOR * SAND_WIDTH_FACTOR)
        add(
            MaterialLine(
                *M_RIVER_SAND,
                sand,
                f"خندق بطول {net.route_length_m:,.0f} م × {SAND_LENGTH_FACTOR:g}"
                f" × {SAND_WIDTH_FACTOR:g}",
            )
        )
        tape = _roundup(net.route_length_m / WARNING_TAPE_ROLL_M)
        add(
            MaterialLine(
                *M_WARNING_TAPE,
                tape,
                f"خندق بطول {net.route_length_m:,.0f} م ÷ {WARNING_TAPE_ROLL_M} م",
            )
        )

    return lines


def labour_underground11(net: Underground11kV, catalog: dict) -> list[LabourLine]:
    """أجور مقطع الشبكة الأرضية 11 ك.ف."""
    rates = catalog["أجور_العمل"]
    out: list[LabourLine] = []

    qty = cable_quantity(net)
    if qty:
        entry = rates["كلفة مد قابلو 3×150 ملم²"]
        out.append(LabourLine("كلفة مد قابلو 3×150 ملم²", entry["الوحدة"], qty, entry["السعر"]))

    if net.straight_boxes:
        entry = rates["كلفة نصب صندوق مستقيم 3×150 ملم²"]
        out.append(
            LabourLine(
                "كلفة نصب صندوق مستقيم 3×150 ملم²", entry["الوحدة"], net.straight_boxes, entry["السعر"]
            )
        )

    end_total = net.end_boxes_internal + net.end_boxes_external
    if end_total:
        entry = rates["كلفة نصب صندوق نهاية 3×150 ملم²"]
        out.append(
            LabourLine("كلفة نصب صندوق نهاية 3×150 ملم²", entry["الوحدة"], end_total, entry["السعر"])
        )

    if net.route_length_m > 0:
        rate = civil_works_rate(net, catalog)
        label = f"الأعمال المدنية — رصيف {net.sidewalk_type.value} × {net.feeder_count} مغذٍّ"
        out.append(LabourLine(label, "متر", net.route_length_m, rate))

    return out


# ═══════════════════════════ 33 ك.ف — قابلو 1×400 ملم² (ق-٣١) ═══════════════════════════

M_CABLE_33 = ("قابلو 1×400 ملم² جهد 33 ك.ف", "متر")
M_BOX_STRAIGHT_33 = ("صندوق مستقيم 1×400 ملم² جهد 33 ك.ف", "عدد")
M_BOX_END_INTERNAL_33 = ("صندوق نهاية داخلي 1×400 ملم² جهد 33 ك.ف", "عدد")
M_BOX_END_EXTERNAL_33 = ("صندوق نهاية خارجي 1×400 ملم² جهد 33 ك.ف", "عدد")

PHASES_PER_CIRCUIT_33 = 3
"""قابلو 33 ك.ف أحادي القلب — كل دائرة (مغذٍّ) تحتاج ثلاثة كابلات منفصلة، طور
لكل كابل. لا نظير لهذا في 11 ك.ف حيث الكابل الواحد ثلاثي القلب يحمل الأطوار
الثلاثة معاً."""

BOXES_PER_END_SET_33 = PHASES_PER_CIRCUIT_33
"""صناديق النهاية 33 ك.ف: السيت الواحد **ثلاثة صناديق**، صندوق لكل طور (ق-٣٥).

المستخدم يُدخل عدد **نقاط النهاية** (السيتات)، والمحرك يضربها ×3 فتصير الكمية
بوحدة «عدد» مطابقةً للسعر المثبت وهو **سعر الصندوق الواحد** لا سعر السيت.
لا نظير لهذا في 11 ك.ف — كابله ثلاثي القلب فنهايته صندوق واحد."""

DRUM_LENGTH_DEFAULT_KEY_33 = "طول_بكرة_القابلو_33ك.ف"


def resolve_drum_length_33(net: Underground33kV, catalog: dict) -> float:
    """طول بكرة القابلو لـ33 ك.ف — من المُدخل إن وُجد، وإلا من الافتراضيات."""
    if net.drum_length_m is not None:
        return net.drum_length_m
    return catalog["المسافات_الافتراضية"][DRUM_LENGTH_DEFAULT_KEY_33]


def cable_count_33(net: Underground33kV) -> int:
    """عدد الكابلات الفعلي: الدوائر × 3 أطوار. مفردة=3، مزدوجة=6."""
    return net.circuit.circuits * PHASES_PER_CIRCUIT_33


def cable_quantity_33(net: Underground33kV) -> float:
    """كمية القابلو = طول المسار × عدد الكابلات (الدوائر×3) × عامل الزيادة.

    مثال المستخدم المتحقَّق منه: 500م مزدوجة الدائرة ← 500×6×1.1 = 3300 م.
    """
    if net.route_length_m <= 0:
        return 0
    waste = 1.0 if net.length_includes_waste else 1.0 + net.waste_pct
    return _roundup(net.route_length_m * cable_count_33(net) * waste)


def materials_underground33(net: Underground33kV) -> list[MaterialLine]:
    """يولّد أسطر مواد مقطع الشبكة الأرضية 33 ك.ف."""
    lines: list[MaterialLine] = []
    add = lines.append

    qty = cable_quantity_33(net)
    if qty:
        waste = 1.0 if net.length_includes_waste else 1.0 + net.waste_pct
        cables = cable_count_33(net)
        add(
            MaterialLine(
                *M_CABLE_33,
                qty,
                f"قابلو 33 ك.ف: {net.route_length_m:,.0f} × {cables} كابل"
                f" ({net.circuit.value}) × {waste:g} زيادة",
            )
        )

    if net.straight_boxes:
        add(
            MaterialLine(
                *M_BOX_STRAIGHT_33,
                net.straight_boxes,
                f"صناديق مستقيمة: {net.straight_boxes}",
            )
        )
    # السيت الواحد ثلاثة صناديق — صندوق لكل طور (ق-٣٥)
    if net.end_boxes_internal:
        add(
            MaterialLine(
                *M_BOX_END_INTERNAL_33,
                net.end_boxes_internal * BOXES_PER_END_SET_33,
                f"نهايات داخلية: {net.end_boxes_internal} سيت"
                f" × {BOXES_PER_END_SET_33} صناديق (طور لكل صندوق)",
            )
        )
    if net.end_boxes_external:
        add(
            MaterialLine(
                *M_BOX_END_EXTERNAL_33,
                net.end_boxes_external * BOXES_PER_END_SET_33,
                f"نهايات خارجية: {net.end_boxes_external} سيت"
                f" × {BOXES_PER_END_SET_33} صناديق (طور لكل صندوق)",
            )
        )

    if net.route_length_m > 0:
        staker = _roundup(net.route_length_m / STAKER_DIVISOR_M)
        add(
            MaterialLine(
                *M_STAKER,
                staker,
                f"خندق بطول {net.route_length_m:,.0f} م ÷ {STAKER_DIVISOR_M:g} م",
            )
        )
        sand = _roundup(net.route_length_m * SAND_LENGTH_FACTOR * SAND_WIDTH_FACTOR)
        add(
            MaterialLine(
                *M_RIVER_SAND,
                sand,
                f"خندق بطول {net.route_length_m:,.0f} م × {SAND_LENGTH_FACTOR:g}"
                f" × {SAND_WIDTH_FACTOR:g}",
            )
        )
        tape = _roundup(net.route_length_m / WARNING_TAPE_ROLL_M)
        add(
            MaterialLine(
                *M_WARNING_TAPE,
                tape,
                f"خندق بطول {net.route_length_m:,.0f} م ÷ {WARNING_TAPE_ROLL_M} م",
            )
        )

    return lines


def labour_underground33(net: Underground33kV, catalog: dict) -> list[LabourLine]:
    """أجور مقطع الشبكة الأرضية 33 ك.ف."""
    rates = catalog["أجور_العمل"]
    out: list[LabourLine] = []

    qty = cable_quantity_33(net)
    if qty:
        entry = rates["كلفة مد قابلو 1×400 ملم²"]
        out.append(LabourLine("كلفة مد قابلو 1×400 ملم²", entry["الوحدة"], qty, entry["السعر"]))

    if net.straight_boxes:
        entry = rates["كلفة نصب صندوق مستقيم 1×400 ملم²"]
        out.append(
            LabourLine(
                "كلفة نصب صندوق مستقيم 1×400 ملم²", entry["الوحدة"], net.straight_boxes, entry["السعر"]
            )
        )

    end_total = net.end_boxes_internal + net.end_boxes_external
    if end_total:
        entry = rates["كلفة نصب صندوق نهاية 1×400 ملم²"]
        out.append(
            LabourLine("كلفة نصب صندوق نهاية 1×400 ملم²", entry["الوحدة"], end_total, entry["السعر"])
        )

    if net.route_length_m > 0:
        rate = civil_works_rate_33(net, catalog)
        label = f"الأعمال المدنية — رصيف {net.sidewalk_type.value} × {net.circuit.value}"
        out.append(LabourLine(label, "متر", net.route_length_m, rate))

    return out
