# -*- coding: utf-8 -*-
"""قالب «تنفيذ أمانة» — المواد وحدها، ثم العمل المدني، ثم العمل الكهربائي (ق-٧٦).

بنصّ المستخدم: «هو يوضح تفاصيل أمر العمل أكثر من القالب الأول. هو فصل المواد
عن العمل، وفصل العمل المدني عن الكهربائي».

## ثلاثة جداول لا جدولان

| الجدول | ما فيه | الأسعار |
|---|---|---|
| **الأول** | المواد بكمياتها | **فارغة افتراضياً** (بطلبه) |
| **الثاني** | الأعمال المدنية | كاملة، ومجموعها في آخره |
| **الثالث** | الأعمال الكهربائية | كاملة، ومجموعها في آخره |

والفصل بين المدني والكهربائي **ليس جديداً في المحرك**: كل بند أجر يحمل وسم بابه
منذ ق-٣٨، والافتراضي «الأعمال الكهربائية». فهذا القالب **عارضٌ** لتصنيفٍ قائم،
ولا يُعيد تصنيف شيء بنفسه — ولو فعل لاختلف الجدولان بين قالبٍ وقالب.

## الأسعار فارغة والمجموع مذكور

خانتا «سعر المفرد» و«السعر الكلي» في جدول المواد تُتركان فارغتين افتراضياً،
**ومجموع كلفة المواد يُطبع مع ذلك** — كما في النموذج الذي رفعه المستخدم
حرفياً. وتُملآن بخيار صريح في تبويب «أمر العمل».

## تسمية بنود الأعمال المدنية

المحرك يسمّي البند «حفر الخندق — رصيف ترابي، مسار مفرد»: نوع الرصيف **وتعدّد
المسار**، وكلاهما يغيّر السعر. وطلب المستخدم ألّا يظهر تعدّد المسار **في
المطبوع** وأن يبقى ظاهراً **في البرنامج**. فالحذف هنا **عرضٌ فقط**: الاسم في
المحرك وفي شاشة البرنامج وفي ورقة التدقيق يبقى كاملاً.

**وأثرٌ مقصود:** مشروعٌ فيه مقطعان بالرصيف نفسه وتعدّدٍ مختلف يُخرج سطرين
متطابقَي الاسم مختلفَي السعر. وهذا **صحيح لا خطأ** — الكميتان مختلفتان والسعران
مختلفان — ومن أراد سبب الاختلاف وجده في البرنامج.
"""

from __future__ import annotations

import re

from engine.availability import unavailable_summary
from engine.underground import CIVIL_GROUP
from engine.workorder import WorkOrder

from .iso_form import _TABLE, _esc, _fmt_qty, _row, styles

ELECTRICAL_GROUP = "الأعمال الكهربائية"
"""اسم باب الأجور الافتراضي — كل ما ليس مدنيّاً (ق-٣٨)."""

STYLE_LABEL = "أسلوب تنفيذ أمانة"
"""العبارة التي تميّز هذا القالب عن الأول، في عنوانه بنصّ المستخدم."""

NOTES = (
    "تنفيذ العمل حسب المواصفات الفنية المعتمدة لوزارة الكهرباء وتوجيهات المهندس المشرف.",
    "يكون صرف أجور المواد وتنفيذ العمل حسب الذرعة المنفذة الفعلية.",
)
"""ملاحظتان ثابتتان في كل أمر عمل بهذا الأسلوب — بنصّ المستخدم.

وملاحظاته الخاصة تُضاف تحتهما إن كتب شيئاً: «نعم قد تزيد الملاحظات».
"""

PREPARATION_COMMITTEE = "لجنة اعداد الكشف"
AUDIT_COMMITTEE = "لجنة تدقيق الكشف"
"""اسما اللجنتين **بلا أسماء الأعضاء** — بنصّ المستخدم: «تذكر اللجان بدون
الاسماء». وتحت كل واحدة خطوط توقيع فارغة بالعدد الذي يضبطه في أمر العمل."""

SIGNATURES_PER_ROW = 3
"""عدد خطوط التوقيع في السطر الواحد — كما في نموذج المستخدم المرفوع."""

SIGNATURE_LINE = "................"

_MULTIPLICITY = re.compile(r"،\s*مسار\s+\S+\s*$")
"""لاحقة تعدّد المسار في اسم بند الأعمال المدنية — تُحذف من **المطبوع** وحده."""


def printed_labour_name(name: str) -> str:
    """اسم بند الأجر كما يُطبع في هذا القالب: بلا لاحقة تعدّد المسار.

    «حفر الخندق — رصيف ترابي، مسار مفرد» ← «حفر الخندق — رصيف ترابي».
    وما ليس فيه اللاحقة يخرج كما دخل.
    """
    return _MULTIPLICITY.sub("", name).strip()


def split_labour(result: dict) -> tuple[list, list]:
    """(الأعمال المدنية، الأعمال الكهربائية) — بالوسم لا بالاسم.

    **بالوسم لا بالاسم:** تصنيفٌ يقرأ أسماء البنود يكسره أول بند يُعاد تسميته،
    والتسمية تتغيّر (تغيّرت مراراً)، أما الوسم فيضعه المحرك عند التوليد.
    """
    lines = result["أجور_العمل"]
    return (
        [line for line in lines if line.group == CIVIL_GROUP],
        [line for line in lines if line.group != CIVIL_GROUP],
    )


def printed_materials(result: dict) -> list[dict]:
    """صفوف جدول المواد كما تُطبع — **ومنها يُؤخذ ترقيم الفقرات**.

    ترقيم «المواد غير المتوفرة تشمل الفقرات (…)» يُحسب من هذه القائمة نفسها،
    فلا يشير رقمٌ إلى غير ما يقابله في الجدول.
    """
    return [row for row in result["المواد"] if row["الكمية"] > 0]


def _money(value: float) -> str:
    return f"{value:,.0f}"


def _material_rows(materials: list[dict], show_prices: bool) -> str:
    out = []
    for index, row in enumerate(materials, start=1):
        if not show_prices:
            price = total = "&nbsp;"
        elif row["سعر_مفقود"]:
            price = total = "بلا سعر"
        elif row["كمية_فقط"]:
            price = total = "ضمن الأجور"
        else:
            price, total = _money(row["سعر الوحدة"]), _money(row["الكلفة"])
        out.append(_row(
            f'<td align="center">{index}</td>',
            f'<td align="right">{_esc(row["المادة"])}</td>',
            f'<td align="center">{_esc(row["الوحدة"])}</td>',
            f'<td align="center">{_fmt_qty(row["الكمية"])}</td>',
            f'<td align="center">{price}</td>',
            f'<td align="center">{total}</td>',
        ))
    return "\n".join(out)


def _labour_rows(lines: list) -> str:
    """صفوف جدول أجور — بالاسم المطبوع، والأجر المفقود يُكتب ولا يُحسب صفراً."""
    if not lines:
        return _row('<td align="center">&nbsp;</td>', '<td>&nbsp;</td>',
                    '<td>&nbsp;</td>', '<td>&nbsp;</td>',
                    '<td>&nbsp;</td>', '<td>&nbsp;</td>')
    out = []
    for index, line in enumerate(lines, start=1):
        rate = "بلا أجر" if line.rate_missing else _money(line.rate)
        cost = "—" if line.rate_missing else _money(line.cost)
        out.append(_row(
            f'<td align="center">{index}</td>',
            f'<td align="right">{_esc(printed_labour_name(line.name))}</td>',
            f'<td align="center">{_esc(line.unit)}</td>',
            f'<td align="center">{_fmt_qty(line.qty)}</td>',
            f'<td align="center">{rate}</td>',
            f'<td align="center">{cost}</td>',
        ))
    return "\n".join(out)


def _summary_row(label: str, value: str, *, strong: bool = False) -> str:
    """صفٌّ عريض: عنوانٌ يمتدّ على أعمدة الجدول وقيمةٌ في آخره."""
    text = f"<b>{label}</b>" if strong else label
    return _row(f'<td class="k" colspan="5" align="center">{text}</td>',
                f'<td align="center"><b>{value}</b></td>')


def _committee(title: str, slots: int) -> str:
    """عنوان اللجنة وتحته خطوط توقيع فارغة — بلا أسماء (بنصّ المستخدم)."""
    cells = [f'<td align="center">{SIGNATURE_LINE}</td>' for _ in range(max(0, slots))]
    rows = []
    for start in range(0, len(cells), SIGNATURES_PER_ROW):
        chunk = cells[start:start + SIGNATURES_PER_ROW]
        chunk += ['<td>&nbsp;</td>'] * (SIGNATURES_PER_ROW - len(chunk))
        rows.append(_row(*chunk))
    body = "\n".join(rows)
    return f"""<p class="section">{title}</p>
<table width="100%" border="0" cellspacing="0" cellpadding="8">
{body}
</table>"""


def _notes_block(order: WorkOrder) -> str:
    lines = list(NOTES)
    if order.notes:
        lines += [line for line in order.notes.splitlines() if line.strip()]
    items = "".join(f"<br>&nbsp;• {_esc(line)}" for line in lines)
    return f'<p align="right"><b>ملاحظات:</b>{items}</p>'


def header_line(order: WorkOrder) -> str:
    """سطر الجهة: الشركة ثم الفرع، **بلا اسم القسم**.

    حقل `branch` يحمل «فرع توزيع كهرباء كربلاء المقدسة - قسم التخطيط والتطوير»،
    وقسم التخطيط جزءٌ من ترويسة نموذج الإيزو لا من هذا القالب: صيغة المستخدم
    لهذا القالب تنتهي عند اسم الفرع. فيُقصّ ما بعد الشرطة **عرضاً فقط**، ولا
    يُمسّ الحقل المحفوظ.
    """
    branch = order.branch.split(" - ")[0].strip()
    return f"{order.organisation} – {branch}"


def title_line(order: WorkOrder) -> str:
    """«أمر عمل رقم (45) – أسلوب تنفيذ أمانة – اسم المشروع» (بنصّ المستخدم).

    ولا يُذكر التبويب هنا: «لا يحتاج، فقط رقم امر العمل مع عبارة (أسلوب تنفيذ
    أمانة) ثم اسم المشروع».
    """
    parts = [f"أمر عمل رقم ({_esc(order.number)})", STYLE_LABEL]
    if order.project_name:
        parts.append(_esc(order.project_name))
    return " – ".join(parts)


def totals(order: WorkOrder, result: dict) -> dict:
    """المجاميع الخمسة التي تُبنى عليها الورقة — دالة نقيّة قابلة للاختبار.

    **ولماذا تُحسب المجاميع من الجدولين لا من `كلفة_العمل` مباشرة:** لأن جمع
    ما يُطبع هو الذي يُطابق الورقة. ولو حُسب المجموع من طريق آخر لأمكن أن يخرج
    مجموعٌ لا يساوي سطوره — وهو أسوأ خطأ يمكن أن يحمله كشفٌ يُصرف عليه مال.
    """
    civil, electrical = split_labour(result)
    civil_cost = sum(line.cost for line in civil)
    electrical_cost = sum(line.cost for line in electrical)
    labour = civil_cost + electrical_cost
    unavailable = unavailable_summary(printed_materials(result),
                                      order.unavailable_materials)
    return {
        "الأعمال_المدنية": civil_cost,
        "الأعمال_الكهربائية": electrical_cost,
        "أجور_العمل": labour,
        "المواد_غير_المتوفرة": unavailable["الكلفة"],
        "كلفة_المواد": result["كلفة_المواد"],
        "العمل_مع_غير_المتوفرة": labour + unavailable["الكلفة"],
        "العمل_مع_كل_المواد": labour + result["كلفة_المواد"],
        "فقرات_غير_متوفرة": unavailable["فقرات"],
    }


MATERIALS_HEADER = "التفاصيل"
"""عنوان يُعرَّف به جدول المواد بين الجداول — لتكرار صفّ العناوين على الصفحات."""


def build_html(order: WorkOrder, result: dict) -> str:
    """يبني نصّ HTML لأمر العمل بأسلوب تنفيذ أمانة."""
    materials = printed_materials(result)
    civil, electrical = split_labour(result)
    sums = totals(order, result)

    unavailable_line = ""
    if sums["فقرات_غير_متوفرة"]:
        numbers = "، ".join(str(n) for n in sums["فقرات_غير_متوفرة"])
        unavailable_line = _row(
            f'<td colspan="6" align="center">المواد غير المتوفرة تشمل الفقرات '
            f'({numbers})</td>'
        )

    head = _row('<th width="6%">ت</th>', f'<th>{MATERIALS_HEADER}</th>',
                '<th width="10%">الوحدة</th>', '<th width="12%">الكمية</th>',
                '<th width="16%">سعر المفرد د.ع</th>',
                '<th width="18%">السعر الكلي د.ع</th>')

    def labour_table(title: str, lines: list, total: float, total_label: str) -> str:
        # لا عنوان فوق الجدول: **رأس عموده الثاني هو عنوانه** كما في نموذج
        # المستخدم — وعنوانٌ فوقه يكرّر الكلمة نفسها مرّتين متجاورتين.
        return f"""<p class="gap">&nbsp;</p>
<table {_TABLE}>
  {_row('<th width="6%">ت</th>', f'<th>{title}</th>',
        '<th width="10%">الوحدة</th>', '<th width="12%">الكمية</th>',
        '<th width="16%">سعر المفرد د.ع</th>', '<th width="18%">السعر الكلي د.ع</th>')}
{_labour_rows(lines)}
  {_summary_row(total_label, _money(total), strong=True)}
</table>"""

    return f"""<html><head><meta charset="utf-8"><style>{styles()}</style></head>
<body dir="rtl">
<p align="center" class="h1">{_esc(header_line(order))}</p>
<p align="center" class="title">{title_line(order)}</p>
<p class="gap">&nbsp;</p>

<table {_TABLE}>
  {head}
{_material_rows(materials, order.show_material_prices)}
  {unavailable_line}
  {_summary_row("الكلفة التخمينية للمواد غير المتوفرة",
                _money(sums["المواد_غير_المتوفرة"]))}
  {_summary_row("الكلفة التخمينية الكلية للمواد", _money(sums["كلفة_المواد"]),
                strong=True)}
</table>

{labour_table("الأعمال المدنية", civil, sums["الأعمال_المدنية"],
              "مجموع اجور عمل الاعمال المدنية")}

{labour_table("الأعمال الكهربائية", electrical, sums["الأعمال_الكهربائية"],
              "مجموع اجور عمل الاعمال الكهربائية")}

<p class="gap">&nbsp;</p>
<table {_TABLE}>
  {_summary_row("مجموع اجور العمل (الاعمال الكهربائية + الاعمال المدنية)",
                _money(sums["أجور_العمل"]))}
  {_summary_row("مجموع أجور العمل + كلفة المواد غير المتوفرة",
                _money(sums["العمل_مع_غير_المتوفرة"]))}
  {_summary_row("مجموع أجور العمل + كلفة المواد الكلية",
                _money(sums["العمل_مع_كل_المواد"]), strong=True)}
</table>

{_notes_block(order)}

{_committee(PREPARATION_COMMITTEE, order.preparation_committee)}
{_committee(AUDIT_COMMITTEE, order.audit_committee)}
</body></html>"""


def document(order: WorkOrder, result: dict):
    """المستند جاهزاً للطباعة — بتكرار عناوين جدول المواد على الصفحات (ق-٦٨)."""
    from PyQt6.QtGui import QTextDocument

    from .iso_form import _rtl_option, repeat_header_rows

    doc = QTextDocument()
    doc.setDefaultStyleSheet(styles())
    doc.setDefaultTextOption(_rtl_option())
    doc.setHtml(build_html(order, result))
    repeat_header_rows(doc, MATERIALS_HEADER)
    return doc


def write_pdf(order: WorkOrder, result: dict, path: str) -> str:
    """يكتب الورقة ملفَّ PDF بمقاس A4 عمودي — كنظيره في قالب الإيزو."""
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter

    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Portrait)
    writer.setPageMargins(QMarginsF(14, 14, 14, 16), QPageLayout.Unit.Millimeter)
    writer.setResolution(150)

    doc = document(order, result)
    doc.setPageSize(writer.pageLayout().paintRectPixels(writer.resolution()).size().toSizeF())
    doc.print(writer)
    return path
