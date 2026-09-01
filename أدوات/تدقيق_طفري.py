# -*- coding: utf-8 -*-
"""تدقيق طفري لاختبارات الطباعة — يُشغَّل بـ `python3 أدوات/تدقيق_طفري.py` (ق-٧٠).

**لماذا وُجد:** الاختبار الذي يمرّ لا يثبت أنه يحرس شيئاً. وقد مرّ في هذا
المشروع حارسٌ نائم شهراً كاملاً (ق-٥٤): كان يتحقّق من وجود قاعدة في الأنماط،
والقاعدة موجودة، والنموذج يُطبع مقلوباً — حتى كشفه المستخدم بعينه.

**كيف يعمل:** يكسر كل خاصية شكلية عمداً، ويُشغّل اختبارات الطباعة، ويسجّل أيّ
طفرة **نجت**. والناجية إمّا خاصية غير محروسة، وإمّا طفرة لا تكسر شيئاً — والفرق
بينهما يُحسم بالفحص لا بالتخمين، ويُسجَّل في ق-٧٠.

**يُعاد تشغيله** كلّما أُضيف حارس شكلي جديد، أو تغيّر القالب تغييراً بنيوياً.
وهو **خارج مجموعة الاختبارات** عمداً: يعدّل ملفات المصدر ويستغرق دقيقة، فلا
يصلح أن يعمل في كل دفعة.
"""

import io
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = "tests/test_templates.py tests/test_iso_form.py tests/test_ui.py"

ISO = "printing/iso_form.py"
AUDIT = "printing/audit_sheet.py"
SHEET = "printing/spreadsheet.py"

# (وسم، ملف، النصّ الأصلي، البديل) — كل طفرة تكسر خاصيةً يدّعي حارسٌ حراستها
MUTATIONS = [
    # ── الاتجاه وترتيب الأعمدة (ق-٦٤) ──
    ("ق-٦٤ لا قلب للأعمدة", ISO,
     'return f"<tr{attrs}>" + "".join(reversed(cells)) + "</tr>"',
     'return f"<tr{attrs}>" + "".join(cells) + "</tr>"'),
    ("ق-٥٤ حذف direction من الأنماط", ISO,
     "direction: rtl; }\ntable    { direction: rtl; }",
     "}\ntable    { }"),
    ("ق-٥٤ حذف اتجاه المستند RightToLeft", ISO,
     "option.setTextDirection(Qt.LayoutDirection.RightToLeft)",
     "option.setTextDirection(Qt.LayoutDirection.LeftToRight)"),

    # ── الأسطر الصفرية (ق-٦٤) ──
    ("ق-٦٤ إبقاء الأسطر الصفرية", ISO,
     '[s for s in order.staff if s.count]', 'list(order.staff)'),
    ("ق-٦٤ إبقاء الآليات الصفرية", ISO,
     '[e for e in order.equipment if e.count]', 'list(order.equipment)'),
    ("ق-٦٤ الترقيم لا يُعاد", ISO,
     'for i, entry in enumerate(entries, start=1)',
     'for i, entry in enumerate(entries, start=7)'),

    # ── سطر الكلفة (ق-٦٥) ──
    ("ق-٦٥ قلب المواد والعمل", ISO,
     'f\'كلفة المواد التخمينية {result["كلفة_المواد"]:,.0f} + \'\n        f\'كلفة العمل التخمينية {result["كلفة_العمل"]:,.0f} = \'',
     'f\'كلفة العمل التخمينية {result["كلفة_العمل"]:,.0f} + \'\n        f\'كلفة المواد التخمينية {result["كلفة_المواد"]:,.0f} = \''),
    ("ق-٦٥ مجموع لا يجمع", ISO,
     'f\'الكلفة التخمينية الكلية <b>{result["الكلفة_الكلية"]:,.0f}</b> د.ع\'',
     'f\'الكلفة التخمينية الكلية <b>{result["الكلفة_الكلية"] + 5:,.0f}</b> د.ع\''),
    ("ق-٦٥ حذف وحدة د.ع", ISO, '</b> د.ع\'', '</b>\''),

    # ── التواقيع (ق-٦٦) ──
    ("ق-٦٦ قلب ترتيب الموقّعين", ISO,
     '_row(*(f\'<td align="center">{name}</td>\' for name in SIGNATURES))',
     '_row(*(f\'<td align="center">{name}</td>\' for name in reversed(SIGNATURES)))'),
    ("ق-٦٦ حذف موقّع", ISO, '    "مسؤول التخطيط",\n', ''),
    ("ق-٦٦ حذف خطوط التوقيع", ISO,
     "'<td align=\"center\">................</td>'",
     "'<td align=\"center\">&nbsp;</td>'"),

    # ── التخطيط المتجاور وتكرار العناوين (ق-٦٨) ──
    ("ق-٦٨ حذف تكرار العناوين من الطباعة", ISO,
     "    repeat_header_rows(doc, MATERIALS_HEADER)\n", ""),
    ("ق-٦٨ تكرار العناوين على كل الجداول", ISO,
     "        if marker in heads:", "        if True:"),
    ("ق-٦٨ إلغاء التجاور", ISO,
     '<td width="55%" valign="top">', '<td width="55%" valign="top"></td></tr><tr><td>'),

    # ── الفراغات (ق-٦٩) ──
    ("ق-٦٩ حذف الفاصل الأوسط", ISO,
     "GUTTER = '<td width=\"2%\">&nbsp;</td>'", "GUTTER = ''"),
    ("ق-٦٩ حذف الفراغ تحت الترويسة", ISO,
     '</table>\n<p class="gap">&nbsp;</p>\n', '</table>\n'),

    # ── الخطّ العربي (ق-٥١، ق-٥٣) ──
    ("ق-٥١ خطّ لاتيني أولاً", ISO,
     'ARABIC_FONTS = (\n    # ويندوز', 'ARABIC_FONTS = (\n    "Bitstream Charter",\n    # ويندوز'),
    ("ق-٥١ إلغاء استبدال %FONT%", ISO,
     'return (_CSS + extra).replace("%FONT%", f"\'{available_arabic_font()}\'")',
     'return (_CSS + extra).replace("%FONT%", "serif")'),

    # ── محتوى جدول المواد ──
    ("جدول المواد يحمل أسعاراً", ISO,
     "f'<td align=\"center\">{_fmt_qty(row[\"الكمية\"])}</td>')",
     "f'<td align=\"center\">{_fmt_qty(row[\"الكمية\"])} سعر {row[\"سعر الوحدة\"]}</td>')"),
    ("مواد الكمية صفر تُطبع", ISO,
     'materials = [row for row in result["المواد"] if row["الكمية"] > 0]',
     'materials = list(result["المواد"])'),
    ("الكميات الكسرية تُبتَر", ISO,
     'return f"{value:,.3f}".rstrip("0").rstrip(".")', 'return f"{int(value):,}"'),
    ("تاريخ فارغ يصير تاريخ اليوم", ISO,
     'return value.strftime("%Y/%m/%d") if value else ""',
     'from datetime import date as _d\n    return (value or _d.today()).strftime("%Y/%m/%d")'),
    ("محارف HTML لا تُهرَّب", ISO,
     'return html.escape(value or "")', 'return value or ""'),

    # ── ورقة التدقيق ──
    ("تدقيق: حذف سطر نسخة الأسعار", AUDIT,
     '{_price_version_line(result)}', ''),
    ("تدقيق: الأجر المفقود يصير صفراً", AUDIT,
     'f\'{"بلا أجر" if line.rate_missing else f"{line.rate:,.0f}"}</td>\',',
     'f\'{0 if line.rate_missing else line.rate:,.0f}</td>\','),
    ("تدقيق: حذف مجاميع الأبواب", AUDIT,
     "        if len(groups) > 1:\n            subtotal", "        if False:\n            subtotal"),
    ("تدقيق: حذف جدول المقاطع", AUDIT,
     '        segments_block = f"""<p class="section">مقاطع المشروع</p>',
     '        segments_block = f"""<p class="section">مقاطع</p>'),

    # ── تصدير إكسل ──
    ("إكسل: كلفة المواد رقم لا معادلة", SHEET,
     'cost = sheet.cell(row, 6, f"=D{row}*E{row}")',
     'cost = sheet.cell(row, 6, 0)'),
    ("إكسل: مجموع المواد رقم لا معادلة", SHEET,
     'formula=f"=SUM(F2:F{row - 1})" if row > 2 else 0)', 'formula=0)'),
    ("إكسل: كلفة الأجور رقم لا معادلة", SHEET,
     'cost = sheet.cell(row, 7, f"=D{row}*F{row}")',
     'cost = sheet.cell(row, 7, 0)'),
    ("إكسل: إلغاء اتجاه الورقة", SHEET,
     'sheet.sheet_view.rightToLeft = True', 'sheet.sheet_view.rightToLeft = False'),
]


def run_tests() -> bool:
    """True إن نجحت كل الاختبارات (أي أن الطفرة **مرّت** بلا أن تُكشَف)."""
    for cache in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    result = subprocess.run(
        f"cd {ROOT} && QT_QPA_PLATFORM=offscreen python3 -m pytest {TESTS} -q -x",
        shell=True, capture_output=True, text=True, timeout=300,
    )
    return result.returncode == 0


def main() -> int:
    survivors, killed, inapplicable = [], [], []
    for label, rel, old, new in MUTATIONS:
        path = ROOT / rel
        original = io.open(path, encoding="utf-8").read()
        if original.count(old) != 1:
            inapplicable.append((label, original.count(old)))
            print(f"⊘ {label}  (لم يُطبَّق: {original.count(old)} تطابق)")
            continue
        io.open(path, "w", encoding="utf-8").write(original.replace(old, new, 1))
        try:
            passed = run_tests()
        finally:
            io.open(path, "w", encoding="utf-8").write(original)
        (survivors if passed else killed).append(label)
        print(f"{'⚠️ نجت' if passed else '✅ كُشفت'}  {label}")

    for cache in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    print(f"\n{'═' * 60}")
    print(f"كُشفت: {len(killed)}  ·  نجت: {len(survivors)}  ·  لم تُطبَّق: {len(inapplicable)}")
    if survivors:
        print("\n⚠️ طفرات نجت — خصائص غير محروسة:")
        for label in survivors:
            print(f"   • {label}")
    if inapplicable:
        print("\n⊘ لم تُطبَّق (النصّ تغيّر):")
        for label, count in inapplicable:
            print(f"   • {label}  ({count} تطابق)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
