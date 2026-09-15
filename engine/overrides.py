# -*- coding: utf-8 -*-
"""التعديل اليدوي على الكميات — طبقةٌ فوق نتيجة المحرك لا داخلها (ق-٨٢).

بطلب المستخدم: «أن يكون التغيير مفتوحاً (بإذن معين) في البرنامج نفسه قبل إجراء
عملية التصدير، لأن هذا أضمن». وبشرطه: «أهمّ شيء الحسابات والنتائج الرئيسية لا
تُمسّ ويمكن العودة إليها».

## لماذا طبقة فوق النتيجة

`compute_project` لا يعرف بهذا الملف شيئاً، ولم يتغيّر فيه حرف. والتعديل يُطبَّق
**بعده** على نسخة من نتيجته. فإلغاء التعديلات ليس «استرجاعاً» بل إزالةُ طبقة:
الرقم المحسوب لم يُمحَ أصلاً.

**وملف `.wo` يحفظ المُدخَلات وحدها** (ق-٦١)، فالرقم المحسوب يُعاد توليده عند كل
فتح. أي أن التراجع يبقى ممكناً بعد شهور، وعلى حاسبة أخرى.

## ما يترتّب على تعديل كمية

| المُعدَّل | ما يتبعه تلقائياً |
|---|---|
| كمية مادة | كلفتها · كلفة المواد · الكلفة الكلية · **وكمية أجرها** (ق-٨١) |
| كمية أجر | كلفته · كلفة العمل · الكلفة الكلية |

**وتعديل الأجر يغلب تعديل مادته:** من عدّل بنداً بعينه أراده بذاته، فلا يُطمَس
بتعديلٍ انتقل إليه من مادته.

## الالتباس يُرفض ولا يُخمَّن

بندا أجرٍ باسمٍ واحد ووحدة واحدة وسعرين مختلفين واردان (ق-٢٤: «نصب عمود مشبك
تعليق 14م» في مقطع مفرد وآخر مزدوج). ولا سبيل لمعرفة أيّهما قُصد بالتعديل،
**فيُرفض تعديلهما معاً** ويُبلَّغ عن السبب — ولا يُطبَّق على أحدهما رجماً.
"""

from __future__ import annotations

from dataclasses import replace

MANUAL = "معدَّل_يدوياً"
COMPUTED = "الكمية_المحسوبة"


def key_of(name: str, unit: str) -> str:
    """مفتاح السطر: اسمه ووحدته. نصٌّ واحد ليُحفظ في ملف `.wo` كما هو."""
    return f"{name}|{unit}"


def ambiguous_labour(result: dict) -> set[str]:
    """مفاتيح أجورٍ تتكرّر بسعرين — لا تقبل تعديلاً لأن المقصود ملتبس."""
    seen: dict[str, int] = {}
    for line in result["أجور_العمل"]:
        key = key_of(line.name, line.unit)
        seen[key] = seen.get(key, 0) + 1
    return {key for key, count in seen.items() if count > 1}


def _material_cost(row: dict) -> float:
    """كلفة المادة بعد تغيّر كميتها — بالقواعد نفسها التي يستعملها المحرك."""
    if row["كمية_فقط"] or row["سعر_مفقود"]:
        return 0.0
    return row["الكمية"] * row["سعر الوحدة"]


def apply(result: dict, materials: dict | None = None,
          labour: dict | None = None) -> dict:
    """يعيد نتيجةً جديدة بعد تطبيق التعديلات اليدوية.

    **وبلا تعديلات يعيد النتيجة نفسها بعينها** — لا نسخةً منها. فغياب التعديل
    يعني غياب هذه الطبقة تماماً، لا مروراً بها بلا أثر: ويحرس ذلك اختبارٌ
    يقارن بالهوية لا بالتساوي.
    """
    materials = {k: v for k, v in (materials or {}).items() if v is not None}
    labour = {k: v for k, v in (labour or {}).items() if v is not None}
    if not materials and not labour:
        return result

    from .links import material_drivers

    out = dict(result)
    blocked = ambiguous_labour(result)

    # ١. المواد
    rows = []
    changed_materials: dict[tuple[str, str], float] = {}
    for row in result["المواد"]:
        key = key_of(row["المادة"], row["الوحدة"])
        wanted = materials.get(key)
        if wanted is None or wanted == row["الكمية"]:
            rows.append(row)
            continue
        edited = dict(row)
        edited[COMPUTED] = row["الكمية"]
        edited[MANUAL] = True
        edited["الكمية"] = wanted
        edited["الكلفة"] = _material_cost(edited)
        edited["تفصيل"] = list(row["تفصيل"]) + [{
            "الكمية": wanted,
            "المصدر": f"قيمة يدوية — والمحسوب {row['الكمية']:g}",
        }]
        rows.append(edited)
        changed_materials[(row["المادة"], row["الوحدة"])] = wanted

    # ٢. الأجور: تعديلٌ صريح، وإلا ما انتقل إليها من مادتها (ق-٨١)
    links = material_drivers(result)
    lines = []
    for index, line in enumerate(result["أجور_العمل"]):
        key = key_of(line.name, line.unit)
        wanted = None if key in blocked else labour.get(key)
        if wanted is None:
            driven = links.get(index)
            if driven in changed_materials:
                wanted = changed_materials[driven]
        if wanted is None or wanted == line.qty:
            lines.append(line)
            continue
        lines.append(replace(line, qty=wanted, manual=True, computed_qty=line.qty))

    out["المواد"] = rows
    out["أجور_العمل"] = lines
    out["كلفة_المواد"] = sum(row["الكلفة"] for row in rows)
    out["كلفة_العمل"] = sum(line.cost for line in lines)
    out["الكلفة_الكلية"] = out["كلفة_المواد"] + out["كلفة_العمل"]
    out["تعديلات_يدوية"] = summary(out)
    return out


def summary(result: dict) -> dict:
    """ما عُدِّل في هذه النتيجة — للعرض على الشاشة وللوسم في ورقة التدقيق."""
    materials = [row["المادة"] for row in result["المواد"] if row.get(MANUAL)]
    labour = [line.name for line in result["أجور_العمل"] if line.manual]
    return {"المواد": materials, "الأجور": labour,
            "العدد": len(materials) + len(labour)}
