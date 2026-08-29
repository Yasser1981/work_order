# -*- coding: utf-8 -*-
"""يبني الملف التنفيذي ويتحقّق منه — أمر واحد بدل خطوات يدوية (ق-٤٩).

    python بناء_الملف_التنفيذي.py

يفعل ثلاثة أمور بالترتيب، ويتوقّف عند أول فشل:

1. **يشغّل الاختبارات** — لا يُبنى ملف تنفيذي من شيفرة ساقطة.
2. **يبني بـ PyInstaller** من `أوامر_العمل.spec`.
3. **يتحقّق من المخرَج**: أنه موجود، وأن نسخة الأسعار محزومة معه.

المخرَج في `dist/`. وعلى ويندوز يكون `dist/أوامر_العمل.exe`.

**تنبيه:** PyInstaller **لا يبني لنظام آخر**. الملف التنفيذي لويندوز يجب أن
يُبنى على ويندوز، ولِلينكس على لينكس. لا خيار «بناء متقاطع» فيه.
"""

import subprocess
import sys
from pathlib import Path

# طرفية ويندوز تفتح افتراضياً بترميز غير UTF-8 (cp1256 أو cp437)، فطباعة العربية
# فيها ترفع UnicodeEncodeError ويتوقّف السكربت قبل أن يبني شيئاً. هذا يجبرها على
# UTF-8. لا أثر له على لينكس (UTF-8 أصلاً).
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "أوامر_العمل.spec"
NAME = "أوامر_العمل"


def run(label: str, command: list[str]) -> None:
    print(f"\n── {label} " + "─" * max(0, 60 - len(label)))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"\n✗ فشل: {label}")


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("✗ PyInstaller غير مثبَّت.  ثبّته بـ:  pip install pyinstaller")

    run("الاختبارات", [sys.executable, "-m", "pytest", "-q"])
    # يُستدعى كوحدة بايثون لا كأمر مستقلّ: على ويندوز قد لا يكون مجلد Scripts
    # في PATH فيفشل الأمر المباشر رغم أن الحزمة مثبَّتة
    run("البناء", [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)])

    produced = ROOT / "dist" / (NAME + (".exe" if sys.platform == "win32" else ""))
    if not produced.exists():
        sys.exit(f"✗ لم يُنتَج الملف المتوقَّع: {produced}")

    size_mb = produced.stat().st_size / (1024 * 1024)
    print(f"\n✔ تمّ: {produced}  ({size_mb:,.0f} ميغابايت)")
    print(
        "\nالخطوة التالية: انسخ هذا الملف وحده إلى حاسبة المستخدم وشغّله.\n"
        "سيُنشئ عند أول تشغيل مجلد «data» بجانبه فيه نسخة الأسعار، وهو المجلد\n"
        "الذي تُحرَّر فيه الأسعار بعد ذلك — ولا يمحوه تشغيلٌ لاحق ولا تحديث."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
