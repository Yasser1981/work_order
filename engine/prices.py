# -*- coding: utf-8 -*-
"""تحرير الأسعار وإصدار نسخة جديدة منها (ق-٦٢).

بنصّ المستخدم: «من الضروري إتاحة تعديل الأسعار (أسعار العمل والمواد من داخل
البرنامج) مع **احتفاظ أوامر العمل القديمة بنفس سعر المواد والعمل في تاريخ
إنشائها** إلا إذا أنا أعطيت أمراً بتغييرها وتحديثها وفق الأسعار المحدَّثة».

## القاعدة الحاكمة لهذا الملف

**نسخة أسعار محفوظة لا تُعدَّل أبداً.** كل تحرير ينتج **ملفاً جديداً** باسم
جديد، والقديم يبقى كما هو حرفاً بحرف.

وهذا ليس تفصيلاً تقنياً بل هو **كلّ ما يجعل تثبيت الأسعار ذا معنى**: أمر عمل
يحمل «نسخة الأسعار = 2026-08» لا يبقى ثابت الكلفة إلا إذا كان الملف
`catalog_2026-08.json` نفسه لا يتغيّر. فلو حُرّر مكانه لتغيّرت كلفة كل أمر عمل
قديم يشير إليه، **بلا أن ينبّه أحد** — وهو الخلل الصامت الذي تمنعه هذه القاعدة.

## تسمية النسخة

`catalog_YYYY-MM-DD.json` لنسخة ينشئها المحرّر، و`catalog_YYYY-MM.json` للنسخ
المؤسِّسة. والترتيب الأبجدي يبقى ترتيباً زمنياً في الحالتين، فلا تنكسر
`latest_catalog_version`.

ولو حُرّرت الأسعار مرّتين في اليوم نفسه أُضيف حرف: `2026-08-31b` ثم `c` — فلا
تُطمَس نسخة صدر بها أمر عمل قبل ساعة.
"""

from __future__ import annotations

import copy
import json
import string

from datetime import date
from pathlib import Path

from .paths import catalog_path, catalog_versions

MATERIALS = "المواد"
LABOUR = "أجور_العمل"
PRICE = "السعر"
DERIVED = "مشتقّ"
REASON = "سبب"

DUAL_PRICE_KEYS = ("السعر_مفردة", "السعر_مزدوجة")
"""بنود أجور لها سعران بحسب نوع الدائرة — تُحرَّر كلٌّ على حدة (ق-١٦)."""


def next_version(today: date | None = None, existing: list[str] | None = None) -> str:
    """اسم نسخة جديدة لا يطمس نسخةً موجودة.

    يبدأ بتاريخ اليوم، فإن كان مأخوذاً أُضيف حرف لاتيني متصاعد. والحرف يبقى
    بعد التاريخ فيظلّ الترتيب الأبجدي زمنياً صحيحاً.
    """
    today = today or date.today()
    existing = catalog_versions() if existing is None else existing
    stem = today.isoformat()
    if stem not in existing:
        return stem
    for letter in string.ascii_lowercase[1:]:      # يبدأ من b: الأصل بلا حرف
        candidate = f"{stem}{letter}"
        if candidate not in existing:
            return candidate
    raise RuntimeError("أكثر من 25 نسخة أسعار في يوم واحد — راجع ما يجري.")


def strip_derived(catalog: dict) -> dict:
    """يحذف الأسعار المحسوبة قبل الحفظ، فلا يُخزَّن رقم مشتقّ رقماً ثابتاً.

    `load_catalog` يملأ سعر المادة المشتقّة عند كل تحميل (ق-٥٨). ولو حُفظ ذلك
    الرقم في الملف لصار سعراً مستقلّاً ظاهرياً، فيوهم من يقرأ الملف أنه قابل
    للتحرير — وهو ليس كذلك، بل يتبع أصله.
    """
    out = copy.deepcopy(catalog)
    for entry in out.get(MATERIALS, {}).values():
        if entry.get(DERIVED):
            entry.pop(PRICE, None)
            entry.pop(REASON, None)
    return out


def save_as_new_version(catalog: dict, version: str) -> Path:
    """يكتب نسخة أسعار جديدة. **يرفض الكتابة فوق نسخة موجودة.**"""
    path = catalog_path(version)
    if path.exists():
        raise FileExistsError(
            f"نسخة الأسعار «{version}» موجودة أصلاً، ولا تُكتَب نسخة فوق نسخة: "
            "أوامر العمل التي تشير إليها ستتغيّر كلفتها بلا تنبيه."
        )
    path.write_text(
        json.dumps(strip_derived(catalog), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def editable_rows(catalog: dict) -> list[dict]:
    """كل سعر قابل للتحرير، مصفوفاً للعرض في جدول واحد.

    المادة المشتقّة **تُعرض ولا تُحرَّر**: سعرها يتبع أصله، وتحريرها مباشرةً
    يكسر الاشتقاق. ويظهر سبب اشتقاقها في عمود الملاحظة.
    """
    rows: list[dict] = []
    for name, entry in catalog.get(MATERIALS, {}).items():
        rows.append({
            "الباب": MATERIALS,
            "الاسم": name,
            "الوحدة": entry.get("الوحدة", ""),
            "المفتاح": PRICE,
            "السعر": entry.get(PRICE),
            "محرَّر": not entry.get(DERIVED),
            "ملاحظة": entry.get(REASON, ""),
        })
    for name, entry in catalog.get(LABOUR, {}).items():
        keys = [k for k in DUAL_PRICE_KEYS if k in entry] or [PRICE]
        for key in keys:
            label = {"السعر_مفردة": " (مفردة)", "السعر_مزدوجة": " (مزدوجة)"}.get(key, "")
            rows.append({
                "الباب": LABOUR,
                "الاسم": name + label,
                "الوحدة": entry.get("الوحدة", ""),
                "المفتاح": key,
                "السعر": entry.get(key),
                "محرَّر": True,
                "ملاحظة": entry.get("ملاحظة", ""),
                "الاسم_الأصلي": name,
            })
    return rows


def apply_edits(catalog: dict, edits: list[dict]) -> dict:
    """ينسخ نسخة الأسعار ويطبّق عليها التعديلات، ولا يمسّ الأصل.

    كل تعديل: `{"الباب", "الاسم_الأصلي" أو "الاسم", "المفتاح", "السعر"}`.
    """
    out = copy.deepcopy(catalog)
    for edit in edits:
        section = out[edit["الباب"]]
        name = edit.get("الاسم_الأصلي") or edit["الاسم"]
        if name not in section:
            raise KeyError(f"لا يوجد بند باسم «{name}» في «{edit['الباب']}»")
        section[name][edit["المفتاح"]] = edit["السعر"]
    return out


def differences(old: dict, new: dict) -> list[dict]:
    """كل سعر اختلف بين نسختين — للعرض قبل الاعتماد وعند تحديث أمر عمل.

    والمواد المشتقّة مستثناة: تغيّرها **نتيجة** لتغيّر أصلها لا تعديلاً مستقلاً،
    فإدراجها يضاعف السطور ويوهم بتعديلين حيث تعديل واحد.
    """
    found: list[dict] = []
    for section in (MATERIALS, LABOUR):
        names = sorted(set(old.get(section, {})) | set(new.get(section, {})))
        for name in names:
            before, after = old.get(section, {}).get(name), new.get(section, {}).get(name)
            if before is not None and before.get(DERIVED):
                continue
            if before is None or after is None:
                found.append({"الباب": section, "الاسم": name,
                              "قبل": None if before is None else "—",
                              "بعد": None if after is None else "—",
                              "الحالة": "أُضيف" if before is None else "حُذف"})
                continue
            for key in (PRICE, *DUAL_PRICE_KEYS):
                if key in before or key in after:
                    if before.get(key) != after.get(key):
                        found.append({
                            "الباب": section, "الاسم": name, "المفتاح": key,
                            "قبل": before.get(key), "بعد": after.get(key),
                            "الحالة": "تغيّر",
                        })
    return found
