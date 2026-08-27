# -*- coding: utf-8 -*-
"""محرك التجهيزات المنصوبة على الأعمدة.

مجموعات لا تتبع طول المسار، بل يُدخل المستخدم عددها:

| التجهيز | المُدخَل | الأجر |
|---|---|---|
| محولة 250 / 400 / 630 KVA بجهد 11/0.4 أو 33/0.4 ك.ف | عدد لكل (جهد، سعة) | نصب المحولة |
| فاصل هوائي 11 ك.ف ON LOAD — منتصف الشبكة / رأس القابلو | عدد | نصب الفاصل ON-LOAD |
| فاصل هوائي 33 ك.ف ON LOAD — منتصف الشبكة / رأس القابلو | عدد | نصب فاصل هوائي 33 ك.ف |
| قفيص عمود مشبك | عدد | بلا أجر |

القاعدة الحاكمة: **أجر التجهيز يشمل ملحقاته كلها** — قاطع الدورة والقاعدة ولنك
الفيوز ومانعة الصواعق والتأريض والترمنلات كلها داخل «نصب المحولة»، وقابلو الفاصل
النحاسي وترمنلاته داخل «نصب الفاصل».

المرجع: ق-٢٣ و ق-٢٥ و ق-٢٦ في docs/سجل_القرارات.md
"""

from __future__ import annotations

from enum import Enum

from .overhead import M_EARTH_TERMINAL, M_EARTH_WIRE
from .types import Equipment, LabourLine, MaterialLine

# ─────────────────────────────── أسماء المواد ───────────────────────────────
# تطابق الملف الأصلي حرفياً — أي اختلاف حرف واحد يفصل المادة عن سعرها.

class TransformerSize(Enum):
    """سعات المحولة المستخدمة في الشبكة الهوائية (ق-٢٦).

    سعة 1000 KVA لا تُستخدم هوائياً — أرضية فقط، وتُضاف مع الشبكة الأرضية لاحقاً.
    """

    KVA250 = 250
    KVA400 = 400
    KVA630 = 630

    @property
    def label(self) -> str:
        return f"{self.value} KVA"


TRANSFORMER_OUTPUTS = {
    TransformerSize.KVA250: (2, 250),
    TransformerSize.KVA400: (2, 400),
    # 630 استثناء: أربعة مخارج بقاطع 400 أمبير لا قاطع 630 (ق-٢٧)
    TransformerSize.KVA630: (4, 400),
}
"""لكل سعة: (عدد المخارج لشبكة الضغط الواطئ، سعة قاطع الدورة بالأمبير).

عدد المخارج = عدد قواطع الدورة، ولا قاطع رئيسي."""

class TransformerVoltage(Enum):
    """جهد المحولة التحويلي — بعض المشاريع 33/0.4 ك.ف لا 11/0.4 (ق-٣٧)."""

    KV11 = "11/0.4 ك.ف"
    KV33 = "33/0.4 ك.ف"


TRANSFORMER_SIZES_BY_VOLTAGE = {
    TransformerVoltage.KV11: [TransformerSize.KVA250, TransformerSize.KVA400,
                              TransformerSize.KVA630],
    # 33/0.4: السعات الثلاث كلها — 250 متوفّرة ولو نادراً (ق-٣٨؛ كانت مستبعَدة في ق-٣٧)
    TransformerVoltage.KV33: [TransformerSize.KVA250, TransformerSize.KVA400,
                              TransformerSize.KVA630],
}

M_TRANSFORMER = {
    (v, s): (f"محولة {s.value} KVA جهد {v.value}", "عدد")
    for v, sizes in TRANSFORMER_SIZES_BY_VOLTAGE.items()
    for s in sizes
}
M_BREAKER = {
    s: (f"قاطع دورة {amps} أمبير مع المتسعة", "عدد")
    for s, (_outputs, amps) in TRANSFORMER_OUTPUTS.items()
}
M_TRANSFORMER_BASE = ("قاعدة محولة مع الملحقات", "سيت")
M_FUSE_LINK = ("لنك فيوز 11 ك.ف مع السلك", "سيت")
M_FUSE_LINK_33 = ("لنك فيوز 33 ك.ف مع السلك", "سيت")
M_FUSE_LINK_BASE = ("قاعدة لنك فيوز مع الملحقات", "عدد")
M_EARTH_ROD = ("قضيب تأريض 1.5 متر مع القفيص", "عدد")
M_CU_CABLE_50 = ("قابلو نحاس 1×50 ملم²", "متر")
M_CU_CABLE_150 = ("قابلو نحاس 1×150 ملم²", "متر")
M_ARRESTER_11 = ("مانعة صواعق 11 KV", "سيت")
M_ARRESTER_BASE = ("قاعدة مانعة صواعق مع الملحقات", "عدد")
M_TERMINAL_150 = ("ترمنل 150 ملم²", "عدد")
M_AL_FITTINGS_CU = ("معدات ربط ألمنيوم – نحاس", "عدد")
M_AL_FITTINGS_CU_210 = ("معدات ربط ألمنيوم – نحاس 210 ملم²", "عدد")
M_ONLOAD = ("فاصل هوائي 11 ك.ف ON LOAD", "عدد")
M_AIR_ISOLATOR_33 = ("فاصل هوائي 33 ك.ف ON LOAD", "عدد")
M_ARRESTER_33 = ("مانعة صواعق 33 ك.ف", "سيت")
M_CABLE_185 = ("قابلو 1×185 ملم²", "متر")
M_TERMINAL_185 = ("ترمنل 185 ملم²", "عدد")
M_LATTICE_CAGE = ("قفيص عمود مشبك", "عدد")
M_BRACKET_21 = ("قاعدة فاصل هوائي – براكيت جنل 2.1م", "عدد")

# ───────────────────────────── جداول الملحقات ─────────────────────────────
# (المادة، الكمية لكل وحدة). مقروءة من RAW_تفصيلي في الملف الأصلي:
# المحولة الصفوف 5–19، الفاصل هوائي 11 ك.ف ON LOAD 43–47، وعلى رأس القابلو 48–57،
# والفاصل الهوائي 33 ك.ف 85–92.

CU_CABLE_150_PER_OUTPUT_M = 40
"""قابلو نحاس 1×150 لكل مخرج (م). مخرجان ← 80 م، وأربعة ← 160 م (ق-٢٧).

الطول يتبع **عدد المخارج** لا سعة المحولة — وهو ما يفسّر الرقمين اللذين ذكرتَهما."""

TERMINAL_150_PER_OUTPUT = 12
"""ترمنل 150 ملم² لكل مخرج. مخرجان ← 24، وأربعة ← 48 (ق-٤٣).

**يتبع عدد المخارج كما يتبعه القابلو** — وهذا ما أغلق الشذوذ الذي كان قائماً:
كان الرقم 30 ثابتاً بلا سعة ولا مخارج، فبقي 30 للمحولة 630 رغم أن قابلوها
تضاعف إلى 160 م في ق-٢٧. والرقم 12 لكل مخرج = **ستة موصلات × طرفين**."""

AL_FITTINGS_CU_PER_OUTPUT = 4
"""معدات ربط ألمنيوم – نحاس لكل مخرج. مخرجان ← 8، وأربعة ← 16 (ق-٤٣).

على جانب الضغط الواطئ، حيث يُربط قابلو المحولة النحاسي بشبكة الألمنيوم —
فيتبع عدد المخارج. وهذا يفسّر 4 لكل مخرج: ثلاثة أطوار وحيادي."""

EARTH_TERMINAL_PER_TRANSFORMER = 8
"""ترمنل 50 ملم² لكل محولة — **ثابت لا يتبع المخارج** (ق-٤٣).

وهذا متّسق: الترمنل هذا للتأريض (قابلو نحاس 1×50 بطول 25 م وسلك نحاس 50)،
والتأريض لا يتغيّر بعدد مخارج الضغط الواطئ."""

TRANSFORMER_COMMON_KIT = [
    (M_TRANSFORMER_BASE, 1),
    (M_FUSE_LINK_BASE, 1),
    (M_EARTH_ROD, 3),
    (M_EARTH_WIRE, 15),
    (M_CU_CABLE_50, 25),
    (M_ARRESTER_BASE, 1),
    (M_EARTH_TERMINAL, EARTH_TERMINAL_PER_TRANSFORMER),
]
"""ما لا يتغيّر بسعة المحولة **ولا بجهدها ولا بعدد مخارجها**.

**قاعدة مانعة الصواعق منها** — واحدة مهما اختلف الجهد (ق-٣٧).
**جهاز الإنارة ملغى تماماً** — كان في الملف الأصلي بكمية 2 وسعر صفر (ق-٢٦).
**وترمنل 150 ومعدات الربط خرجا منها في ق-٤٣** — صارا يتبعان عدد المخارج."""

TRANSFORMER_VOLTAGE_KIT = {
    # ما يتبع جهد المحولة: مانعة الصواعق وفاصل الفيوز (ق-٣٧)
    TransformerVoltage.KV11: [(M_ARRESTER_11, 1), (M_FUSE_LINK, 1)],
    TransformerVoltage.KV33: [(M_ARRESTER_33, 1), (M_FUSE_LINK_33, 1)],
}


def transformer_kit(
    size: TransformerSize, voltage: TransformerVoltage = TransformerVoltage.KV11
) -> list[tuple[tuple[str, str], float]]:
    """مواد محولة واحدة بسعتها وجهدها.

    **المتغيّر بالسعة:** المحولة نفسها، وقاطع الدورة (سعةً وعدداً)، وثلاثة بنود
    تتبع عدد المخارج: قابلو الضغط الواطئ وترمنل 150 ومعدات ربط ألمنيوم – نحاس
    (ق-٤٣).
    **المتغيّر بالجهد:** مانعة الصواعق وفاصل الفيوز (ق-٣٧).
    **قاطع الدورة لا يتبع الجهد** — الضغط الواطئ 0.4 ك.ف في الحالتين.
    وما عدا ذلك مشترك لا يتغيّر بأيٍّ منهما.
    """
    if size not in TRANSFORMER_SIZES_BY_VOLTAGE[voltage]:
        raise ValueError(f"سعة {size.label} غير متاحة لجهد {voltage.value}")
    outputs, _amps = TRANSFORMER_OUTPUTS[size]
    return [
        (M_TRANSFORMER[(voltage, size)], 1),
        (M_BREAKER[size], outputs),
        # ثلاثة بنود تتبع عدد المخارج: القابلو وترمنله ومعدات ربطه (ق-٤٣)
        (M_CU_CABLE_150, outputs * CU_CABLE_150_PER_OUTPUT_M),
        (M_TERMINAL_150, outputs * TERMINAL_150_PER_OUTPUT),
        (M_AL_FITTINGS_CU, outputs * AL_FITTINGS_CU_PER_OUTPUT),
    ] + TRANSFORMER_VOLTAGE_KIT[voltage] + TRANSFORMER_COMMON_KIT


TRANSFORMER_KITS = {
    (voltage, size): (transformer_kit(size, voltage), f"محولة {size.label} {voltage.value}")
    for voltage, sizes in TRANSFORMER_SIZES_BY_VOLTAGE.items()
    for size in sizes
}

# ─────────────────── الفاصل هوائي 11 ك.ف ON LOAD: مصفوفة الجهد × الموقع ───────────────────
# الفاصل نوعان بالجهد وحالتان بالموقع، فأربع تركيبات (ق-٢٥):
#
#            │ منتصف الشبكة        │ على رأس القابلو
#   ─────────┼─────────────────────┼──────────────────────────────────
#   11 ك.ف   │ قابلو 1×150، 20 م   │ قابلو 1×150، 10 م + مانعة 11 ك.ف
#   33 ك.ف   │ قابلو 1×185، 20 م   │ قابلو 1×185، 10 م + مانعة 33 ك.ف
#
# قاعدتان تحكمان الفروق:
#   • **مانعة الصواعق لرأس القابلو وحده.** الفاصل في منتصف الشبكة الهوائية لا
#     يحتاجها — الشبكة محمية أصلاً. ورأس القابلو نقطة انتقال من هوائي إلى أرضي،
#     وهي بالضبط موضع انعكاس الموجة الصاعقية، فتلزم المانعة.
#   • **قابلو رأس القابلو نصف الكمية.** في منتصف الشبكة يُربط الفاصل بالشبكة
#     الهوائية من **جهتيه**، وعلى رأس القابلو من **جهة واحدة** فقط والجهة الثانية
#     يربطها القابلو الأرضي نفسه.

CABLE_MID_NETWORK_M = 20
CABLE_HEAD_M = CABLE_MID_NETWORK_M // 2
LUGS_PER_ISOLATOR = 6

FITTINGS_PER_ISOLATOR = 6
"""معدات ربط ألمنيوم – نحاس لكل فاصل — في الجهدين معاً، وفي الموقعين معاً (ق-٢٦).

لا وجود لمعدات ألمنيوم – ألمنيوم في الفاصل إطلاقاً. ونوعها يتبع الجهد: العادية
في 11 ك.ف و«210 ملم²» في 33 ك.ف (ق-٣٧)."""

BRACKETS_21_PER_ISOLATOR = 1
"""قاعدة فاصل هوائي – براكيت جنل 2.1م — واحد لكل فاصل، بالجهدين والموقعين (ق-٢٧).

يُعيد ما ألغاه ق-١٩ بطلبك، وهو **«قاعدة الفاصل الهوائي»** بتسمية المستخدم —
لا مادة غيره لهذا الغرض (ت-٩ حُسم في ق-٤١). أجر تركيبه داخل أجر نصب الفاصل،
وسعره 110,000 (ق-٣٦)."""

ARRESTER_ASSEMBLY_EXTRAS = [
    (M_ARRESTER_BASE, 1),
    (M_EARTH_ROD, 1),
    (M_CU_CABLE_50, 15),
    (M_EARTH_TERMINAL, 1),
]
"""ما يرافق مانعة الصواعق: قاعدتها وتأريضها. لا معنى لمانعة بلا أرضي."""


class IsolatorVoltage(Enum):
    KV11 = "11 ك.ف"
    KV33 = "33 ك.ف"


class IsolatorPosition(Enum):
    MID_NETWORK = "منتصف الشبكة"
    CABLE_HEAD = "على رأس القابلو"

    @property
    def needs_arrester(self) -> bool:
        return self is IsolatorPosition.CABLE_HEAD

    @property
    def cable_m(self) -> int:
        return CABLE_HEAD_M if self.needs_arrester else CABLE_MID_NETWORK_M


ISOLATOR_PARTS = {
    IsolatorVoltage.KV11: {
        "isolator": M_ONLOAD,
        "cable": M_CU_CABLE_150,
        "lug": M_TERMINAL_150,
        "arrester": M_ARRESTER_11,
        "fittings": (M_AL_FITTINGS_CU, FITTINGS_PER_ISOLATOR),
        "labour": "نصب الفاصل ON-LOAD",
    },
    IsolatorVoltage.KV33: {
        "isolator": M_AIR_ISOLATOR_33,
        "cable": M_CABLE_185,
        "lug": M_TERMINAL_185,
        "arrester": M_ARRESTER_33,
        # 210 ملم² لا العادية — السلك المتّصل 210/35 (ق-٣٧).
        # والملف الأصلي أغفلها كلياً في 33 ك.ف، وأكّدتَ أنها 6 (ق-٢٦)
        "fittings": (M_AL_FITTINGS_CU_210, FITTINGS_PER_ISOLATOR),
        "labour": "نصب فاصل هوائي 33 ك.ف",
    },
}


def isolator_kit(
    voltage: IsolatorVoltage, position: IsolatorPosition
) -> list[tuple[tuple[str, str], float]]:
    """مواد فاصل واحد بجهده وموقعه."""
    parts = ISOLATOR_PARTS[voltage]
    kit = [
        (parts["isolator"], 1),
        (parts["cable"], position.cable_m),
        (parts["lug"], LUGS_PER_ISOLATOR),
        (M_BRACKET_21, BRACKETS_21_PER_ISOLATOR),
    ]
    if parts["fittings"]:
        kit.append(parts["fittings"])
    if position.needs_arrester:
        kit.append((parts["arrester"], 1))
        kit.extend(ARRESTER_ASSEMBLY_EXTRAS)
    return kit


CAGES_PER_CABLE_HEAD_POLE = 6
"""قفيص عمود مشبك: **6 لكل عمود مشبك عليه رأس قابلو** (ق-٣٥).

وعدد أعمدة رأس القابلو يُستنتج من عدد الفواصل على رأس القابلو — لكل فاصل عمود.
الكمية **استرشادية** كبقية الاقتراحات: تُعتمد أو تُعدَّل يدوياً (ق-١٠)."""


def suggest_lattice_cages(eq: Equipment) -> int:
    """الاقتراح الاسترشادي لأقفاص العمود المشبك.

    6 أقفاص لكل عمود مشبك عليه رأس قابلو، وعدد تلك الأعمدة = مجموع الفواصل
    على رأس القابلو في الجهدين معاً.
    """
    cable_head_poles = eq.onload_11_head + eq.isolator_33_head
    return cable_head_poles * CAGES_PER_CABLE_HEAD_POLE


ISOLATORS = [
    ("onload_11_mid", IsolatorVoltage.KV11, IsolatorPosition.MID_NETWORK),
    ("onload_11_head", IsolatorVoltage.KV11, IsolatorPosition.CABLE_HEAD),
    ("isolator_33_mid", IsolatorVoltage.KV33, IsolatorPosition.MID_NETWORK),
    ("isolator_33_head", IsolatorVoltage.KV33, IsolatorPosition.CABLE_HEAD),
]

ISOLATOR_KITS = {
    attr: (isolator_kit(v, p), f"فاصل {v.value} — {p.value}")
    for attr, v, p in ISOLATORS
}

KITS = [(attr, kit, label) for attr, (kit, label) in ISOLATOR_KITS.items()]

# ───────────────────────────────── التوليد ─────────────────────────────────


def materials_equipment(eq: Equipment) -> list[MaterialLine]:
    """يولّد أسطر مواد التجهيزات — سطر مستقل لكل مادة في كل مجموعة.

    الفاصلان (الهوائي وعلى رأس القابلو) يُنتجان المادة نفسها «فاصل هوائي 11 ك.ف ON LOAD» بسعر
    واحد، لكن بمصدرين مختلفين فيبقى تتبّع الرقم ممكناً.
    """
    lines: list[MaterialLine] = []

    # مفتاح المحولة ثنائي (الجهد، السعة). مفتاح مجهول يُرفَض صراحةً ولا يُهمَل
    # بصمت — إهماله يعني محولة بملايين الدنانير تختفي من الجدول (ق-٣٧).
    unknown = set(eq.transformers) - set(TRANSFORMER_KITS)
    if unknown:
        raise KeyError(
            "مفتاح محولة غير معروف: "
            + "، ".join(repr(k) for k in sorted(unknown, key=repr))
            + " — المفتاح المتوقَّع (TransformerVoltage, TransformerSize)"
        )

    def emit(kit, count, label):
        for material, per_unit in kit:
            lines.append(
                MaterialLine(
                    *material, count * per_unit, f"{label}: {count} × {per_unit}"
                )
            )

    for key, (kit, label) in TRANSFORMER_KITS.items():  # ترتيب ثابت لا يتبع الإدخال
        count = eq.transformers.get(key, 0)
        if count:
            emit(kit, count, label)

    for attr, kit, label in KITS:
        count = getattr(eq, attr)
        if count:
            emit(kit, count, label)

    if eq.lattice_cages:
        lines.append(
            MaterialLine(
                *M_LATTICE_CAGE, eq.lattice_cages, f"قفيص عمود مشبك: {eq.lattice_cages}"
            )
        )
    return lines


def labour_equipment(eq: Equipment, rates: dict) -> list[LabourLine]:
    """أجور التجهيزات.

    الفاصلان يجتمعان في بند أجر واحد — كما في الملف الأصلي، لأن العمل نفسه.
    القفيص بلا أجر مستقل: يُركَّب مع العمود.
    """
    transformers = sum(eq.transformers.values())
    items = [("نصب المحولة", transformers, "عدد المحولات بكل السعات والجهود")]

    # الفاصلان في الجهد الواحد يتقاسمان بند الأجر: العمل نفسه، والموقع لا يغيّره.
    for voltage, label in (
        (IsolatorVoltage.KV11, ISOLATOR_PARTS[IsolatorVoltage.KV11]["labour"]),
        (IsolatorVoltage.KV33, ISOLATOR_PARTS[IsolatorVoltage.KV33]["labour"]),
    ):
        mid, head = (
            (eq.onload_11_mid, eq.onload_11_head)
            if voltage is IsolatorVoltage.KV11
            else (eq.isolator_33_mid, eq.isolator_33_head)
        )
        if mid + head:
            items.append(
                (label, mid + head, f"منتصف الشبكة {mid} + على رأس القابلو {head}")
            )

    out = []
    for label, count, source in items:
        if count:
            entry = rates[label]
            out.append(LabourLine(label, entry["الوحدة"], count, entry["السعر"], source))
    return out
