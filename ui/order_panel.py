# -*- coding: utf-8 -*-
"""لوحة بيانات أمر العمل — ترويسة النموذج الرسمي وأقسامه اليدوية."""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDateEdit,
    QHeaderView,
    QLabel,
    QCheckBox,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from engine.workorder import WorkOrder, days_in, default_equipment, default_staff

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
        self._auto_days: int | None = None
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
        self.start_unset = QCheckBox("غير محدَّد — يُطبع فارغاً")
        form.addRow("تاريخ المباشرة بالعمل:", self.start_date)
        form.addRow("", self.start_unset)
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
        form.addRow(QLabel(
            "العدد يُملأ يدوياً. و«عدد الأيام» ينزل تلقائياً من مدّة أمر العمل، "
            "ويبقى قابلاً للتعديل لكل سطر."
        ))
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
        # الأيام تنزل قبل إشارة التغيير لتصل القيمة الجديدة إلى الطباعة (ق-٥٥)
        self.duration.textChanged.connect(self._sync_days)
        self.start_unset.toggled.connect(self._toggle_start_date)
        self.start_unset.toggled.connect(self.changed)
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

    def _toggle_start_date(self, unset: bool) -> None:
        """يُعطّل حقل التاريخ حين يُختار «غير محدَّد» — فلا يوهم بقيمة تُطبع."""
        self.start_date.setEnabled(not unset)

    DAYS_COLUMN = 2
    """عمود «عدد الأيام» في جدولَي العاملين والآليات."""

    def _sync_days(self) -> None:
        """ينزّل مدّة أمر العمل في عمود الأيام — بلا أن يمحو ما عدّله المستخدم.

        بطلبك (ق-٥٥): «عدد الأيام ينزل تلقائياً وهو نفس عدد أيام أمر العمل».

        **ولا يُكتَب إلا في خلية فارغة أو خلية تحمل المدّة السابقة.** فلو غيّرتَ
        سطراً بعينه إلى 10 أيام ثم غيّرت المدّة، بقي سطرك على 10 ولم يُمحَ.
        """
        days = days_in(self.duration.text())
        previous = self._auto_days
        self._auto_days = days
        if days is None:
            return
        for table in (self.staff, self.equipment):
            for row in range(table.rowCount()):
                box = table.cellWidget(row, self.DAYS_COLUMN)
                if box.value() in (0, previous):
                    box.setValue(days)

    @staticmethod
    def _cell(table: QTableWidget, row: int, col: int) -> int | None:
        """صفر يعني «غير مُدخَل» فيُطبع فارغاً — كما في النموذج الورقي."""
        value = table.cellWidget(row, col).value()
        return value or None

    def load(self, wo: WorkOrder) -> None:
        """يملأ الحقول من أمر عمل محفوظ (ق-٦١) — بإشارة تغيير واحدة في آخره."""
        self.blockSignals(True)
        try:
            self.number.setText(wo.number)
            self.classification.setText(wo.classification)
            if wo.order_date:
                self.order_date.setDate(QDate(wo.order_date.year, wo.order_date.month,
                                              wo.order_date.day))
            self.project_name.setText(wo.project_name)
            self.duration.setText(wo.duration)
            # المدّة تنزّل الأيام تلقائياً (ق-٥٥)، وهنا **المحفوظ أولى**:
            # فلو عدّل المستخدم يوماً بعينه فحُفظ، لا يجوز أن تمحوه المدّة عند
            # الفتح. فتُضبط المدّة أولاً ثم تُكتب الأيام المحفوظة فوقها.
            self._auto_days = days_in(wo.duration)
            self.start_unset.setChecked(wo.start_date is None)
            if wo.start_date:
                self.start_date.setDate(QDate(wo.start_date.year, wo.start_date.month,
                                              wo.start_date.day))
            self.work_scope.setPlainText(wo.work_scope)
            self.notes.setPlainText(wo.notes)
            self._fill_table(self.staff, wo.staff)
            self._fill_table(self.equipment, wo.equipment)
        finally:
            self.blockSignals(False)
        self._toggle_start_date(self.start_unset.isChecked())
        self.changed.emit()

    @staticmethod
    def _fill_table(table: QTableWidget, entries: list) -> None:
        """يكتب العدد والأيام في جدول ثابت الأسماء — والصفر يعني «فارغ»."""
        for row, entry in enumerate(entries):
            if row >= table.rowCount():
                break
            table.cellWidget(row, 1).setValue(entry.count or 0)
            table.cellWidget(row, 2).setValue(entry.days or 0)

    def order(self) -> WorkOrder:
        """يبني كائن أمر العمل من الحقول الحالية."""
        wo = WorkOrder(
            number=self.number.text().strip(),
            order_date=self.order_date.date().toPyDate(),
            classification=self.classification.text().strip(),
            project_name=self.project_name.text().strip(),
            duration=self.duration.text().strip(),
            work_scope=self.work_scope.toPlainText().strip(),
            # التاريخ الفارغ خيار مقصود — أمر العمل قد يصدر قبل تحديد
            # موعد المباشرة (ق-٥٥). والمحرك يقبل None أصلاً.
            start_date=(
                None if self.start_unset.isChecked()
                else self.start_date.date().toPyDate()
            ),
            notes=self.notes.toPlainText().strip(),
        )
        for row, entry in enumerate(wo.staff):
            entry.count = self._cell(self.staff, row, 1)
            entry.days = self._cell(self.staff, row, 2)
        for row, entry in enumerate(wo.equipment):
            entry.count = self._cell(self.equipment, row, 1)
            entry.days = self._cell(self.equipment, row, 2)
        return wo
