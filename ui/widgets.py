# -*- coding: utf-8 -*-
"""عناصر واجهة مشتركة."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def section(title: str) -> tuple[QGroupBox, QFormLayout]:
    """صندوق مُعنوَن يحوي نموذج حقول."""
    box = QGroupBox(title)
    form = QFormLayout(box)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    form.setFormAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
    form.setHorizontalSpacing(14)
    form.setVerticalSpacing(8)
    return box, form


def number_field(
    minimum: float = 0,
    maximum: float = 1_000_000,
    value: float = 0,
    decimals: int = 0,
    step: float = 1,
    suffix: str = "",
) -> QSpinBox | QDoubleSpinBox:
    """حقل رقمي. يعيد QSpinBox للأعداد الصحيحة و QDoubleSpinBox للكسور."""
    if decimals == 0:
        widget = QSpinBox()
        widget.setRange(int(minimum), int(maximum))
        widget.setValue(int(value))
        widget.setSingleStep(int(step) or 1)
    else:
        widget = QDoubleSpinBox()
        widget.setDecimals(decimals)
        widget.setRange(minimum, maximum)
        widget.setValue(value)
        widget.setSingleStep(step)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setMinimumWidth(120)
    if suffix:
        widget.setSuffix(f"  {suffix}")
    return widget


class HintLabel(QLabel):
    """سطر يشرح كيف تكوّن الرقم — يُعرض تحت الحقول التي تُحسب منها كميات.

    الغرض أن يرى المستخدم المعادلة لا النتيجة وحدها، فيكتشف خطأ الإدخال بنفسه.
    """

    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)
        self.setObjectName("hint")


def separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def scroll_body() -> tuple[QWidget, QVBoxLayout]:
    body = QWidget()
    layout = QVBoxLayout(body)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(12)
    return body, layout
