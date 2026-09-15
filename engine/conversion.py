# -*- coding: utf-8 -*-
"""تحويل شبكة 11 ك.ف قائمة من مفردة إلى مزدوجة (ق-٨٣، وعُدّل بـق-٨٤).

بنصّ المستخدم: «هناك شبكة كهربائية 11 ك.ف منصوبة أصلاً، وتكون شبكة مفردة، يراد
تحويلها إلى شبكة مزدوجة».

## المبدأ: **الفرق يُشتقّ ولا يُكتَب**

لا رقم في هذا الملف يقول «براكيتان لكل عمود» ولا «ثلاثة عوازل». بل:

> **ما يزيده العمود القائم = مولّد الشبكة المزدوجة − مولّد الشبكة المفردة**

يُطرح `materials_11kv` من نفسه بعمودٍ واحد ومسارٍ صفر. فلو تغيّرت قاعدة براكيت
أو عازل يوماً **تبعها التحويل تلقائياً**، ولم يبقَ رقمان لقاعدة واحدة يفترقان.

**وثمرةٌ ثانية للطرح:** ما لا يتغيّر بتغيّر الدائرة — العمود نفسه، والكونكريت،
والتأريض، والستي رود — **فرقُه صفرٌ فيسقط من تلقائه**. فامتناعُ الكونكريت عن
عمودٍ قائمٍ ليس سطراً نسيَه أحدٌ أو تذكّره، بل نتيجةُ الطرح.

**وقد صدّق المستخدم الفرق المشتقّ**: المدوّر +2 براكيت (بمقاسين في النمط
القياسي، ومقاسٍ واحد في البديل)، والمشبك **+4** لا +2 — وهو ما نبّهتُ عليه
فأقرّه.

## الاستثناء الوحيد: احتياط التاج (ق-٨٤)

رقمان **مكتوبان** هنا لأنهما لا يُشتقّان من جدول: العازل القائم على رأس العمود
(**التاج**) يُنقل مكانه عند التحويل، وبنصّ المستخدم «قد يُهمل أو يتلف عند تغيير
مكانه». فهي **بدلُ تالفٍ لا حاجةُ دائرةٍ جديدة** — واقعُ ميدانٍ لا قاعدةُ تصميم،
ولذلك لا يعرفه المولّد ولا يُطلب منه أن يعرفه.

فيُكتب باسمه وسببه ومقداره في مكان واحد: `CROWN_SPARE`.

## ثلاثة مصادر للمواد، لكلٍّ قاعدته

| المصدر | القاعدة |
|---|---|
| **الأعمدة القائمة** | الفرق وحده + احتياط التاج |
| **الدائرة الجديدة** | المسار × 3 أطوار × دائرة واحدة × معامل الزيادة |
| **أعمدة الإسناد المضافة** | حاجةُ عمودِ شبكةٍ مزدوجةٍ **كاملة** |

**ولماذا الأعمدة المضافة بالحاجة الكاملة:** العمود الجديد يحمل الدائرتين معاً،
فليس «تحويلاً» بل عمود شبكة مزدوجة. ويُولَّد باستدعاء `materials_11kv` نفسها
بمسارٍ صفر، فتأتي معه البراكيت والعوازل والكونكريت والتأريض بقواعدها المعتمدة
بلا أن تُكتب هنا ثانية. **ولا احتياط تاجٍ له**: عوازله كلها جديدة.

## الأجور: التسليك ونصب المضاف — ولا شيء غيرهما (ق-٨٤)

بنصّ المستخدم: «أجر التحويل بدون أجور، عدا أجور المواد طبعاً. بالنسبة للعمل،
يؤخذ أجر التسليك فقط، وبالتأكيد أجر الأعمدة الإضافية».

فـ**تركيب البراكيت والعوازل على العمود القائم لا أجر له أصلاً** — لا «أجرٌ
ينتظر تسعيراً». وهذا يُبطل ما كان في ق-٨٣ من إخراجه بنداً بلا سعر على قاعدة
ق-٩: **فق-٩ لموضعٍ يُستحقّ فيه أجرٌ ولم يُسعَّر بعد**، وهذا موضعٌ لا يُستحقّ
فيه أجر. وبقاؤه بنداً بلا سعر كان يُبقي تحذيراً أصفر لا ينطفئ أبداً، ويوهم
المدقّق أن في الكشف نقصاً.

**وأثر العمل القائم لا يضيع** بزوال بنده: أسطر المواد تسمّي الأعمدة القائمة
بعددها ونوعها في خانة المصدر، فيقرأ المدقّق من أين جاء كل براكيت وكل عازل.
"""

from __future__ import annotations

from .overhead import (
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
    BracketPattern,
    CircuitType,
    Conversion11kV,
    LabourLine,
    MaterialLine,
    Network11kV,
    PoleType11,
)

CROWN_SPARE: dict[PoleType11, dict[tuple[str, str], int]] = {
    PoleType11.ROUND: {M_PIN_INSULATOR_11: 1},
    PoleType11.LATTICE: {M_DISC_INSULATOR_11: 2},
}
"""احتياط التاج: بدلُ العازل القائم على رأس العمود إذا تلف عند نقله (ق-٨٤).

**الرقم الوحيد المكتوب في هذا الملف**، لأنه بدلُ تالفٍ لا حاجةُ دائرةٍ جديدة —
فلا يعرفه مولّد الشبكة. بنصّ المستخدم: المدوّر **+1 دبوسي** والمشبك **+2 قرصي**،
«فوق الأرقام التي ذكرتَها».
"""


def bracket_increment(pattern: BracketPattern, pole: PoleType11) -> dict[str, int]:
    """الفرق في البراكيت لعمود قائم واحد: المزدوجة ناقص المفردة.

    **لا يُكتب الفرق رقماً** بل يُطرح من الجدولين، فيبقى تابعاً لهما أبداً.
    وتقرأه اللوحة لتعرض التفصيل بالمقاسات، وحارسٌ يلزمه بموافقة `pole_increment`
    فلا يفترق الشرحُ عن الحساب.
    """
    single = bracket_need_11(CircuitType.SINGLE, pattern, pole)
    double = bracket_need_11(CircuitType.DOUBLE, pattern, pole)
    increment = {size: double.get(size, 0) - single.get(size, 0)
                 for size in set(single) | set(double)}
    return {size: count for size, count in increment.items() if count > 0}


def _one_pole(circuit: CircuitType, pattern: BracketPattern,
              pole: PoleType11) -> dict[tuple[str, str], float]:
    """مواد عمودٍ واحدٍ بمسارٍ صفر، مجموعةً بالاسم والوحدة."""
    net = Network11kV(
        route_length_m=0,
        circuit=circuit,
        bracket_pattern=pattern,
        poles_lattice=1 if pole is PoleType11.LATTICE else 0,
        poles_round=1 if pole is PoleType11.ROUND else 0,
    )
    totals: dict[tuple[str, str], float] = {}
    for line in materials_11kv(net):
        key = (line.name, line.unit)
        totals[key] = totals.get(key, 0) + line.qty
    return totals


def pole_increment(pattern: BracketPattern,
                   pole: PoleType11) -> dict[tuple[str, str], float]:
    """كل ما يزيده تحويل **عمودٍ قائمٍ واحد** من مفرد إلى مزدوج.

    المولّد مطروحٌ من نفسه. فما لا يتغيّر بتغيّر الدائرة — العمود والكونكريت
    والتأريض — فرقُه صفرٌ **فيسقط من تلقائه** لا بسطرٍ يستثنيه.
    """
    single = _one_pole(CircuitType.SINGLE, pattern, pole)
    double = _one_pole(CircuitType.DOUBLE, pattern, pole)
    return {key: qty - single.get(key, 0)
            for key, qty in double.items() if qty - single.get(key, 0) > 0}


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

    # ٢. الأعمدة القائمة — الفرق المشتقّ، ومعه احتياط التاج وحده مكتوباً
    for pole, count, label in (
        (PoleType11.LATTICE, net.existing_lattice, "أعمدة مشبكة قائمة"),
        (PoleType11.ROUND, net.existing_round, "أعمدة مدوّرة قائمة"),
    ):
        if not count:
            continue
        spares = CROWN_SPARE[pole]
        for key, per_pole in pole_increment(net.bracket_pattern, pole).items():
            spare = spares.get(key, 0)
            if spare:
                source = (f"{label}: {count} × ({per_pole:g} فرق المزدوجة عن المفردة"
                          f" + {spare} بدل تاج)")
            else:
                source = f"{label}: {count} × {per_pole:g} (فرق المزدوجة عن المفردة)"
            lines.append(MaterialLine(*key, (per_pole + spare) * count, source))

    # ٣. أعمدة الإسناد المضافة — بحاجة عمود الشبكة المزدوجة كاملة
    lines += materials_11kv(_added_network(net))
    return lines


def labour_conversion_11(net: Conversion11kV, rates: dict) -> list[LabourLine]:
    """أجور التحويل: التسليك ونصب الأعمدة المضافة — **ولا شيء غيرهما** (ق-٨٤).

    فتركيب البراكيت والعوازل على العمود القائم لا أجر له بنصّ المستخدم.
    """
    out: list[LabourLine] = []

    qty = wire_quantity(net.route_length_m, CircuitType.SINGLE,
                        net.length_includes_waste, net.waste_pct)
    if qty:
        entry = rates[WIRING_11_RATE]
        out.append(LabourLine(WIRING_11_LABEL, entry["الوحدة"], qty, entry["السعر"],
                              source="تسليك الدائرة الجديدة", driver=M_WIRE_11))

    out += labour_11kv(_added_network(net), rates)
    return out
