# -*- coding: utf-8 -*-
"""إخراج أمر العمل بقالب الإيزو الرسمي — MOE / D6-FO-30.

A4 عمودي، من اليمين لليسار، مع ترقيم صفحات تلقائي عند تجاوز المواد صفحة واحدة
(الملف الأصلي كان يقطع ما زاد عن 35 مادة بلا تحذير).

**جدول المواد لا يحمل أسعاراً** — النموذج الرسمي جدول كميات لا جدول كلف. أما الكلفة
التخمينية فتظهر رقماً واحداً في الترويسة.
"""

from __future__ import annotations

import html
from datetime import date

from engine.workorder import WorkOrder

ARABIC_FONTS = (
    # ويندوز — مرتَّبة بحسب ملاءمتها للمستند الرسمي (ق-٥١)
    "Simplified Arabic",
    "Traditional Arabic",
    "Tahoma",            # يُشحن مع كل ويندوز منذ XP، وعربيّته ممتازة
    "Arial",
    # لينكس — بيئة التطوير
    "Noto Naskh Arabic",
    "FreeSerif",
    "DejaVu Sans",
)
"""ترتيب تفضيل الخطوط العربية للطباعة.

**المشكلة التي يحلّها هذا (ق-٥١):** كانت القائمة `FreeSerif, Noto Naskh Arabic`
وكلاهما **خطّ لينكس لا يُشحن مع ويندوز**. فعلى حاسبة المستخدم كان الاختيار يسقط
إلى `serif` العامّ — أي Times New Roman، وعربيّته ضعيفة في المستندات الرسمية.
وهو خلل لا يظهر إلا **بعد** البناء والتسليم، كنظير خلل مجلد البيانات في ق-٢٨.
"""


def available_arabic_font(families: list[str] | None = None) -> str:
    """أول خطّ عربي متاح فعلاً على هذا الجهاز، أو `serif` إن لم يتوفّر شيء.

    يُقرأ من `QFontDatabase` وقت التشغيل لا وقت البناء، فيختار الخطّ الأنسب على
    ويندوز وعلى لينكس بلا شيفرة خاصة بكل نظام.

    **ولا يُستدعى `QFontDatabase` بلا `QApplication` قائمة** — استدعاؤها حينها
    **يُسقط العملية بـ Abort** لا برفع استثناء يمكن التقاطه. فيُعاد `serif`
    عندئذٍ. وهذا لا يمسّ الطباعة الفعلية: `write_pdf` تحتاج `QApplication` أصلاً،
    فالخطّ يُحلّ دائماً في المسار الحقيقي.
    """
    if families is None:
        from PyQt6.QtGui import QFontDatabase
        from PyQt6.QtWidgets import QApplication

        if QApplication.instance() is None:
            return "serif"
        families = QFontDatabase.families()
    installed = set(families)
    for name in ARABIC_FONTS:
        if name in installed:
            return name
    return "serif"


# ملاحظة: QTextDocument يدعم مجموعة محدودة من CSS ويتجاهل width على الجداول.
# لذلك تُضبط أعراض الجداول والمحاذاة بخصائص HTML مباشرة، لا بالأنماط.
_CSS = """
/* اتجاه المستند من اليمين إلى اليسار (ق-٥٤).
   `direction` على **الجدول** هو الذي يقلب ترتيب الأعمدة فعلاً في محرّك
   QTextDocument. جُرِّبت بدائل أربعة فلم تنفع: `dir="rtl"` على الجدول،
   و`dir` على body، و`QTextTableFormat.setLayoutDirection`، وضبط اتجاه
   الإطار الجذر. و`setDefaultTextOption(RightToLeft)` يضبط اتجاه النصّ
   داخل الفقرة ولا يمسّ ترتيب الأعمدة. */
body     { font-family: %FONT%, serif; font-size: 11pt; direction: rtl; }
table    { direction: rtl; }
th       { background-color: #e8e8e8; font-weight: bold; }
.k       { font-weight: bold; background-color: #f4f4f4; }
.section { font-weight: bold; font-size: 12pt; }
.code    { font-size: 9pt; }
.h1      { font-size: 14pt; font-weight: bold; }
.h2      { font-size: 11pt; }
.title   { font-size: 15pt; font-weight: bold; }
"""


def styles(extra: str = "") -> str:
    """أنماط المستند بعد استبدال `%FONT%` بأول خطّ عربي متاح (ق-٥١).

    تُستدعى **وقت الطباعة** لا وقت الاستيراد، لأن `QFontDatabase` تحتاج
    `QApplication` قائمة.
    """
    return (_CSS + extra).replace("%FONT%", f"'{available_arabic_font()}'")

_TABLE = 'width="100%" border="1" cellspacing="0" cellpadding="4"'


def _fmt_qty(value: float) -> str:
    """كمية بلا كسور زائدة: 31.5 تبقى 31.5 و21.0 تصير 21."""
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def _fmt_date(value: date | None) -> str:
    return value.strftime("%Y/%m/%d") if value else ""


def _esc(value: str) -> str:
    return html.escape(value or "")


def build_html(order: WorkOrder, result: dict) -> str:
    """يبني نصّ HTML لأمر العمل جاهزاً للطباعة أو التحويل إلى PDF."""
    materials = [row for row in result["المواد"] if row["الكمية"] > 0]
    total = result["الكلفة_الكلية"]

    rows = "\n".join(
        f'<tr><td align="center">{i}</td>'
        f'<td align="right">{_esc(row["المادة"])}</td>'
        f'<td align="center">{_esc(row["الوحدة"])}</td>'
        f'<td align="center">{_fmt_qty(row["الكمية"])}</td></tr>'
        for i, row in enumerate(materials, start=1)
    )

    staff_rows = "\n".join(
        f'<tr><td align="center">{i}</td><td align="right">{_esc(s.role)}</td>'
        f'<td align="center">{s.count if s.count is not None else "&nbsp;"}</td>'
        f'<td align="center">{s.days if s.days is not None else "&nbsp;"}</td></tr>'
        for i, s in enumerate(order.staff, start=1)
    )

    equip_rows = "\n".join(
        f'<tr><td align="center">{i}</td><td align="right">{_esc(e.name)}</td>'
        f'<td align="center">{e.count if e.count is not None else "&nbsp;"}</td>'
        f'<td align="center">{e.days if e.days is not None else "&nbsp;"}</td></tr>'
        for i, e in enumerate(order.equipment, start=1)
    )

    return f"""<html><head><meta charset="utf-8"><style>{styles()}</style></head>
<body dir="rtl">
<p align="center" class="h1">{_esc(order.organisation)}</p>
<p align="center" class="h2">{_esc(order.branch)}</p>
<p align="left" class="code">{_esc(order.form_code)}</p>

<p align="center" class="title">أمر عمل رقم {_esc(order.number)}</p>

<table {_TABLE}>
  <tr><td class="k" width="22%">التبويب</td><td width="28%">{_esc(order.classification)}</td>
      <td class="k" width="20%">التاريخ</td><td>{_fmt_date(order.order_date)}</td></tr>
  <tr><td class="k">اسم المشروع وموقعه</td><td colspan="3">{_esc(order.project_name)}</td></tr>
  <tr><td class="k">المدة اللازمة لتنفيذ العمل</td><td colspan="3">{_esc(order.duration)}</td></tr>
  <tr><td class="k">الكلفة التخمينية للمواد + العمل</td>
      <td colspan="3"><b>{total:,.0f}</b> دينار</td></tr>
  <tr><td class="k">حجم العمل المخطط تنفيذه</td><td colspan="3">{_esc(order.work_scope)}</td></tr>
  <tr><td class="k">تاريخ المباشرة بالعمل</td><td colspan="3">{_fmt_date(order.start_date)}</td></tr>
</table>

<p class="section">أ - جدول المواد المخمنة</p>
<table {_TABLE}>
  <tr><th width="7%">ت</th><th>اسم المادة</th>
      <th width="18%">الوحدة القياسية</th><th width="16%">الكمية</th></tr>
{rows}
</table>

<p class="section">ب - الاشراف الفني</p>
<table {_TABLE}>
  <tr><th width="7%">ت</th><th>نوع العاملين</th>
      <th width="20%">العدد</th><th width="20%">عدد الأيام</th></tr>
{staff_rows}
</table>

<p class="section">ج - الاليات والمعدات</p>
<table {_TABLE}>
  <tr><th width="7%">ت</th><th>نوع الآلية</th>
      <th width="20%">الرقم</th><th width="20%">عدد الأيام</th></tr>
{equip_rows}
</table>

<p class="section">ملاحظات إضافية</p>
<table {_TABLE}>
  <tr><td height="60" valign="top" align="right">{_esc(order.notes) or "&nbsp;"}</td></tr>
</table>

<br>
<table width="100%" border="0" cellspacing="0" cellpadding="10">
  <tr><td align="center">مُعِدّ أمر العمل</td>
      <td align="center">مدير القسم</td>
      <td align="center">المصادقة</td></tr>
  <tr><td align="center">.....................</td>
      <td align="center">.....................</td>
      <td align="center">.....................</td></tr>
</table>
</body></html>"""


def write_pdf(order: WorkOrder, result: dict, path: str) -> str:
    """يكتب أمر العمل ملفَّ PDF بمقاس A4 عمودي مع ترقيم صفحات تلقائي."""
    from PyQt6.QtCore import QMarginsF, Qt
    from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Portrait)
    writer.setPageMargins(QMarginsF(14, 14, 14, 16), QPageLayout.Unit.Millimeter)
    writer.setResolution(150)

    doc = QTextDocument()
    doc.setDefaultStyleSheet(styles())
    doc.setDefaultTextOption(_rtl_option())
    doc.setHtml(build_html(order, result))
    doc.setPageSize(writer.pageLayout().paintRectPixels(writer.resolution()).size().toSizeF())
    doc.print(writer)
    return path


def _rtl_option():
    from PyQt6.QtGui import QTextOption
    from PyQt6.QtCore import Qt

    option = QTextOption()
    option.setTextDirection(Qt.LayoutDirection.RightToLeft)
    return option
