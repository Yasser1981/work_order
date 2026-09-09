# -*- coding: utf-8 -*-
"""بيانات أمر العمل الرسمي — ترويسة النموذج وأقسامه اليدوية.

المرجع: نموذج MOE / D6-FO-30 في ملف الإكسل الأصلي.
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field
from datetime import date


@dataclass
class StaffRow:
    """سطر في جدول الإشراف الفني."""

    role: str
    count: int | None = None
    days: int | None = None


@dataclass
class EquipmentRow:
    """سطر في جدول الآليات والمعدات."""

    name: str
    count: int | None = None
    days: int | None = None


def default_staff() -> list[StaffRow]:
    """أنواع العاملين كما وردت في النموذج الرسمي."""
    return [StaffRow(r) for r in ("مهندس", "فني", "عامل", "سائق", "محاسب")]


def default_equipment() -> list[EquipmentRow]:
    """أنواع الآليات كما وردت في النموذج الرسمي."""
    return [
        EquipmentRow(n)
        for n in (
            "بيك اب دبل قمارة",
            "بيكب حمل",
            "رافعة",
            "لوري هايب",
            "كرين",
            "شفل",
        )
    ]


def days_in(duration: str) -> int | None:
    """عدد الأيام المستخرَج من نصّ المدة، أو `None` إن لم يكن فيه رقم (ق-٥٥).

    المدة حقل نصّي حرّ («60 يوم»، «90 يوماً»، «شهرين»). فيُقرأ منه **أول عدد
    صحيح**، ولا يُخمَّن شيء إن لم يوجد — «شهرين» تعيد `None`.
    """
    match = re.search(r"\d+", duration or "")
    return int(match.group()) if match else None


@dataclass
class WorkOrder:
    """ترويسة أمر العمل وأقسامه التي تُملأ يدوياً."""

    number: str = ""
    """أمر عمل رقم."""

    order_date: date | None = None
    classification: str = ""
    """التبويب."""

    project_name: str = ""
    """اسم المشروع وموقعه."""

    duration: str = ""
    """المدة اللازمة لتنفيذ العمل."""

    work_scope: str = ""
    """حجم العمل المخطط تنفيذه."""

    start_date: date | None = None
    """تاريخ المباشرة بالعمل."""

    notes: str = ""
    """ملاحظات إضافية."""

    staff: list[StaffRow] = field(default_factory=default_staff)
    equipment: list[EquipmentRow] = field(default_factory=default_equipment)

    # ─────────────── خاصٌّ بقالب «تنفيذ أمانة» (ق-٧٦) ───────────────

    unavailable_materials: list[str] = field(default_factory=list)
    """أسماء المواد غير المتوفرة في المخازن — يؤشّرها المستخدم، ويجمع البرنامج
    كلفتها. تُحفظ **بالاسم** لا بالرقم: ترتيب جدول المواد يتغيّر بتغيّر
    المقاطع، فحفظ الرقم كان يجعل التأشير يشير إلى مادة أخرى بعد أي تعديل."""

    show_material_prices: bool = False
    """هل تُملأ خانتا «سعر المفرد» و«السعر الكلي» في جدول مواد قالب الأمانة.

    الافتراضي **فارغتان** بنصّ المستخدم — والورقة تحمل مع ذلك مجموع كلفة
    المواد، كما في نموذجه المرفوع."""

    preparation_committee: int = 6
    """عدد خطوط التوقيع تحت «لجنة اعداد الكشوفات» (من 3 إلى 6 عادةً)."""

    audit_committee: int = 5
    """عدد خطوط التوقيع تحت «لجنة تدقيق الكشوفات»."""

    organisation: str = "الشركة العامة لتوزيع كهرباء الفرات الأوسط"
    branch: str = "فرع توزيع كهرباء كربلاء المقدسة - قسم التخطيط والتطوير"
    form_code: str = "MOE / D6-FO-30"
