# -*- coding: utf-8 -*-
"""حفظ أمر العمل وفتحه — ملف `.wo` مستقلّ لكل أمر عمل (ق-٦١).

بنصّ المستخدم: «هذا الأمر مهمّ بالنسبة لي، حتى يتسنّى لي العمل على كل أمر عمل
على حدة وتعديله وتغييره والعودة إليه متى شئت».

## لماذا ملفّ لكل أمر عمل لا قاعدة بيانات واحدة

الملف المستقلّ يُنسخ ويُرسَل بالبريد ويُحفَظ مع مخططات المشروع في مجلده. وقاعدة
البيانات الواحدة تجعل أمر العمل سجلّاً لا يخرج من البرنامج.

## ماذا يُحفَظ

**المدخلات وحدها.** الكميات والكلف **لا تُحفَظ** بل تُحسب عند الفتح — فلو
صُحِّحت قاعدة حسابية (كما صُحّح البراكيت في ق-٦٠) ظهر التصحيح في أوامر العمل
القديمة عند فتحها، ولم تبقَ أرقام خاطئة محفوظة إلى الأبد.

**ويُحفَظ معها اسم نسخة الأسعار** (ق-٤٠). فأمر عمل أُنشئ بأسعار آب يبقى على
أسعار آب مهما حُدِّثت الأسعار بعده — إلا بأمر صريح من المستخدم.

## الصيغة

JSON عربي مقروء بالعين. كل كائن يحمل حقل «نوع» يعرّف صنفه، فالقارئ لا يحتاج إلى
تخمين البنية، والملف يبقى مفهوماً حتى لو فُتح بمحرّر نصوص.

**والترميز مبنيّ على `dataclasses.fields`** لا على قائمة حقول مكتوبة يدوياً:
فأي حقل يُضاف إلى `Network11kV` أو غيرها **يُحفَظ تلقائياً** بلا تعديل هنا، ولا
يضيع صامتاً — وهو خطر حقيقي في الحفظ اليدوي.
"""

from __future__ import annotations

import json

from dataclasses import fields, is_dataclass
from datetime import date
from enum import Enum
from pathlib import Path

from . import equipment as _equipment_module
from . import types as _types_module
from . import workorder as _workorder_module

FILE_KIND = "أمر عمل — نظام أوامر العمل الكهربائية"
"""بصمة تُكتب في رأس الملف ويُتحقَّق منها عند الفتح، فلا يُفتح ملف غريب بصمت."""

FORMAT_VERSION = 1
"""إصدار صيغة الملف. يُرفَع حين تتغيّر البنية تغيّراً لا يقبله القارئ القديم."""

EXTENSION = ".wo"

TYPE_KEY = "نوع"
VALUE_KEY = "قيمة"
ITEMS_KEY = "عناصر"
ENTRIES_KEY = "أزواج"


def _registry() -> dict[str, type]:
    """كل الأصناف التي قد ترد في الملف، مفهرسة باسمها.

    تُجمَع من الوحدات نفسها لا بقائمة مكتوبة يدوياً — فصنف جديد يُضاف إلى
    `engine.types` يصير قابلاً للحفظ والفتح بلا تعديل هنا.
    """
    found: dict[str, type] = {}
    for module in (_types_module, _equipment_module, _workorder_module):
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and (is_dataclass(obj) or issubclass(obj, Enum)):
                found.setdefault(obj.__name__, obj)
    return found


REGISTRY = _registry()


# ───────────────────────────────── الترميز ─────────────────────────────────


def encode(value):
    """يحوّل قيمة بايثون إلى بنية JSON تحمل نوعها معها."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        # يُحفظ **الاسم** لا القيمة: القيمة نصّ عربي معروض قد يُحرَّر يوماً
        # (كما حُرّرت أسماء المواد مراراً)، والاسم البرمجي ثابت.
        return {TYPE_KEY: type(value).__name__, VALUE_KEY: value.name}
    if isinstance(value, date):
        return {TYPE_KEY: "date", VALUE_KEY: value.isoformat()}
    if is_dataclass(value):
        out = {TYPE_KEY: type(value).__name__}
        for f in fields(value):
            out[f.name] = encode(getattr(value, f.name))
        return out
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value):
            return {k: encode(v) for k, v in value.items()}
        # مفاتيح غير نصّية (مفتاح المحولة ثنائيّ: جهد وسعة) ← قائمة أزواج
        return {
            TYPE_KEY: "dict",
            ENTRIES_KEY: [{"مفتاح": encode(k), VALUE_KEY: encode(v)}
                          for k, v in value.items()],
        }
    if isinstance(value, tuple):
        return {TYPE_KEY: "tuple", ITEMS_KEY: [encode(v) for v in value]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    raise TypeError(f"لا أعرف كيف أحفظ قيمة من نوع {type(value).__name__}")


class LoadError(Exception):
    """ملف لا يمكن فتحه — يُبلَّغ عنه بنصّ عربي واضح، ولا يُخمَّن محتواه."""


def decode(data):
    """يعكس `encode`. أي نوع غير معروف يرفع `LoadError` ولا يُتجاهل بصمت."""
    if data is None or isinstance(data, (bool, int, float, str)):
        return data
    if isinstance(data, list):
        return [decode(v) for v in data]
    if not isinstance(data, dict):
        raise LoadError(f"قيمة غير مفهومة في الملف: {data!r}")

    kind = data.get(TYPE_KEY)
    if kind is None:
        return {k: decode(v) for k, v in data.items()}
    if kind == "date":
        return date.fromisoformat(data[VALUE_KEY])
    if kind == "tuple":
        return tuple(decode(v) for v in data[ITEMS_KEY])
    if kind == "dict":
        return {decode(e["مفتاح"]): decode(e[VALUE_KEY]) for e in data[ENTRIES_KEY]}

    cls = REGISTRY.get(kind)
    if cls is None:
        raise LoadError(
            f"الملف يذكر نوعاً لا يعرفه هذا الإصدار من البرنامج: «{kind}». "
            "قد يكون حُفظ بإصدار أحدث."
        )
    if issubclass(cls, Enum):
        try:
            return cls[data[VALUE_KEY]]
        except KeyError as exc:
            raise LoadError(f"قيمة غير معروفة للنوع «{kind}»: {data[VALUE_KEY]}") from exc

    known = {f.name for f in fields(cls)}
    kwargs = {k: decode(v) for k, v in data.items() if k != TYPE_KEY and k in known}
    # حقل موجود في الملف وغير موجود في الصنف ← أُهمل عمداً (ملف من إصدار أحدث).
    # وحقل موجود في الصنف وغائب عن الملف ← يأخذ قيمته الافتراضية (ملف أقدم).
    return cls(**kwargs)


# ─────────────────────────── الحفظ والفتح ───────────────────────────


def document(order, project, price_version: str) -> dict:
    """يبني بنية الملف الكاملة — دالة نقيّة قابلة للاختبار بلا قرص."""
    return {
        "نوع_الملف": FILE_KIND,
        "إصدار_الصيغة": FORMAT_VERSION,
        "نسخة_الأسعار": price_version,
        "أمر_العمل": encode(order),
        "المشروع": encode(project),
    }


def save(path: str | Path, order, project, price_version: str) -> Path:
    """يحفظ أمر العمل في `path` ويعيد المسار الفعلي (بامتداد `.wo`)."""
    path = Path(path)
    if path.suffix.lower() != EXTENSION:
        path = path.with_suffix(EXTENSION)
    text = json.dumps(document(order, project, price_version),
                      ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    return path


def load(path: str | Path) -> tuple[object, object, str]:
    """يفتح ملف `.wo` ويعيد (أمر العمل، المشروع، اسم نسخة الأسعار)."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LoadError(f"الملف ليس ملفَّ أمر عمل سليماً — تعذّرت قراءته:\n{exc}") from exc

    if not isinstance(data, dict) or data.get("نوع_الملف") != FILE_KIND:
        raise LoadError("هذا الملف ليس ملفَّ أمر عمل صادراً عن هذا البرنامج.")

    version = data.get("إصدار_الصيغة")
    if not isinstance(version, int) or version > FORMAT_VERSION:
        raise LoadError(
            f"الملف بصيغة إصدار {version}، وهذا البرنامج يقرأ حتى {FORMAT_VERSION}. "
            "حدّث البرنامج لفتحه."
        )

    order = decode(data["أمر_العمل"])
    project = decode(data["المشروع"])
    price_version = data.get("نسخة_الأسعار") or ""
    return order, project, price_version
