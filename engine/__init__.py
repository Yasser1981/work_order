# -*- coding: utf-8 -*-
"""محرك حساب أمر العمل الكهربائي."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_catalog(version: str = "2026-08") -> dict:
    """يحمّل نسخة الأسعار والأجور.

    أمر العمل يحفظ اسم النسخة المستخدمة فيه، فلا تتغيّر كلفة أوامر العمل القديمة عند
    تحديث الأسعار (ق-٠).
    """
    path = DATA_DIR / f"catalog_{version}.json"
    return json.loads(path.read_text(encoding="utf-8"))
