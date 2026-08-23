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
    return json.loads(path.read_text(encoding="utf-8"))
