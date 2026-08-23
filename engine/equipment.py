# -*- coding: utf-8 -*-
"""محرك التجهيزات المنصوبة على الأعمدة.

أربع مجموعات لا تتبع طول المسار، بل يُدخل المستخدم عددها:

| التجهيز | المواد المولَّدة | الأجر |
|---|---|---|
| محولة 400 KVA | 15 مادة | نصب المحولة |
| فاصل ON-LOAD | 4 مواد | نصب الفاصل ON-LOAD |
| فاصل ON-LOAD على رأس القابلو | 9 مواد | نصب الفاصل ON-LOAD |
| فاصل هوائي 33 ك.ف | 8 مواد | نصب فاصل هوائي 33 ك.ف |
| قفيص عمود مشبك | مادة واحدة | بلا أجر |

القاعدة الحاكمة: **أجر التجهيز يشمل ملحقاته كلها** — قاطع الدورة والقاعدة ولنك
الفيوز ومانعة الصواعق والتأريض والترمنلات وجهاز الإنارة كلها داخل «نصب المحولة»،
وقابلو الفاصل النحاسي وترمنلاته داخل «نصب الفاصل». هذا ما يقوله الملف الأصلي حرفياً
وما أكّده المستخدم في وصف واجهة كلفة العمل.

**براكيت 2.1 متر ملغى تماماً (ق-١٩)** — كان في الملف الأصلي سطراً لكل فاصل، وأُسقط
من المجموعتين هنا: لا كمادة ولا كأجر.

المرجع: ق-٢٣ في docs/سجل_القرارات.md
"""

from __future__ import annotations

from enum import Enum

from .overhead import M_EARTH_TERMINAL, M_EARTH_WIRE
from .types import Equipment, LabourLine, MaterialLine

# ─────────────────────────────── أسماء المواد ───────────────────────────────
# تطابق الملف الأصلي حرفياً — أي اختلاف حرف واحد يفصل المادة عن سعرها.

M_TRANSFORMER = ("محولة 400 KVA", "عدد")
M_BREAKER = ("قاطع دورة 400 أمبير مع المتسعة", "عدد")
M_TRANSFORMER_BASE = ("قاعدة محولة 2.4 متر", "سيت")
M_FUSE_LINK = ("لنك فيوز 15 KV مع سلك فيوز 40 أمبير", "سيت")
M_FUSE_LINK_BASE = ("قاعدة لنك فيوز 2.4 متر", "عدد")
M_EARTH_ROD = ("قضيب تأريض 1.5 متر مع القفيص", "عدد")
M_CU_CABLE_50 = ("قابلو نحاس 1×50 ملم²", "متر")
M_CU_CABLE_150 = ("قابلو نحاس 1×150 ملم²", "متر")
M_ARRESTER_11 = ("مانعة صواعق 11 KV", "سيت")
M_ARRESTER_BASE = ("قاعدة مانعة صواعق مع الملحقات", "عدد")
M_TERMINAL_150 = ("ترمنل 150 ملم²", "عدد")
M_AL_FITTINGS_CU = ("معدات ربط ألمنيوم – نحاس", "عدد")
M_LIGHTING = ("جهاز إنارة", "عدد")
M_ONLOAD = ("فاصل ON-LOAD", "عدد")
M_AIR_ISOLATOR_33 = ("فاصل هوائي 33 ك.ف", "عدد")
M_ARRESTER_33 = ("مانعة صواعق 33 ك.ف", "سيت")
M_CABLE_185 = ("قابلو 1×185 ملم2", "متر")
M_TERMINAL_185 = ("ترمنل 185 ملم2", "عدد")
M_LATTICE_CAGE = ("قفيص عمود مشبك", "عدد")

# ───────────────────────────── جداول الملحقات ─────────────────────────────
# (المادة، الكمية لكل وحدة). مقروءة من RAW_تفصيلي في الملف الأصلي:
# المحولة الصفوف 5–19، الفاصل ON-LOAD 43–47، وعلى رأس القابلو 48–57،
# والفاصل الهوائي 33 ك.ف 85–92.

TRANSFORMER_KIT = [
    (M_TRANSFORMER, 1),
    (M_BREAKER, 2),
    (M_TRANSFORMER_BASE, 1),
    (M_FUSE_LINK, 1),
    (M_FUSE_LINK_BASE, 1),
    (M_EARTH_ROD, 3),
    (M_EARTH_WIRE, 15),
    (M_CU_CABLE_50, 25),
    (M_CU_CABLE_150, 80),
    (M_ARRESTER_11, 1),
    (M_ARRESTER_BASE, 1),
    (M_AL_FITTINGS_CU, 15),
    (M_EARTH_TERMINAL, 15),
    (M_TERMINAL_150, 30),
    (M_LIGHTING, 2),
]

# ─────────────────── الفاصل ON-LOAD: مصفوفة الجهد × الموقع ───────────────────
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
        # معدات ربط ألمنيوم – نحاس: 6 لكل فاصل في 11 ك.ف. لا نظير لها في 33 ك.ف
        # في الملف الأصلي — سؤال مفتوح س-٩.
        "fittings": (M_AL_FITTINGS_CU, 6),
        "labour": "نصب الفاصل ON-LOAD",
    },
    IsolatorVoltage.KV33: {
        "isolator": M_AIR_ISOLATOR_33,
        "cable": M_CABLE_185,
        "lug": M_TERMINAL_185,
        "arrester": M_ARRESTER_33,
        "fittings": None,
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
    ]
    if parts["fittings"]:
        kit.append(parts["fittings"])
    if position.needs_arrester:
        kit.append((parts["arrester"], 1))
        kit.extend(ARRESTER_ASSEMBLY_EXTRAS)
    return kit


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

KITS = [("transformers", TRANSFORMER_KIT, "محولة 400 KVA")] + [
    (attr, kit, label) for attr, (kit, label) in ISOLATOR_KITS.items()
]

# ───────────────────────────────── التوليد ─────────────────────────────────


def materials_equipment(eq: Equipment) -> list[MaterialLine]:
    """يولّد أسطر مواد التجهيزات — سطر مستقل لكل مادة في كل مجموعة.

    الفاصلان (الهوائي وعلى رأس القابلو) يُنتجان المادة نفسها «فاصل ON-LOAD» بسعر
    واحد، لكن بمصدرين مختلفين فيبقى تتبّع الرقم ممكناً.
    """
    lines: list[MaterialLine] = []
    for attr, kit, label in KITS:
        count = getattr(eq, attr)
        if not count:
            continue
        for material, per_unit in kit:
            lines.append(
                MaterialLine(
                    *material, count * per_unit, f"{label}: {count} × {per_unit}"
                )
            )

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
    items = [("نصب المحولة", eq.transformers, "عدد المحولات")]

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
