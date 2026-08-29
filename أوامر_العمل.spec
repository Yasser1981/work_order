# -*- mode: python ; coding: utf-8 -*-
"""مواصفة بناء الملف التنفيذي — PyInstaller (ق-٤٩).

**نمط الملف الواحد** (`--onefile`): ملف تنفيذي واحد يُنسخ ويُشغَّل بلا تنصيب.

**ومجلد البيانات خارجه لا داخله** — وهذا جوهر ما بُني في ق-٢٨. لولاه لضاع كل
تعديل يجريه المستخدم على الأسعار مع أول إغلاق، لأن PyInstaller يفكّ محتوى
الحزمة في مجلد مؤقّت يُمسح عند الخروج. فنسخة الأسعار تُحزَم للقراءة فقط
(«نسخة المصنع»)، وتُنسخ عند أول تشغيل إلى مجلد `data` بجانب الملف التنفيذي،
ومنه يقرأ البرنامج ويكتب بعد ذلك.

**البناء:**  pyinstaller --noconfirm أوامر_العمل.spec
**المخرَج:** dist/أوامر_العمل  (وعلى ويندوز: dist/أوامر_العمل.exe)
"""

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    # نسخة المصنع من الأسعار — للقراءة فقط، تُنسخ إلى مجلد المستخدم عند أول تشغيل
    datas=[("data", "data")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # حزم ثقيلة لا يستوردها البرنامج — استبعادها يقلّص الحجم كثيراً
    excludes=["pandas", "numpy", "matplotlib", "pytest", "tkinter", "PyQt6.QtWebEngineCore"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="أوامر_العمل",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # لا نافذة طرفية سوداء خلف البرنامج على ويندوز
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
