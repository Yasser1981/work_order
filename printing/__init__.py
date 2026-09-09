# -*- coding: utf-8 -*-
"""قوالب إخراج أمر العمل.

المحرك يُنتج **بيانات** (نتيجة `compute`)، والقالب مجرّد **عارض** لها. لذلك يمكن
لمشروع واحد أن يُخرَج بأي عدد من القوالب، ويختار المستخدم المناسب لكل حالة.

لإضافة قالب جديد: أنشئ وحدة فيها `build_html(order, result) -> str` و
`write_pdf(order, result, path) -> str`، ثم سجّلها هنا. لا يُمسّ المحرك.

**وتصدير الإكسل يتبع القالب المختار** (ق-٧٦): لكل قالب `write_xlsx` خاصّته،
فزرّ «تصدير إلى إكسل» يُخرج ورقة القالب الذي على الشاشة لا ورقةً واحدة لكل
القوالب.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from engine.workorder import WorkOrder


@dataclass(frozen=True)
class Template:
    """قالب إخراج واحد."""

    key: str
    name: str
    description: str
    build_html: Callable[[WorkOrder, dict], str]
    write_pdf: Callable[[WorkOrder, dict, str], str]
    write_xlsx: Callable[[WorkOrder, dict, str], str]
    """كاتب ورقة الإكسل لهذا القالب — يُستدعى من زرّ التصدير."""


_REGISTRY: dict[str, Template] = {}


def register(template: Template) -> Template:
    if template.key in _REGISTRY:
        raise ValueError(f"القالب «{template.key}» مسجَّل مسبقاً")
    _REGISTRY[template.key] = template
    return template


def get(key: str) -> Template:
    if key not in _REGISTRY:
        raise KeyError(f"لا يوجد قالب بالمفتاح «{key}»")
    return _REGISTRY[key]


def available() -> list[Template]:
    """القوالب المتاحة بترتيب تسجيلها."""
    return list(_REGISTRY.values())


def _register_builtin() -> None:
    from . import amana_form, amana_sheet, audit_sheet, iso_form, spreadsheet

    register(
        Template(
            key="iso",
            name="قالب الإيزو الرسمي",
            description="النموذج الرسمي MOE / D6-FO-30 — المواد وكمياتها والكلفة "
                        "الكلية، بلا تفصيل فقرات العمل.",
            build_html=iso_form.build_html,
            write_pdf=iso_form.write_pdf,
            write_xlsx=spreadsheet.write_xlsx,
        )
    )
    register(
        Template(
            key="audit",
            name="ورقة التدقيق",
            description="المواد مع تفصيل مصدر كل كمية، وفقرات العمل بأسعارها "
                        "وكلفها — للمراجعة الداخلية لا للتسليم الرسمي.",
            build_html=audit_sheet.build_html,
            write_pdf=audit_sheet.write_pdf,
            # ورقة التدقيق للقراءة لا للتحرير، فتصديرها إكسلاً يُخرج ورقة
            # أمر العمل نفسها — وهو ما كان يفعله الزرّ قبل ق-٧٦ بلا استثناء.
            write_xlsx=spreadsheet.write_xlsx,
        )
    )
    register(
        Template(
            key="amana",
            name="قالب تنفيذ أمانة",
            description="المواد وحدها، ثم الأعمال المدنية، ثم الأعمال الكهربائية "
                        "— كلٌّ بمجموعه، مع المواد غير المتوفرة ولجنتَي الكشف.",
            build_html=amana_form.build_html,
            write_pdf=amana_form.write_pdf,
            write_xlsx=amana_sheet.write_xlsx,
        )
    )


_register_builtin()
