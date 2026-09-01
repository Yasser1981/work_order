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
/* فراغ يفصل عنوان القسم عمّا فوقه وعمّا تحته — كانت الجداول تلتصق
   بالترويسة وبعناوينها فتبدو كتلةً واحدة (ق-٦٩) */
.section { font-weight: bold; font-size: 12pt;
           margin-top: 12px; margin-bottom: 5px; }
.code    { font-size: 9pt; }
/* سطر فاصل رفيع. الهامش العلوي يُلغى في رأس خلية الجدول، فلا يُبعد عنوان
   القسم عن الترويسة فوقه — والفقرة الفارغة تفعلها في كل الحالات (ق-٦٩) */
.gap     { font-size: 4pt; }
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


def _row(*cells: str, attrs: str = "") -> str:
    """صفُّ جدول يُكتب بترتيبه المنطقي ويُخرَج **مقلوباً**، فأولى خلاياه يمينُه.

    **لماذا القلب في الشيفرة لا في CSS (ق-٦٤):** محرّك `QTextDocument` **لا
    يقلب ترتيب أعمدة الجدول** بـ`direction: rtl` — يقلب اتجاه النصّ داخل الخلية
    وحده. وكان ق-٥٤ يظنّ أن القاعدة تكفي، وهو استنتاج خاطئ ظهر على أول أمر عمل
    مطبوع: عمود «ت» في أقصى اليسار و«الكمية» في أقصى اليمين، عكس النموذج الرسمي.

    فالقلب هنا **حسابي لا اعتمادَ فيه على محرّك العرض**، فيخرج الترتيب نفسه على
    ويندوز ولينكس وأي إصدار من Qt. ويحرسه اختبار **هندسي** يقيس مواضع الأعمدة
    في المستند المرسوم فعلاً، فلو غيّر Qt سلوكه يوماً سقط الاختبار ولم ينقلب
    النموذج الرسمي صامتاً.
    """
    return f"<tr{attrs}>" + "".join(reversed(cells)) + "</tr>"


def _fmt_qty(value: float) -> str:
    """كمية بلا كسور زائدة: 31.5 تبقى 31.5 و21.0 تصير 21."""
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def _fmt_date(value: date | None) -> str:
    return value.strftime("%Y/%m/%d") if value else ""


def _esc(value: str) -> str:
    return html.escape(value or "")


SIGNATURES = (
    "مسؤول القطاع",
    "مسؤول التنفيذ",
    "مسؤول الفنية",
    "مسؤول التخطيط",
    "مدير الفرع",
)
"""أسماء التذييل التي توقّع أمر العمل، بترتيبها من اليمين (ق-٦٦).

بنصّ المستخدم. وكانت ثلاثة عناوين عامّة («مُعِدّ أمر العمل، مدير القسم،
المصادقة») لم تأتِ من النموذج الرسمي بل كانت تقديراً منّي في أول بناء.
والترتيب من اليمين إلى اليسار هو ترتيب التوقيع صعوداً إلى مدير الفرع.
"""


def _cost_line(result: dict) -> str:
    """سطر الكلفة التخمينية مفصَّلاً في سطر واحد (ق-٦٥).

    بنصّ المستخدم: «كلفة المواد التخمينية (المبلغ) + كلفة العمل التخمينية
    (المبلغ) = الكلفة التخمينية الكلية (المجموع) د.ع».

    فيرى المدقّق الشقّين والمجموع معاً بلا فتح ورقة التدقيق، ويتحقّق من الجمع
    بنظرة واحدة.

    **ولا تُغلَّف `+` و`=` بعلامات اتجاه.** بنيتُها أولاً بعلامات RLM خشية أن
    تنتقل — فهي محارف محايدة في خوارزمية BiDi تأخذ اتجاهها من جيرانها — ثم
    رسمتُ السطر مع العلامات وبدونها فخرجا **متطابقين**: اتجاه الفقرة مضبوط
    RTL، وهو وحده يكفي لحسم موضع المحايدات. فحُذفت: محارف غير مرئية في المستند
    خطرٌ في ذاتها (تنتقل مع النسخ وتُفسد البحث فيه)، ولا تُدفَع كلفتها بلا أثر
    مقيس. **ويحرس الترتيبَ اختبار هندسي** يقيس موضع كل مبلغ في السطر المرسوم.
    """
    return (
        f'كلفة المواد التخمينية {result["كلفة_المواد"]:,.0f} + '
        f'كلفة العمل التخمينية {result["كلفة_العمل"]:,.0f} = '
        f'الكلفة التخمينية الكلية <b>{result["الكلفة_الكلية"]:,.0f}</b> د.ع'
    )


def _people_rows(entries: list, label_field: str) -> str:
    """صفوف جدولَي الإشراف الفني والآليات — المُدخَل وحده، بلا أسطر صفرية.

    وحين لا يُدخَل شيء يبقى **صفٌّ فارغ واحد**، فيحتفظ النموذج بشكله ولا يظهر
    جدولاً برأس بلا جسم كأنّ الطباعة انقطعت.
    """
    if not entries:
        return _row('<td align="center">&nbsp;</td>', '<td>&nbsp;</td>',
                    '<td>&nbsp;</td>', '<td>&nbsp;</td>')
    return "\n".join(
        _row(f'<td align="center">{i}</td>',
             f'<td align="right">{_esc(getattr(entry, label_field))}</td>',
             f'<td align="center">{entry.count}</td>',
             f'<td align="center">{entry.days if entry.days is not None else "&nbsp;"}</td>')
        for i, entry in enumerate(entries, start=1)
    )


def build_html(order: WorkOrder, result: dict) -> str:
    """يبني نصّ HTML لأمر العمل جاهزاً للطباعة أو التحويل إلى PDF."""
    # المحرّك لا يُخرج مادةً بكمية صفر أصلاً، فهذا **دفاع في العمق** لا شرط
    # عامل — ولذلك لا يحرسه اختبار: لا مُدخَل يجعله يعمل (ق-٧٠)
    materials = [row for row in result["المواد"] if row["الكمية"] > 0]

    rows = "\n".join(
        _row(f'<td align="center">{i}</td>',
             f'<td align="right">{_esc(row["المادة"])}</td>',
             f'<td align="center">{_esc(row["الوحدة"])}</td>',
             f'<td align="center">{_fmt_qty(row["الكمية"])}</td>')
        for i, row in enumerate(materials, start=1)
    )

    # السطر بلا عدد لا يُطبع (ق-٦٤). النموذج الورقي يُملأ باليد فتبقى فيه أسطر
    # فارغة، أما المطبوع فيُظهر ما استُخدم فعلاً: خمسة أنواع عاملين وستّ آليات
    # معظمها أصفار تُطيل الجدول ولا تحمل معلومة.
    staff_rows = _people_rows([s for s in order.staff if s.count], "role")
    equip_rows = _people_rows([e for e in order.equipment if e.count], "name")

    return f"""<html><head><meta charset="utf-8"><style>{styles()}</style></head>
<body dir="rtl">
<p align="center" class="h1">{_esc(order.organisation)}</p>
<p align="center" class="h2">{_esc(order.branch)}</p>
<p align="left" class="code">{_esc(order.form_code)}</p>

<p align="center" class="title">أمر عمل رقم {_esc(order.number)}</p>

<table {_TABLE}>
  {_row('<td class="k" width="22%">التبويب</td>',
        f'<td width="28%">{_esc(order.classification)}</td>',
        '<td class="k" width="20%">التاريخ</td>',
        f'<td>{_fmt_date(order.order_date)}</td>')}
  {_row('<td class="k">اسم المشروع وموقعه</td>',
        f'<td colspan="3">{_esc(order.project_name)}</td>')}
  {_row('<td class="k">المدة اللازمة لتنفيذ العمل</td>',
        f'<td colspan="3">{_esc(order.duration)}</td>')}
  {_row('<td class="k">الكلفة التخمينية للمواد + العمل</td>',
        f'<td colspan="3">{_cost_line(result)}</td>')}
  {_row('<td class="k">حجم العمل المخطط تنفيذه</td>',
        f'<td colspan="3">{_esc(order.work_scope)}</td>')}
  {_row('<td class="k">تاريخ المباشرة بالعمل</td>',
        f'<td colspan="3">{_fmt_date(order.start_date)}</td>')}
</table>
<p class="gap">&nbsp;</p>

<table width="100%" border="0" cellspacing="0" cellpadding="0">
  {_row(f'''<td width="55%" valign="top">
    <p class="section">أ - جدول المواد المخمنة</p>
    <table {_TABLE}>
      {_row('<th width="7%">ت</th>', '<th>اسم المادة</th>',
            '<th width="20%">الوحدة القياسية</th>', '<th width="18%">الكمية</th>')}
    {rows}
    </table>
  </td>''',
        GUTTER,
        f'''<td valign="top">
    <p class="section">ب - الاشراف الفني</p>
    <table {_TABLE}>
      {_row('<th width="8%">ت</th>', '<th>نوع العاملين</th>',
            '<th width="22%">العدد</th>', '<th width="24%">عدد الأيام</th>')}
    {staff_rows}
    </table>

    <p class="section">ج - الاليات والمعدات</p>
    <table {_TABLE}>
      {_row('<th width="8%">ت</th>', '<th>نوع الآلية</th>',
            '<th width="22%">الرقم</th>', '<th width="24%">عدد الأيام</th>')}
    {equip_rows}
    </table>

    <p class="section">ملاحظات إضافية</p>
    <table {_TABLE}>
      <tr><td height="70" valign="top" align="right">{_esc(order.notes) or "&nbsp;"}</td></tr>
    </table>
  </td>''')}
</table>

<br>
<table width="100%" border="0" cellspacing="0" cellpadding="6">
  {_row(*(f'<td align="center">{name}</td>' for name in SIGNATURES))}
  {_row(*('<td align="center">................</td>' for _ in SIGNATURES))}
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

    doc = document(order, result)
    doc.setPageSize(writer.pageLayout().paintRectPixels(writer.resolution()).size().toSizeF())
    doc.print(writer)
    return path


GUTTER = '<td width="2%">&nbsp;</td>'
"""خلية فاصلة بين عمودَي التخطيط (ق-٦٩).

الفراغ في **الوسط وحده**. وحشوةُ الخلايا (`cellpadding`) كانت ستضعه في الجهات
الأربع فتُزيح حدود الجداول عن أطراف الورقة وتضيق المتاح للأسماء الطويلة.
"""


MATERIALS_HEADER = "اسم المادة"
"""عنوان يُعرَّف به جدول المواد بين الجداول — أثبت من ترتيبه بينها."""


def document(order: WorkOrder, result: dict):
    """المستند جاهزاً للطباعة: أنماطه واتجاهه وتكرار عناوينه (ق-٦٨).

    **مفصولة عن `write_pdf` عمداً:** الطباعة تحتاج `QPdfWriter` وملفاً على
    القرص، فلا يمكن لاختبار أن يتحقّق مما فيها. وبنائها هنا يجعل كل خطوة
    تحضيرية مقيسةً — ولولا ذلك لمرّ حذفُ `repeat_header_rows` بلا أن يسقط
    اختبار، وقد جرّبتُه فمرّ فعلاً.
    """
    from PyQt6.QtGui import QTextDocument

    doc = QTextDocument()
    doc.setDefaultStyleSheet(styles())
    doc.setDefaultTextOption(_rtl_option())
    doc.setHtml(build_html(order, result))
    repeat_header_rows(doc, MATERIALS_HEADER)
    return doc


def repeat_header_rows(doc, marker: str) -> int:
    """يجعل صفّ العناوين يتكرّر في كل صفحة، ويعيد عدد الجداول التي عُولجت (ق-٦٨).

    **قارئ الملف يفصله عن صفّ العناوين ورقةٌ كاملة.** جدول مواد فيه 90 مادة
    يمتدّ على صفحتين، فتخرج الثانية بأعمدة بلا عناوين: أربعة أرقام لا يُعرف
    أيّها الكمية وأيّها الوحدة.

    **ولا يفعل ذلك `<th>` وحده:** مستورد HTML في Qt لا يضبط `headerRowCount`
    منه، فيُضبط هنا بعد التحميل. والجدول يُعرَّف بنصّ في صفّه الأول لا بترتيبه
    بين الجداول — فترتيبه يتغيّر بأي إضافة، ونصّ عنوانه لا يتغيّر إلا بقرار.
    """
    from PyQt6.QtGui import QTextTable

    treated = 0
    pending = list(doc.rootFrame().childFrames())
    while pending:                       # **بحث متداخل**: جدول المواد صار داخل
        frame = pending.pop()            # جدول التخطيط (ق-٦٨)، فلا يكفي المستوى
        pending.extend(frame.childFrames())   # الأول من `rootFrame`
        if not isinstance(frame, QTextTable):
            continue
        heads = [frame.cellAt(0, c).firstCursorPosition().block().text().strip()
                 for c in range(frame.columns())]
        if marker in heads:
            fmt = frame.format()
            fmt.setHeaderRowCount(1)
            frame.setFormat(fmt)
            treated += 1
    return treated


def _rtl_option():
    """اتجاه المستند الافتراضي.

    **قِيس أثره فوجِد صفراً (ق-٧٠):** رُسمت الورقة بـ`RightToLeft` وبـ
    `LeftToRight` فخرجت الصورتان **متطابقتين بايتاً ببايت**، حتى في فقرة نصّ
    حرّ تخلط عربيةً بأرقام وترقيم. فترتيب الأعمدة يحسمه `_row`، والمحاذاة
    يحسمها `align` في كل خلية، واتجاه الفقرة يحسمه أول حرف قويّ فيها.

    **ويبقى** لأن إزالته لا تربح شيئاً وقد تختلف على منصّة لم أقِس عليها.
    وهذا التوثيق هو المقصود: لئلا يُظنّ يوماً أنه يضبط ما لا يضبطه — كما ظُنّ
    في ق-٥٤ بقاعدة `direction: rtl`.
    """
    from PyQt6.QtGui import QTextOption
    from PyQt6.QtCore import Qt

    option = QTextOption()
    option.setTextDirection(Qt.LayoutDirection.RightToLeft)
    return option
