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
"""شتايكر كل نصف متر من طول المسار."""

SAND_DEPTH_M = 0.4
"""سُمك طبقة الرمل النهري (م) — ما يوضع **أسفل المغذي وأعلاه** معاً (ق-٤٣).

هذا هو الرقم 0.4 في الصيغة القديمة `طول × 0.6 × 0.4`. أما 0.6 فكان **عرض
الخندق** مثبَّتاً، وهو عرض المغذيَّين لا عرضاً عاماً — فصار يُقرأ من جدول
`عرض_الخندق` بحسب عدد المغذيات."""

WIDE_TRENCH_M = 1.0
"""العرض الذي يتضاعف عنده الشتايكر وشريط التحذير: **متر فأكثر** (ق-٤٣).

بنصّ المستخدم: «إذا كان عرض الحفر متر فما فوق توضع قطعتان شتايكر متجاورتان»،
وكذلك «لفّتان متجاورتان» من الشريط. ويبدأ من **5 مغذيات** حيث يبلغ العرض 1.0 م."""

WIDE_TRENCH_MULTIPLIER = 2
"""قطعتان لا واحدة، ولفّتان لا واحدة، في الخندق العريض (ق-٤٣)."""

WARNING_TAPE_ROLL_M = 90
"""طول لفة شريط التحذير الواحدة (م)."""


def trench_width_m(feeder_count: int, catalog: dict) -> float | None:
    """عرض الخندق (م) بحسب عدد المغذيات فيه — من جدول `عرض_الخندق` (ق-٤٣).

    الجدول يبلغ 8 مغذيات، وما زاد عليها يأخذ قيمة الثمانية بنصّ المستخدم
    («ثمانية أو أكثر يكون 1.8»). و`None` حين لا جدول أصلاً — يُبلَّغ عنه بدل
    أن يُخمَّن عرض تُبنى عليه كميةُ رملٍ خاطئة.
    """
    table = catalog.get("عرض_الخندق", {})
    widths = {int(k): v for k, v in table.items() if not k.startswith("_")}
    if not widths or feeder_count <= 0:
        return None
    return widths.get(feeder_count, widths[max(widths)] if feeder_count > max(widths) else None)


def is_wide_trench(width_m: float | None) -> bool:
    """هل الخندق عريض بما يستدعي مضاعفة الشتايكر والشريط؟"""
    return width_m is not None and width_m >= WIDE_TRENCH_M

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


CIVIL_GROUP = "الأعمال المدنية"
"""وسم يجمع بنود الأعمال المدنية كلها في الطباعة — الحفر وإعادة المسار وعبور
الشوارع معاً — بنصّ المستخدم: «عبور الشوارع الفرعية والحفر المخفي للشوارع
الرئيسية أيضاً تُعتبر ضمن الأعمال المدنية وتُضاف إن وُجدت» (ق-٣٨)."""

CIVIL_COMPONENTS = ("حفر الخندق", "إعادة المسار")
"""مكوّنا التعرفة بترتيب تنفيذهما على الأرض (ق-٣٨). كانا رقماً واحداً مجموعاً
قبل ذلك، وفصّلهما المستخدم بأرقام صريحة لكل نوع رصيف × كل تعدّد مسار."""

ROUTE_MULTIPLICITY = {1: "مفرد", 2: "ثنائي", 3: "ثلاثي"}
"""تسمية المستخدم لعدد المغذيات في الخندق. المفتاح في الجدول رقمي، والتسمية
للعرض فقط — 1 مغذٍّ = مسار مفرد، و2 = ثنائي، و3 = ثلاثي."""


def route_multiplicity_label(count: int) -> str:
    return ROUTE_MULTIPLICITY.get(count, f"{count} مغذيات")


def civil_tariff_parts(
    sidewalk_type: SidewalkType, count: int, catalog: dict
) -> list[tuple[str, float | None]]:
    """مكوّنات تعرفة الأعمال المدنية للمتر: [(اسم المكوّن، دينار/متر)].

    ثلاث حالات لا رابع لها:

    1. العدد في الجدول المفصَّل (1 أو 2 أو 3) ← **مكوّنان**: حفر الخندق ثم
       إعادة المسار، كلٌّ بسعره (ق-٣٨).
    2. العدد في الإجمالي غير المفصَّل (4 أو 5) ← **مكوّن واحد** موسوم بأنه لم
       يُفصَّل بعد. الرقم القديم من ملف المستخدم محفوظ كما هو ولم يُحذف (ق-٠).
    3. العدد خارج الجدولين ← مكوّن واحد بسعر `None`، فيُطبع «بلا أجر» ويُبلَّغ
       عنه بدل أن يُخمَّن رقم قد يكون خاطئاً في الاتجاهين.

    مشتركة بين 11 و33 ك.ف — الجدول واحد (ق-٣١).
    """
    tariff = catalog["تعرفة_الأعمال_المدنية"]
    detailed = tariff.get("مفصَّلة", {})
    key = str(count)

    parts = [
        (component, detailed[component][sidewalk_type.value][key])
        for component in CIVIL_COMPONENTS
        if key in detailed.get(component, {}).get(sidewalk_type.value, {})
    ]
    if len(parts) == len(CIVIL_COMPONENTS):
        return parts

    # ما زاد على 3 مغذيات: **كل مكوّن** يزيد 2,000 لكل مغذٍّ إضافي (ق-٤٧).
    # فالتفصيل يشمل كل عدد ولا يبقى إجمالٌ غير مفصَّل.
    extra = tariff.get("زيادة_ما_فوق_الجدول", {})
    base_count = extra.get("من_عدد")
    step = extra.get("الزيادة_لكل_مكوّن")
    if base_count and step and count > base_count:
        base_key = str(base_count)
        added = (count - base_count) * step
        extended = [
            (component, detailed[component][sidewalk_type.value][base_key] + added)
            for component in CIVIL_COMPONENTS
            if base_key in detailed.get(component, {}).get(sidewalk_type.value, {})
        ]
        if len(extended) == len(CIVIL_COMPONENTS):
            return extended

    return [("الحفر وإعادة المسار", None)]


def _civil_tariff_lookup(
    sidewalk_type: SidewalkType, count: int, catalog: dict
) -> float | None:
    """إجمالي التعرفة للمتر — مجموع المكوّنات. `None` إن كان العدد خارج الجدول.

    باقٍ لأن الواجهة والاختبارات تعرضان الإجمالي، والتفصيل يظهر في جدول الأجور.
    """
    parts = civil_tariff_parts(sidewalk_type, count, catalog)
    if any(rate is None for _name, rate in parts):
        return None
    return sum(rate for _name, rate in parts)


def civil_works_rate(net: Underground11kV, catalog: dict) -> float | None:
    """تعرفة الأعمال المدنية لمقطع 11 ك.ف — بعدد المغذيات (= عدد الكابلات)."""
    return _civil_tariff_lookup(net.sidewalk_type, net.feeder_count, catalog)


def civil_works_rate_33(net: Underground33kV, catalog: dict) -> float | None:
    """تعرفة الأعمال المدنية لمقطع 33 ك.ف — بعدد **الدوائر** لا عدد الكابلات.

    المغذي الواحد (بكابلاته الثلاثة معاً في خندق واحد) يُعامَل معاملة مغذٍّ واحد
    مماثل لـ11 ك.ف — بتأكيد المستخدم صراحةً (ق-٣١). نفس الجدول بالضبط.
    """
    return _civil_tariff_lookup(net.sidewalk_type, net.circuit.circuits, catalog)


def _civil_labour_lines(
    sidewalk_type: SidewalkType, count: int, route_length_m: float, catalog: dict
) -> list[LabourLine]:
    """سطر أجر لكل مكوّن من مكوّني التعرفة — لا سطراً واحداً مجموعاً (ق-٣٨)."""
    multiplicity = route_multiplicity_label(count)
    return [
        LabourLine(
            f"{component} — رصيف {sidewalk_type.value}، مسار {multiplicity}",
            "متر",
            route_length_m,
            rate,
            group=CIVIL_GROUP,
        )
        for component, rate in civil_tariff_parts(sidewalk_type, count, catalog)
    ]


M_CROSSING_PIPE = ("أنبوب 8 انج 10 بار", "روطة")

PIPE_LENGTH_M = 6
"""طول الأنبوب الواحد (م) — «الروطة» الواحدة (ق-٤٥)."""

SPARE_PIPES = 1
"""أنبوب احتياط واحد يُضاف إلى المجموع (ق-٤٨).

**واحد للعبور كلّه لا لكل مغذٍّ** — كما أملاه المستخدم بصيغة المفرد. غرضه أن
يبقى في الموقع بديلٌ لأنبوب يُكسَر أثناء التركيب، فلا يتوقّف العمل."""


def street_crossing_pipes(
    street_length_m: float, feeder_count: int, label: str
) -> list[MaterialLine]:
    """أنابيب عبور الشارع — **للشوارع الفرعية وحدها** (ق-٤٦).

    ```
    العدد = ⌈طول الشارع ÷ 6⌉ × عدد المغذيات العابرة + 1 احتياط
    ```

    **لكل مغذٍّ أنبوبه الخاص** بتصحيح المستخدم في ق-٤٦ — كان لا يُضرب بعددهم
    في ق-٤٥ فصُحّح. **ويُضاف أنبوب احتياط واحد** للعبور كلّه (ق-٤٨).

    **والطول هنا طول الشارع المعبور، لا طول المسار.**

    **ولا أنبوب للشوارع الرئيسية** — عبورها «حفر مخفي»، والأنبوب يُحسب للفرعية
    فقط بنصّ المستخدم. فالمناداة على هذه الدالة مسؤولية المستدعي.
    """
    if street_length_m <= 0 or feeder_count <= 0:
        return []
    per_feeder = _roundup(street_length_m / PIPE_LENGTH_M)
    return [
        MaterialLine(
            *M_CROSSING_PIPE,
            per_feeder * feeder_count + SPARE_PIPES,
            f"{label}: ⌈شارع {street_length_m:,.0f} م ÷ {PIPE_LENGTH_M} م⌉"
            f" × {feeder_count} مغذيات + {SPARE_PIPES} احتياط",
        )
    ]


def trench_materials(
    route_length_m: float, feeder_count: int, catalog: dict
) -> list[MaterialLine]:
    """موادّ الخندق الثلاث: الشتايكر والرمل النهري وشريط التحذير (ق-٣٠، ق-٤٣).

    الثلاثة **كمية بلا كلفة** بقرارك — تظهر في جدول الكميات ولا تدخل المجموع
    المالي، لأن كلفتها ضمن أجر الأعمال المدنية.

    **الجديد في ق-٤٣: عرض الخندق يتبع عدد المغذيات**، فيحكم الثلاثة معاً:

    ```
    الرمل   = طول × عرض الخندق × 0.4          (م³)
    الشتايكر = ⌈طول ÷ 0.5⌉ × (2 إن كان العرض ≥ 1 م)
    الشريط   = ⌈طول ÷ 90⌉  × (2 إن كان العرض ≥ 1 م)
    ```

    وحين لا يُعرف العرض (عدد مغذيات خارج الجدول) تُحسب الثلاثة بأضيق فرض —
    لا. بل **لا تُولَّد أسطر الخندق إطلاقاً**، ويُولَّد بدلها سطر واحد بكمية صفر
    ومصدر يشرح السبب: تخمين العرض يعني كمية رمل خاطئة في جدول يُسلَّم للمنفّذ.
    """
    if route_length_m <= 0:
        return []

    width = trench_width_m(feeder_count, catalog)
    if width is None:
        return [
            MaterialLine(
                *M_RIVER_SAND,
                0,
                f"⚠ لا عرض خندق لـ{feeder_count} مغذيات في الجدول — "
                "الرمل والشتايكر والشريط لم تُحسب",
            )
        ]

    wide = is_wide_trench(width)
    factor = WIDE_TRENCH_MULTIPLIER if wide else 1
    wide_note = (
        f" × {WIDE_TRENCH_MULTIPLIER} (العرض {width:g} م ≥ {WIDE_TRENCH_M:g} م)"
        if wide
        else ""
    )
    length_note = f"خندق بطول {route_length_m:,.0f} م"

    return [
        MaterialLine(
            *M_STAKER,
            _roundup(route_length_m / STAKER_DIVISOR_M) * factor,
            f"{length_note} ÷ {STAKER_DIVISOR_M:g} م{wide_note}",
        ),
        MaterialLine(
            *M_RIVER_SAND,
            _roundup(route_length_m * width * SAND_DEPTH_M),
            f"{length_note} × عرض {width:g} م ({feeder_count} مغذيات)"
            f" × سُمك {SAND_DEPTH_M:g} م",
        ),
        MaterialLine(
            *M_WARNING_TAPE,
            _roundup(route_length_m / WARNING_TAPE_ROLL_M) * factor,
            f"{length_note} ÷ {WARNING_TAPE_ROLL_M} م{wide_note}",
        ),
    ]


def materials_underground11(net: Underground11kV, catalog: dict) -> list[MaterialLine]:
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

    lines += trench_materials(net.route_length_m, net.feeder_count, catalog)

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
        out += _civil_labour_lines(
            net.sidewalk_type, net.feeder_count, net.route_length_m, catalog
        )

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


def materials_underground33(net: Underground33kV, catalog: dict) -> list[MaterialLine]:
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

    # 33 ك.ف: عرض الخندق بعدد **الدوائر** لا عدد الكابلات — كما الأعمال المدنية
    # تماماً (ق-٣١): المغذي الواحد بكابلاته الثلاثة مغذٍّ واحد في الخندق.
    lines += trench_materials(net.route_length_m, net.circuit.circuits, catalog)

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
        # 33 ك.ف: بعدد الدوائر لا عدد الكابلات — المغذي الواحد بكابلاته الثلاثة
        # يُعامَل معاملة مغذٍّ واحد مماثل لـ11 ك.ف (ق-٣١)
        out += _civil_labour_lines(
            net.sidewalk_type, net.circuit.circuits, net.route_length_m, catalog
        )

    return out
