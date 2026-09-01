# -*- coding: utf-8 -*-
"""ورقة التدقيق — المواد مع تفصيل مصدر كل كمية، وفقرات العمل بأسعارها.

**ليست للتسليم الرسمي.** غرضها أن يتتبّع المدقّق كل رقم إلى مصدره: من أين جاءت
كمية البراكيت، وكيف تكوّنت كلفة التنفيذ. النموذج الرسمي (قالب الإيزو) يبقى
كما هو بلا زيادة.
"""

from __future__ import annotations

from collections import OrderedDict

from engine.workorder import WorkOrder

from .iso_form import _esc, _fmt_date, _fmt_qty, _row, styles, _TABLE, _rtl_option

_EXTRA = """
.src   { font-size: 9pt; color: #444; }
.tot   { font-weight: bold; background-color: #f0f0f0; }
.grp   { font-weight: bold; background-color: #e8e8e8; }
.sub   { font-weight: bold; }
.note  { font-size: 9pt; }
"""




def _price_version_line(result: dict) -> str:
    """سطر نسخة الأسعار — يجيب سؤال المدقّق «بأي أسعار حُسبت هذه الورقة؟».

    ورقتان بالأرقام نفسها وبنسختَي أسعار مختلفتين ورقتان مختلفتان. بلا هذا السطر
    لا سبيل لمعرفة أيّهما، ولا لإعادة إنتاج الورقة بعد تحديث الأسعار (ق-٤٠).
    """
    version = result.get("نسخة_الأسعار") or ""
    if not version:
        return "⚠ نسخة الأسعار غير مسجَّلة في هذه النتيجة"
    return f"محسوبة بنسخة الأسعار: {_esc(version)}"


def _labour_table(lines: list) -> str:
    """صفوف جدول الأجور مبوّبةً بـ `group`، ولكل باب صفّ مجموع.

    البنود بلا وسم هي **الأعمال الكهربائية** وهي الأصل، فتتصدّر. الأبواب الموسومة
    تليها بترتيب أول ظهورها. الباب الواحد لا يُطبع عنوانه إن كان الوحيد — لا معنى
    لتبويب جدول من باب واحد.
    """
    groups: "OrderedDict[str, list]" = OrderedDict()
    for line in lines:
        groups.setdefault(line.group or "الأعمال الكهربائية", []).append(line)

    rows: list[str] = []
    index = 0
    for name, members in groups.items():
        if len(groups) > 1:
            rows.append(_row(f'<td colspan="5" align="right"><b>{_esc(name)}</b></td>',
                             attrs=' class="grp"'))
        for line in members:
            index += 1
            rows.append(_row(
                f'<td align="center">{index}</td>',
                f'<td align="right">{_esc(line.name)}</td>',
                f'<td align="center">{_fmt_qty(line.qty)} {_esc(line.unit)}</td>',
                # الأجر المفقود يُطبع نصّاً لا صفراً — الصفر يوهم بأن البند مجّاني
                f'<td align="center">'
                f'{"بلا أجر" if line.rate_missing else f"{line.rate:,.0f}"}</td>',
                f'<td align="center">'
                f'{"—" if line.rate_missing else f"{line.cost:,.0f}"}</td>',
            ))
        if len(groups) > 1:
            subtotal = sum(line.cost for line in members)
            rows.append(_row(
                f'<td colspan="4" align="right">مجموع {_esc(name)}</td>',
                f'<td align="center">{subtotal:,.0f}</td>', attrs=' class="sub"'))
    return "\n".join(rows)


def build_html(order: WorkOrder, result: dict) -> str:
    """يبني ورقة التدقيق: كل كمية ومصادرها، وكل فقرة عمل وكلفتها."""
    materials = [row for row in result["المواد"] if row["الكمية"] > 0]

    material_rows = []
    for i, row in enumerate(materials, start=1):
        parts = row["تفصيل"]
        if row["سعر_مفقود"]:
            price, cost = "غير مُسعَّر", "—"
        elif row["كمية_فقط"]:
            price, cost = "ضمن الأجور", "—"
        else:
            price = f"{row['سعر الوحدة']:,.0f}"
            cost = f"{row['الكلفة']:,.0f}"

        span = f' rowspan="{len(parts)}"'
        material_rows.append(_row(
            f'<td align="center"{span}>{i}</td>',
            f'<td align="right"{span}>{_esc(row["المادة"])}</td>',
            f'<td align="center"{span}>{_esc(row["الوحدة"])}</td>',
            f'<td align="center"{span}><b>{_fmt_qty(row["الكمية"])}</b></td>',
            f'<td align="center">{_fmt_qty(parts[0]["الكمية"])}</td>',
            f'<td align="right" class="src">{_esc(parts[0]["المصدر"])}</td>',
            f'<td align="center"{span}>{price}</td>',
            f'<td align="center"{span}>{cost}</td>',
        ))
        for part in parts[1:]:
            material_rows.append(_row(
                f'<td align="center">{_fmt_qty(part["الكمية"])}</td>',
                f'<td align="right" class="src">{_esc(part["المصدر"])}</td>',
            ))

    # فقرات العمل مبوّبة: الأعمال الكهربائية أولاً ثم الأعمال المدنية، ولكل باب
    # مجموعه. عبور الشوارع ضمن المدنية بنصّ المستخدم (ق-٣٨).
    labour_rows = _labour_table(result["أجور_العمل"])

    notes = []
    if result["أسعار_مفقودة"]:
        notes.append("مواد بلا سعر: " + "، ".join(result["أسعار_مفقودة"]))
    if result.get("أجور_مفقودة"):
        notes.append("بنود بلا أجر: " + "، ".join(result["أجور_مفقودة"]))
    warning = ""
    if notes:
        warning = (
            f'<p class="note"><b>تنبيه — لم تُحتسب في المجموع:</b> '
            f'{_esc(" · ".join(notes))}</p>'
        )

    # جدول المقاطع: يسبق جدول المواد لأنه مفتاح قراءة عمود «المصدر» بعده
    segments_block = ""
    segments = result.get("المقاطع") or []
    named = [s for s in segments if s.name]
    if named:
        rows = "\n".join(
            _row(f'<td align="center">{i}</td>',
                 f'<td align="right">{_esc(s.name)}</td>',
                 f'<td align="right">{_esc(s.kind.value)}</td>')
            for i, s in enumerate(named, start=1)
        )
        segments_block = f"""<p class="section">مقاطع المشروع</p>
<table {_TABLE}>
  {_row('<th width="6%">ت</th>', '<th width="44%">اسم المقطع</th>', '<th>نوعه</th>')}
{rows}
</table>
"""

    return f"""<html><head><meta charset="utf-8"><style>{styles(_EXTRA)}</style></head>
<body dir="rtl">
<p align="center" class="h1">ورقة تدقيق أمر العمل</p>
<p align="center" class="h2">{_esc(order.project_name)}</p>
<p align="center" class="note">أمر عمل رقم {_esc(order.number)} &nbsp;·&nbsp;
   {_fmt_date(order.order_date)} &nbsp;·&nbsp; للمراجعة الداخلية لا للتسليم الرسمي</p>
<p align="center" class="note">{_price_version_line(result)}</p>

{segments_block}
<p class="section">أ - المواد وتفصيل مصادر كمياتها</p>
<table {_TABLE}>
  {_row('<th width="5%">ت</th>', '<th>اسم المادة</th>', '<th width="9%">الوحدة</th>',
        '<th width="9%">الكمية</th>', '<th width="8%">منها</th>',
        '<th width="30%">المصدر</th>', '<th width="10%">سعر الوحدة</th>',
        '<th width="12%">الكلفة</th>')}
{chr(10).join(material_rows)}
  {_row('<td colspan="7" align="right">مجموع كلفة المواد</td>',
        f'<td align="center">{result["كلفة_المواد"]:,.0f}</td>', attrs=' class="tot"')}
</table>
{warning}

<p class="section">ب - فقرات العمل</p>
<table {_TABLE}>
  {_row('<th width="5%">ت</th>', '<th>الفقرة</th>', '<th width="18%">الكمية</th>',
        '<th width="16%">السعر الوحدي</th>', '<th width="18%">الكلفة</th>')}
{labour_rows}
  {_row('<td colspan="4" align="right">مجموع أجور التنفيذ</td>',
        f'<td align="center">{result["كلفة_العمل"]:,.0f}</td>', attrs=' class="tot"')}
</table>

<table {_TABLE}>
  {_row('<td align="right">الكلفة الكلية (مواد + عمل)</td>',
        f'<td width="30%" align="center">{result["الكلفة_الكلية"]:,.0f} دينار</td>',
        attrs=' class="tot"')}
</table>
</body></html>"""


def write_pdf(order: WorkOrder, result: dict, path: str) -> str:
    """يكتب ورقة التدقيق ملفَّ PDF بمقاس A4 **أفقي** — لأن أعمدتها أكثر."""
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
    writer.setResolution(150)

    doc = QTextDocument()
    doc.setDefaultStyleSheet(styles(_EXTRA))
    doc.setDefaultTextOption(_rtl_option())
    doc.setHtml(build_html(order, result))
    doc.setPageSize(writer.pageLayout().paintRectPixels(writer.resolution()).size().toSizeF())
    doc.print(writer)
    return path
