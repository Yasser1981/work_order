# -*- coding: utf-8 -*-
"""بيانات أمر العمل الرسمي — ترويسة النموذج وأقسامه اليدوية.

المرجع: نموذج MOE / D6-FO-30 في ملف الإكسل الأصلي.
"""

from __future__ import annotations

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

    organisation: str = "الشركة العامة لتوزيع كهرباء الفرات الأوسط"
    branch: str = "فرع توزيع كهرباء كربلاء المقدسة - قسم التخطيط والتطوير"
    form_code: str = "MOE / D6-FO-30"
