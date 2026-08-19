# -*- coding: utf-8 -*-
"""لوحة بيانات أمر العمل — ترويسة النموذج الرسمي وأقسامه اليدوية."""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDateEdit,
    QHeaderView,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from engine.workorder import WorkOrder, default_equipment, default_staff

from .widgets import scroll_body, section


def _date_edit(value: date | None = None) -> QDateEdit:
    widget = QDateEdit()
    widget.setCalendarPopup(True)
    widget.setDisplayFormat("yyyy/MM/dd")
    widget.setDate(QDate(value.year, value.month, value.day) if value else QDate.currentDate())
    return widget


class OrderPanel(QWidget):
    """حقول أمر العمل التي تُملأ يدوياً وتظهر في النموذج المطبوع."""

    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._build()
        self._connect()

    def _build(self) -> None:
        body, layout = scroll_body()

        box, form = section("ترويسة أمر العمل")
        self.number = QLineEdit()
        self.number.setPlaceholderText("مثال: 45")
        self.classification = QLineEdit()
        self.classification.setPlaceholderText("مثال: توسعات")
        self.order_date = _date_edit()
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("اسم المشروع وموقعه")
        self.duration = QLineEdit()
        self.duration.setPlaceholderText("مثال: 90 يوم")
        self.start_date = _date_edit()
        form.addRow("أمر عمل رقم:", self.number)
        form.addRow("التبويب:", self.classification)
        form.addRow("التاريخ:", self.order_date)
        form.addRow("اسم المشروع وموقعه:", self.project_name)
        form.addRow("المدة اللازمة للتنفيذ:", self.duration)
        form.addRow("تاريخ المباشرة بالعمل:", self.start_date)
        layout.addWidget(box)

        box, form = section("حجم العمل المخطط تنفيذه")
        self.work_scope = QTextEdit()
        self.work_scope.setMaximumHeight(70)
        form.addRow(self.work_scope)
        layout.addWidget(box)

        box, form = section("ب - الاشراف الفني")
        self.staff = self._people_table(
            [s.role for s in default_staff()], ["نوع العاملين", "العدد", "عدد الأيام"]
        )
        form.addRow(self.staff)
        form.addRow(QLabel("تُملأ يدوياً — لا يحسبها البرنامج."))
        layout.addWidget(box)

        box, form = section("ج - الاليات والمعدات")
        self.equipment = self._people_table(
            [e.name for e in default_equipment()], ["نوع الآلية", "الرقم", "عدد الأيام"]
        )
        form.addRow(self.equipment)
        layout.addWidget(box)

        box, form = section("ملاحظات إضافية")
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        form.addRow(self.notes)
        layout.addWidget(box)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    @staticmethod
    def _people_table(names: list[str], headers: list[str]) -> QTableWidget:
        """جدول بأسماء ثابتة وعمودَي عدد قابلين للتحرير."""
        table = QTableWidget(len(names), 3)
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setMinimumHeight(28 * len(names) + 34)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for row, name in enumerate(names):
            item = QTableWidgetItem(name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 0, item)
            for col in (1, 2):
                spin = QSpinBox()
                spin.setRange(0, 999)
                spin.setSpecialValueText(" ")   # الصفر يُعرض فارغاً كما في النموذج الورقي
                spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setCellWidget(row, col, spin)
        return table

    def _connect(self) -> None:
        for w in (self.number, self.classification, self.project_name, self.duration):
            w.textChanged.connect(self.changed)
        for w in (self.order_date, self.start_date):
            w.dateChanged.connect(self.changed)
        for w in (self.work_scope, self.notes):
            w.textChanged.connect(self.changed)
        for table in (self.staff, self.equipment):
            for row in range(table.rowCount()):
                for col in (1, 2):
                    table.cellWidget(row, col).valueChanged.connect(self.changed)

    @staticmethod
    def _cell(table: QTableWidget, row: int, col: int) -> int | None:
        """صفر يعني «غير مُدخَل» فيُطبع فارغاً — كما في النموذج الورقي."""
        value = table.cellWidget(row, col).value()
        return value or None

    def order(self) -> WorkOrder:
        """يبني كائن أمر العمل من الحقول الحالية."""
        wo = WorkOrder(
            number=self.number.text().strip(),
            order_date=self.order_date.date().toPyDate(),
            classification=self.classification.text().strip(),
            project_name=self.project_name.text().strip(),
            duration=self.duration.text().strip(),
            work_scope=self.work_scope.toPlainText().strip(),
            start_date=self.start_date.date().toPyDate(),
            notes=self.notes.toPlainText().strip(),
        )
        for row, entry in enumerate(wo.staff):
            entry.count = self._cell(self.staff, row, 1)
            entry.days = self._cell(self.staff, row, 2)
        for row, entry in enumerate(wo.equipment):
            entry.count = self._cell(self.equipment, row, 1)
            entry.days = self._cell(self.equipment, row, 2)
        return wo
