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

ONLOAD_KIT = [
    (M_ONLOAD, 1),
    (M_CU_CABLE_150, 20),
    (M_AL_FITTINGS_CU, 6),
    (M_TERMINAL_150, 6),
]

# على رأس القابلو: نفس الفاصل زائد حماية وتأريضاً كاملين.
ONLOAD_CABLE_HEAD_KIT = ONLOAD_KIT + [
    (M_ARRESTER_11, 1),
    (M_ARRESTER_BASE, 1),
    (M_EARTH_ROD, 1),
    (M_CU_CABLE_50, 15),
    (M_EARTH_TERMINAL, 1),
]

AIR_ISOLATOR_33_KIT = [
    (M_AIR_ISOLATOR_33, 1),
    (M_ARRESTER_33, 1),
    (M_ARRESTER_BASE, 1),
    (M_EARTH_ROD, 1),
    (M_CABLE_185, 20),
    (M_TERMINAL_185, 6),
    (M_CU_CABLE_50, 15),
    (M_EARTH_TERMINAL, 1),
]

KITS = [
    ("transformers", TRANSFORMER_KIT, "محولة 400 KVA"),
    ("onload", ONLOAD_KIT, "فاصل ON-LOAD"),
    ("onload_cable_head", ONLOAD_CABLE_HEAD_KIT, "فاصل ON-LOAD على رأس القابلو"),
    ("air_isolator_33", AIR_ISOLATOR_33_KIT, "فاصل هوائي 33 ك.ف"),
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
    out: list[LabourLine] = []
    for label, count, source in (
        ("نصب المحولة", eq.transformers, "عدد المحولات"),
        (
            "نصب الفاصل ON-LOAD",
            eq.onload + eq.onload_cable_head,
            f"هوائي {eq.onload} + على رأس القابلو {eq.onload_cable_head}",
        ),
        ("نصب فاصل هوائي 33 ك.ف", eq.air_isolator_33, "عدد الفواصل الهوائية 33 ك.ف"),
    ):
        if count:
            entry = rates[label]
            out.append(LabourLine(label, entry["الوحدة"], count, entry["السعر"], source))
    return out
