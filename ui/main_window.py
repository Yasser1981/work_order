# -*- coding: utf-8 -*-
"""النافذة الرئيسية — مدخلات الشبكة الهوائية ونتائجها الحيّة."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engine.overhead import compute
from engine.types import OverheadProject

from .panels import Panel11kV, Panel33kV

STYLE = """
QWidget       { font-size: 13px; }
QGroupBox     { font-weight: 600; border: 1px solid palette(mid);
                border-radius: 6px; margin-top: 10px; padding: 14px 10px 10px 10px; }
/* في التخطيط من اليمين لليسار يجب تثبيت موضع العنوان صراحةً، وإلا قُطع أوّله */
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top right;
                   padding: 0 10px; }
QLabel#hint   { color: palette(dark); background: palette(alternate-base);
                border-radius: 4px; padding: 6px 8px; }
QLabel#total  { font-size: 15px; font-weight: 700; }
QPushButton   { padding: 6px 14px; border-radius: 5px; }
"""


class MainWindow(QMainWindow):
    def __init__(self, catalog: dict) -> None:
        super().__init__()
        self.catalog = catalog
        self._rows: list[dict] = []
        self.setWindowTitle("نظام أوامر العمل الكهربائية — الشبكة الهوائية")
        self.resize(1500, 950)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setStyleSheet(STYLE)
        self._build()
        self.recalculate()

    def _build(self) -> None:
        self.panel11 = Panel11kV(self.catalog)
        self.panel33 = Panel33kV(self.catalog)
        self.panel11.changed.connect(self.recalculate)
        self.panel33.changed.connect(self.recalculate)

        tabs = QTabWidget()
        tabs.addTab(self.panel11, "شبكة 11 ك.ف")
        tabs.addTab(self.panel33, "شبكة 33 ك.ف")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(tabs)
        splitter.addWidget(self._results_pane())
        splitter.setSizes([680, 820])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

    def _results_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        title = QLabel("جدول المواد")
        title.setFont(QFont("", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        self.materials = QTableWidget(0, 5)
        self.materials.setHorizontalHeaderLabels(
            ["المادة", "الوحدة", "الكمية", "سعر الوحدة", "الكلفة"]
        )
        self._tune_table(self.materials)
        self.materials.itemSelectionChanged.connect(self._show_breakdown)
        layout.addWidget(self.materials, stretch=3)

        # تفصيل الرقم — من أين جاءت كمية المادة المحدّدة
        self.breakdown = QLabel()
        self.breakdown.setWordWrap(True)
        self.breakdown.setObjectName("hint")
        self.breakdown.setTextFormat(Qt.TextFormat.RichText)
        self.breakdown.setMinimumHeight(70)
        self.breakdown.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )
        layout.addWidget(self.breakdown)

        title = QLabel("أجور العمل")
        title.setFont(QFont("", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        self.labour = QTableWidget(0, 4)
        self.labour.setHorizontalHeaderLabels(["البند", "الكمية", "السعر الوحدي", "الكلفة"])
        self._tune_table(self.labour)
        layout.addWidget(self.labour, stretch=2)

        self.warning = QLabel()
        self.warning.setWordWrap(True)
        self.warning.setObjectName("hint")
        layout.addWidget(self.warning)

        totals = QHBoxLayout()
        self.total_mat = QLabel()
        self.total_lab = QLabel()
        self.total_all = QLabel()
        self.total_all.setObjectName("total")
        for w in (self.total_mat, self.total_lab, self.total_all):
            totals.addWidget(w)
        totals.addStretch(1)
        layout.addLayout(totals)
        return pane

    @staticmethod
    def _tune_table(table: QTableWidget) -> None:
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    # ─────────────────────────────── الحساب ───────────────────────────────

    @staticmethod
    def _fmt(value: float) -> str:
        return f"{value:,.3f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"

    def _show_breakdown(self) -> None:
        """يعرض تفصيل كمية المادة المحدّدة — مصادرها ومعادلة كل مصدر."""
        index = self.materials.currentRow()
        if index < 0 or index >= len(self._rows):
            self.breakdown.setText("اختر مادة من الجدول لعرض تفصيل حساب كميتها.")
            return
        row = self._rows[index]
        parts = row["تفصيل"]

        head = f"<b>{row['المادة']}</b> — الكمية {self._fmt(row['الكمية'])} {row['الوحدة']}"
        if len(parts) == 1:
            body = f"<br>{parts[0]['المصدر']}"
        else:
            items = "".join(
                f"<br>&nbsp;&nbsp;• <b>{self._fmt(p['الكمية'])}</b> ← {p['المصدر']}"
                for p in parts
            )
            body = f" &nbsp;<i>(مجموع {len(parts)} مصادر)</i>{items}"
        self.breakdown.setText(head + body)

    def recalculate(self) -> None:
        project = OverheadProject(
            net11=self.panel11.network(), net33=self.panel33.network()
        )
        result = compute(project, self.catalog)

        rows = result["المواد"]
        self._rows = rows
        self.materials.setRowCount(len(rows))
        for r, row in enumerate(rows):
            qty = row["الكمية"]
            qty_text = f"{qty:,.3f}".rstrip("0").rstrip(".") if qty % 1 else f"{qty:,.0f}"
            if row["سعر_مفقود"]:
                price_text, cost_text = "— غير مُسعَّر —", "—"
            elif row["كمية_فقط"]:
                price_text, cost_text = "ضمن الأجور", "—"
            else:
                price_text = f"{row['سعر الوحدة']:,.0f}"
                cost_text = f"{row['الكلفة']:,.0f}"
            name = row["المادة"] + ("  ⊕" if row["مجمَّع"] else "")
            cells = [name, row["الوحدة"], qty_text, price_text, cost_text]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if row["سعر_مفقود"]:
                    item.setForeground(QColor("#b45309"))
                elif row["كمية_فقط"]:
                    item.setForeground(QColor("#6b7280"))
                self.materials.setItem(r, c, item)

        labour = result["أجور_العمل"]
        self.labour.setRowCount(len(labour))
        for r, line in enumerate(labour):
            qty = line.qty
            qty_text = f"{qty:,.0f}" if qty % 1 == 0 else f"{qty:,.2f}"
            cells = [line.name, f"{qty_text} {line.unit}",
                     f"{line.rate:,.0f}", f"{line.cost:,.0f}"]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.labour.setItem(r, c, item)

        missing = result["أسعار_مفقودة"]
        if missing:
            self.warning.setText(
                "⚠️ مواد بلا سعر، كلفتها غير محتسبة في المجموع: " + "، ".join(missing)
            )
            self.warning.setVisible(True)
        else:
            self.warning.setVisible(False)

        self._show_breakdown()
        self.total_mat.setText(f"كلفة المواد:  {result['كلفة_المواد']:,.0f}")
        self.total_lab.setText(f"أجور العمل:  {result['كلفة_العمل']:,.0f}")
        self.total_all.setText(f"الكلفة الكلية:  {result['الكلفة_الكلية']:,.0f} دينار")
