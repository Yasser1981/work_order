# -*- coding: utf-8 -*-
"""تحويل شبكة 11 ك.ف قائمة من مفردة إلى مزدوجة (ق-٨٣).

بنصّ المستخدم: «هناك شبكة كهربائية 11 ك.ف منصوبة أصلاً، وتكون شبكة مفردة، يراد
تحويلها إلى شبكة مزدوجة».

## المبدأ: **الفرق يُشتقّ ولا يُكتَب**

لا رقم في هذا الملف يقول «براكيتان لكل عمود». بل:

> **المطلوب لكل عمود قائم = حاجته في المزدوجة − حاجته في المفردة**

تُقرأ من جداول `overhead` نفسها التي اعتُمدت في ق-٥ و ق-٢١. فلو تغيّرت قاعدة
براكيت يوماً **تبعها التحويل تلقائياً**، ولم يبقَ رقمان لقاعدة واحدة.

**وقد صدّق المستخدم الفرق المشتقّ**: المدوّر +2 (بمقاسين في النمط القياسي،
ومقاسٍ واحد في البديل)، والمشبك **+4** لا +2 — وهو ما نبّهتُ عليه فأقرّه.

## ثلاثة مصادر للمواد، لكلٍّ قاعدته

| المصدر | القاعدة |
|---|---|
| **الأعمدة القائمة** | الفرق وحده: براكيت وعوازل. لا عمود ولا كونكريت ولا تأريض |
| **الدائرة الجديدة** | المسار × 3 أطوار × دائرة واحدة × معامل الزيادة |
| **أعمدة الإسناد المضافة** | حاجةُ عمودِ شبكةٍ مزدوجةٍ **كاملة** — ولذلك تُولَّد بمولّد الشبكة نفسه |

**ولماذا الأعمدة المضافة بالحاجة الكاملة:** العمود الجديد يحمل الدائرتين معاً،
فليس «تحويلاً» بل عمود شبكة مزدوجة. ويُولَّد باستدعاء `materials_11kv` نفسها
بمسارٍ صفر، فتأتي معه البراكيت والعوازل والكونكريت والتأريض بقواعدها المعتمدة
بلا أن تُكتب هنا ثانية.

## الأجور

- **التسليك** بند قائم مُسعَّر، وكميته أمتار الدائرة الجديدة.
- **نصب الأعمدة المضافة** بند قائم مُسعَّر.
- **تحويل العمود القائم** (تركيب البراكيت والعوازل عليه) — **بلا سعر بعد**،
  بنصّ المستخدم: «اتركه فارغاً حالياً بدون أجور». فيخرج بنداً ظاهراً بلا أجر
  على قاعدة ق-٩: الفراغ يعني «غير مُسعَّر» لا صفراً، فيبقى العمل مرئياً في
  الكشف ويُنبَّه عليه، ومتى أُدخل سعره في نسخة الأسعار امتلأ وحده.

**والسعر يُقرأ بـ`.get` لا بالفهرسة**، فلا ينهار الحساب على نسخة أسعار قديمة
لا تعرف هذين البندين (ق-٨٣).
"""

from __future__ import annotations

from .overhead import (
    CONVERSION_LATTICE_RATE,
    CONVERSION_ROUND_RATE,
    M_BRACKET_12,
    M_BRACKET_14,
    M_AL_FITTINGS_11,
    M_DISC_INSULATOR_11,
    M_PIN_INSULATOR_11,
    M_WIRE_11,
    WIRING_11_LABEL,
    WIRING_11_RATE,
    bracket_need_11,
    materials_11kv,
    labour_11kv,
    wire_quantity,
)
from .types import (
    CircuitType,
    Conversion11kV,
    LabourLine,
    MaterialLine,
    Network11kV,
    PoleType11,
)

PIN_PER_POLE_PER_CIRCUIT = 3
"""عازل دبوسي لكل عمود لكل دائرة — ثلاثة أطوار (مقروء من مولّد الشبكة)."""

DISC_PER_LATTICE_PER_CIRCUIT = 6
"""عازل قرصي ومعدات ربط لكل عمود مشبك لكل دائرة (للشدّ)."""


def bracket_increment(pattern, pole: PoleType11) -> dict[str, int]:
    """الفرق في البراكيت لعمود قائم واحد: المزدوجة ناقص المفردة.

    **لا يُكتب الفرق رقماً** بل يُطرح من الجدولين، فيبقى تابعاً لهما أبداً.
    """
    single = bracket_need_11(CircuitType.SINGLE, pattern, pole)
    double = bracket_need_11(CircuitType.DOUBLE, pattern, pole)
    increment = {size: double.get(size, 0) - single.get(size, 0)
                 for size in set(single) | set(double)}
    return {size: count for size, count in increment.items() if count > 0}


def _added_network(net: Conversion11kV) -> Network11kV:
    """أعمدة الإسناد المضافة **كشبكة مزدوجة بمسار صفر**.

    الحيلة مقصودة: المسار صفرٌ فلا سلك ولا تكرار لحساب الدائرة الجديدة، والدائرة
    مزدوجة فتأتي الأعمدة بحاجتها الكاملة من مولّد الشبكة المعتمد نفسه.
    """
    return Network11kV(
        route_length_m=0,
        circuit=CircuitType.DOUBLE,
        poles_lattice=net.added_lattice,
        poles_round=net.added_round,
        lattice_supply=net.added_lattice_supply,
        round_supply=net.added_round_supply,
        bracket_pattern=net.bracket_pattern,
        stay_rod_sets=net.stay_rod_sets,
    )


def materials_conversion_11(net: Conversion11kV) -> list[MaterialLine]:
    """مواد التحويل: فرقُ الأعمدة القائمة + سلك الدائرة الجديدة + الأعمدة المضافة."""
    lines: list[MaterialLine] = []

    # ١. سلك الدائرة الجديدة — دائرة واحدة على طول المسار
    qty = wire_quantity(net.route_length_m, CircuitType.SINGLE,
                        net.length_includes_waste, net.waste_pct)
    if qty:
        factor = 1.0 if net.length_includes_waste else 1 + net.waste_pct
        lines.append(MaterialLine(
            *M_WIRE_11, qty,
            f"الدائرة الجديدة: {net.route_length_m:,.0f} م × 3 أطوار × "
            f"{factor:g} زيادة"))

    # ٢. فرق البراكيت على الأعمدة القائمة
    sizes = {"1.2": M_BRACKET_12, "1.4": M_BRACKET_14}
    for pole, count, label in (
        (PoleType11.LATTICE, net.existing_lattice, "أعمدة مشبكة قائمة"),
        (PoleType11.ROUND, net.existing_round, "أعمدة مدوّرة قائمة"),
    ):
        if not count:
            continue
        for size, per_pole in bracket_increment(net.bracket_pattern, pole).items():
            lines.append(MaterialLine(
                *sizes[size], per_pole * count,
                f"{label}: {count} × {per_pole} (فرق المزدوجة عن المفردة)"))

    # ٣. فرق العوازل على الأعمدة القائمة — دائرة واحدة إضافية
    existing = net.existing_lattice + net.existing_round
    if existing:
        lines.append(MaterialLine(
            *M_PIN_INSULATOR_11, existing * PIN_PER_POLE_PER_CIRCUIT,
            f"أعمدة قائمة: {existing} × {PIN_PER_POLE_PER_CIRCUIT} (دائرة إضافية)"))
    if net.existing_lattice:
        for material in (M_DISC_INSULATOR_11, M_AL_FITTINGS_11):
            lines.append(MaterialLine(
                *material, net.existing_lattice * DISC_PER_LATTICE_PER_CIRCUIT,
                f"أعمدة مشبكة قائمة: {net.existing_lattice} × "
                f"{DISC_PER_LATTICE_PER_CIRCUIT} (دائرة إضافية)"))

    # ٤. أعمدة الإسناد المضافة — بحاجة عمود الشبكة المزدوجة كاملة
    lines += materials_11kv(_added_network(net))
    return lines


def labour_conversion_11(net: Conversion11kV, rates: dict) -> list[LabourLine]:
    """أجور التحويل: التسليك، ونصب المضاف، وتحويل الأعمدة القائمة (بلا سعر بعد)."""
    out: list[LabourLine] = []

    qty = wire_quantity(net.route_length_m, CircuitType.SINGLE,
                        net.length_includes_waste, net.waste_pct)
    if qty:
        entry = rates[WIRING_11_RATE]
        out.append(LabourLine(WIRING_11_LABEL, entry["الوحدة"], qty, entry["السعر"],
                              source="تسليك الدائرة الجديدة", driver=M_WIRE_11))

    # تحويل الأعمدة القائمة: بندان — العمل يختلف كثيراً بين النوعين
    # (المشبك 4 براكيت و6 عوازل قرصية، والمدوّر 2 براكيت)
    for name, count, label in (
        (CONVERSION_LATTICE_RATE, net.existing_lattice, "عمود مشبك قائم"),
        (CONVERSION_ROUND_RATE, net.existing_round, "عمود مدوّر قائم"),
    ):
        if not count:
            continue
        entry = rates.get(name) or {}
        out.append(LabourLine(name, entry.get("الوحدة", "عدد"), count,
                              entry.get("السعر"), source=f"{label}: {count}"))

    out += labour_11kv(_added_network(net), rates)
    return out
