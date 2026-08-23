# -*- coding: utf-8 -*-
"""أين يجد البرنامج ملفاته — في التطوير وفي الملف التنفيذي.

المشكلة التي يحلّها هذا الملف: PyInstaller بنمط الملف الواحد يفكّ البرنامج في
**مجلد مؤقّت يُمسح عند الإغلاق**. فلو قرأ البرنامج أسعاره من داخل الحزمة، لضاع كل
تعديل يجريه المستخدم عليها مع أول إغلاق — وهو خلل لا يظهر إلا **بعد** التسليم.

الحل: مجلدان لا واحد.

| المجلد | أين | لمن |
|---|---|---|
| **المرافق** (bundled) | داخل الحزمة، للقراءة فقط | نسخة المصنع من الأسعار |
| **المستخدم** (user) | بجانب الملف التنفيذي | النسخة العاملة، قابلة للتعديل |

عند أول تشغيل تُنسخ نسخة المصنع إلى مجلد المستخدم إن لم تكن موجودة. وبعدها يقرأ
البرنامج من مجلد المستخدم وحده، فتبقى تعديلاته باقية عبر التحديثات.

**في التطوير المجلدان واحد** (`data/` في المستودع)، فلا نسخ ولا ازدواج.

المرجع: ق-٢٨ في docs/سجل_القرارات.md
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

APP_FOLDER_NAME = "أوامر_العمل"
"""اسم مجلد البيانات الاحتياطي حين يتعذّر الكتابة بجانب الملف التنفيذي."""


def is_frozen() -> bool:
    """هل نعمل من داخل ملف تنفيذي مبنيّ بـ PyInstaller؟"""
    return getattr(sys, "frozen", False)


def bundled_data_dir() -> Path:
    """مجلد نسخة المصنع — داخل الحزمة عند التجميد، ومجلد المستودع عند التطوير."""
    if is_frozen():
        # _MEIPASS هو المجلد المؤقّت الذي يفكّ فيه PyInstaller محتوى الحزمة
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "data"
    return Path(__file__).resolve().parent.parent / "data"


def _is_writable(folder: Path) -> bool:
    """يختبر الكتابة فعلياً بدل الاعتماد على الصلاحيات المعلنة.

    ويندوز يعلن صلاحيات لا يحترمها دائماً (Program Files و«الملفات المحمية»)،
    فالاختبار الوحيد الموثوق أن نكتب ملفاً ونحذفه.
    """
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".اختبار_الكتابة"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def user_data_dir() -> Path:
    """مجلد البيانات العامل — الذي يقرأ منه البرنامج ويكتب فيه.

    عند التطوير: `data/` في المستودع.
    عند التجميد: مجلد `data` بجانب الملف التنفيذي، فإن تعذّرت الكتابة هناك
    (كأن يوضع البرنامج في Program Files) فمجلد باسم البرنامج في مجلد المستخدم.
    """
    if not is_frozen():
        return bundled_data_dir()

    beside_exe = Path(sys.executable).resolve().parent / "data"
    if _is_writable(beside_exe):
        return beside_exe
    return Path.home() / APP_FOLDER_NAME / "data"


def ensure_user_data() -> Path:
    """ينسخ نسخة المصنع إلى مجلد المستخدم عند أول تشغيل، ويعيد مجلد المستخدم.

    **لا يستبدل ملفاً موجوداً أبداً** — تعديلات المستخدم على الأسعار أعلى من نسخة
    المصنع، ولا يجوز أن يمحوها تحديثٌ للبرنامج (ق-٠).
    """
    target = user_data_dir()
    source = bundled_data_dir()
    if target == source:
        return target

    target.mkdir(parents=True, exist_ok=True)
    for item in sorted(source.glob("*.json")):
        destination = target / item.name
        if not destination.exists():
            shutil.copy2(item, destination)
    return target


def catalog_versions() -> list[str]:
    """نسخ الأسعار المتاحة، من الأقدم إلى الأحدث.

    التسمية `catalog_YYYY-MM.json` تجعل الترتيب الأبجدي ترتيباً زمنياً.
    """
    folder = ensure_user_data()
    return sorted(p.stem.removeprefix("catalog_") for p in folder.glob("catalog_*.json"))


def latest_catalog_version() -> str:
    """أحدث نسخة أسعار متاحة."""
    versions = catalog_versions()
    if not versions:
        raise FileNotFoundError(
            f"لا توجد أي نسخة أسعار في {user_data_dir()} — "
            "المتوقَّع ملف باسم catalog_YYYY-MM.json"
        )
    return versions[-1]


def catalog_path(version: str) -> Path:
    """مسار ملف نسخة أسعار بعينها."""
    return ensure_user_data() / f"catalog_{version}.json"
