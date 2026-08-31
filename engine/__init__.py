# -*- coding: utf-8 -*-
"""محرك حساب أمر العمل الكهربائي."""

import json

from .paths import (  # noqa: F401  — تُعاد تصديرها للواجهة وأدوات الصيانة
    catalog_path,
    catalog_versions,
    ensure_user_data,
    latest_catalog_version,
    user_data_dir,
)


def load_catalog(version: str | None = None) -> dict:
    """يحمّل نسخة الأسعار والأجور. `None` تعني أحدث نسخة متاحة.

    أمر العمل يحفظ اسم النسخة المستخدمة فيه، فلا تتغيّر كلفة أوامر العمل القديمة عند
    تحديث الأسعار (ق-٠).

    تُقرأ من مجلد المستخدم لا من داخل الحزمة، فيبقى تعديل الأسعار ممكناً بعد بناء
    الملف التنفيذي (ق-٢٨).
    """
    if version is None:
        version = latest_catalog_version()

    path = catalog_path(version)
    if not path.exists():
        available = "، ".join(catalog_versions()) or "لا شيء"
        raise FileNotFoundError(
            f"نسخة الأسعار «{version}» غير موجودة في {user_data_dir()}."
            f" المتاح: {available}"
        )
    return _resolve_derived_prices(json.loads(path.read_text(encoding="utf-8")))


def _resolve_derived_prices(catalog: dict) -> dict:
    """يحسب الأسعار المشتقّة: سعر مادة = سعر أخرى ناقص سعر ثالثة (ق-٥٨).

    **السبب:** سعر العمود المثبَّت في السوق هو سعره **مورَّداً بملحقاته**، والعمود
    العاري = ذاك ناقص سعر براكيته. فلو خُزّن الرقمان مستقلَّين لانفصلا عند أول
    تحديث أسعار — يُحدَّث أحدهما ويُنسى الآخر.

    فالمشتقّ يُحسب عند كل تحميل، ويبقى **الرقم الأصل وحده** قابلاً للتحرير في
    نسخة الأسعار. والصيغة تُكتب في حقل «سبب» فتظهر لمن يقرأ الملف.
    """
    prices = catalog.get("المواد", {})
    for name, entry in prices.items():
        rule = entry.get("مشتقّ")
        if not rule:
            continue
        base = prices.get(rule["من"], {}).get("السعر")
        minus = prices.get(rule["ناقص"], {}).get("السعر")
        if base is None or minus is None:
            entry["السعر"] = None      # ناقص أحد طرفيه ← يُبلَّغ عنه لا يُخمَّن
            continue
        entry["السعر"] = base - minus
        entry["سبب"] = (
            f"مشتقّ: «{rule['من']}» {base:,} ناقص «{rule['ناقص']}» {minus:,}"
            f" = {entry['السعر']:,}"
        )
    return catalog
