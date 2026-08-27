# -*- coding: utf-8 -*-
"""حساب المشروع بالمقاطع.

المشروع الواقعي مقاطع لا شبكة واحدة: مقطع مزدوج، ومقطع مفرد، ومقطع ضغط واطئ
بالقابلو المعلق، وآخر بالأسلاك. المحرك لم يحتج تغييراً جوهرياً لأن التجميع بمفتاح
(المادة + الوحدة) قائم أصلاً — كل ما أُضيف أن المقاطع تُولّد أسطرها ثم تُجمَّع معاً،
واسم المقطع يُلصق بمصدر كل سطر فيبقى التتبّع كاملاً.

المرجع: ق-٢٤ في docs/سجل_القرارات.md
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace

from .equipment import labour_equipment, materials_equipment
from .lowvoltage import labour_lv, materials_lv
from .overhead import (
    aggregate,
    labour_11kv,
    labour_33kv,
    materials_11kv,
    materials_33kv,
)
from .types import (
    Equipment,
    LabourLine,
    MaterialLine,
    Network11kV,
    Network33kV,
    NetworkLV,
    Project,
    Segment,
    Underground11kV,
    Underground33kV,
)
from .underground import (
    CIVIL_GROUP,
    labour_underground11,
    labour_underground33,
    materials_underground11,
    materials_underground33,
)


def _tag(lines: list, label: str) -> list:
    """يُلصق اسم المقطع بمصدر كل سطر. الاسم الفارغ لا يُلصق شيئاً."""
    if not label:
        return lines
    return [replace(line, source=f"{label} ← {line.source}") for line in lines]


def materials_of(segment: Segment, catalog: dict) -> list[MaterialLine]:
    """أسطر مواد مقطع واحد، موسومة باسمه.

    يستقبل نسخة الأسعار لأن مقاطع الشبكة الأرضية تحتاج جدول «عرض_الخندق»
    لحساب الرمل والشتايكر والشريط (ق-٤٣)."""
    content = segment.content
    if isinstance(content, Network11kV):
        lines = materials_11kv(content)
    elif isinstance(content, Network33kV):
        lines = materials_33kv(content)
    elif isinstance(content, NetworkLV):
        lines = materials_lv(content)
    elif isinstance(content, Equipment):
        lines = materials_equipment(content)
    elif isinstance(content, Underground11kV):
        lines = materials_underground11(content, catalog)
    elif isinstance(content, Underground33kV):
        lines = materials_underground33(content, catalog)
    else:
        raise TypeError(f"محتوى مقطع غير معروف: {type(content).__name__}")
    return _tag(lines, segment.name)


def labour_of(segment: Segment, catalog: dict) -> list[LabourLine]:
    """أسطر أجور مقطع واحد، موسومة باسمه.

    يستقبل نسخة الأسعار كاملة لا قسم الأجور وحده — الشبكة الأرضية تحتاج أيضاً
    جدول «تعرفة الأعمال المدنية» (ق-٣٠).
    """
    content = segment.content
    rates = catalog["أجور_العمل"]
    if isinstance(content, Network11kV):
        lines = labour_11kv(content, rates)
    elif isinstance(content, Network33kV):
        lines = labour_33kv(content, rates)
    elif isinstance(content, NetworkLV):
        lines = labour_lv(content, rates)
    elif isinstance(content, Equipment):
        lines = labour_equipment(content, rates)
    elif isinstance(content, Underground11kV):
        lines = labour_underground11(content, catalog)
    elif isinstance(content, Underground33kV):
        lines = labour_underground33(content, catalog)
    else:
        raise TypeError(f"محتوى مقطع غير معروف: {type(content).__name__}")
    return _tag(lines, segment.name)


def aggregate_labour(lines: list[LabourLine]) -> list[LabourLine]:
    """يجمع أسطر الأجور المتطابقة في بند واحد، ويصل مصادرها بفاصل.

    بلا هذا يظهر «نصب عمود مشبك 11م» ثلاث مرات في مشروع من ثلاثة مقاطع — وهو ما
    لا يقبله جدول أجور العمل في أمر العمل الرسمي.

    البنود ذات الأجر المختلف تبقى منفصلة: «نصب عمود مشبك تعليق 14م» في مقطع مفرد أجره
    260,000 وفي مقطع مزدوج 450,000، فجمعهما في سطر واحد يُخفي فارقاً حقيقياً.
    """
    merged: "OrderedDict[tuple, LabourLine]" = OrderedDict()
    for line in lines:
        key = (line.name, line.unit, line.rate)
        if key in merged:
            previous = merged[key]
            merged[key] = replace(
                previous,
                qty=previous.qty + line.qty,
                source=f"{previous.source} + {line.source}"
                if line.source and previous.source
                else previous.source or line.source,
            )
        else:
            merged[key] = line
    return list(merged.values())


def compute_project(project: Project, catalog: dict) -> dict:
    """يحسب المشروع بمقاطعه ويعيد المواد والأجور والمجاميع."""
    prices = catalog["المواد"]
    rates = catalog["أجور_العمل"]

    raw: list[MaterialLine] = []
    labour_raw: list[LabourLine] = []
    for segment in project.segments:
        raw += materials_of(segment, catalog)
        labour_raw += labour_of(segment, catalog)

    # عبور الشوارع: إجمالي واحد للمشروع كله، لا لكل مقطع (بطلب المستخدم، ق-٣٠).
    # وهما **ضمن الأعمال المدنية** بنصّ المستخدم، فيحملان وسمها (ق-٣٨).
    for field_name, label in (
        ("street_crossing_secondary_m", "عبور الشوارع الفرعية"),
        ("street_crossing_main_m", "عبور الشوارع الرئيسية – حفر مخفي"),
    ):
        length = getattr(project, field_name)
        if length:
            entry = rates[label]
            labour_raw.append(
                LabourLine(
                    label, entry["الوحدة"], length, entry["السعر"], group=CIVIL_GROUP
                )
            )

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

    labour = aggregate_labour(labour_raw)
    labour_cost = sum(line.cost for line in labour)

    return {
        "raw": raw,
        # نسخة الأسعار التي أنتجت هذه الأرقام — تُطبع على الورقة وتُحفظ مع
        # المشروع لاحقاً، فلا تتغيّر كلفة أمر عمل قديم بتحديث الأسعار (ق-٤٠).
        "نسخة_الأسعار": catalog.get("نسخة", ""),
        "المقاطع": list(project.segments),
        "المواد": materials,
        "أجور_العمل": labour,
        "كلفة_المواد": materials_cost,
        "كلفة_العمل": labour_cost,
        "الكلفة_الكلية": materials_cost + labour_cost,
        "أسعار_مفقودة": [m["المادة"] for m in materials if m["سعر_مفقود"]],
        "أجور_مفقودة": [l.name for l in labour if l.rate_missing],
    }
