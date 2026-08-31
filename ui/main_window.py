# -*- coding: utf-8 -*-
"""النافذة الرئيسية — مقاطع المشروع ونتائجها الحيّة."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engine import latest_catalog_version, load_catalog
from engine.prices import differences
from engine.project import compute_project
from engine.store import EXTENSION, LoadError, load as load_order, save as save_order
from engine.workorder import WorkOrder
from engine.types import Project, SegmentKind
import printing

from .order_panel import OrderPanel
from .prices_window import open_prices
from .segments_panel import SegmentsPanel

WO_FILTER = f"ملف أمر عمل (*{EXTENSION})"

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
/* عناوين الجدولين. تُضبط هنا لا بـ QFont: تمرير عائلة فارغة إلى QFont
   يكسر تشكيل العربية على ويندوز فتظهر الحروف مقطّعة ومن خطوط مختلفة (ق-٥٣). */
QLabel#pane   { font-size: 16px; font-weight: 700; padding: 2px 2px 4px 2px; }
QPushButton   { padding: 6px 14px; border-radius: 5px; }
QPushButton#print { font-weight: 600; padding: 8px 20px; }
"""


class MainWindow(QMainWindow):
    def __init__(self, catalog: dict, version: str | None = None) -> None:
        super().__init__()
        self.catalog = catalog
        self.version = version or latest_catalog_version()
        """نسخة الأسعار التي يُحسب بها أمر العمل المفتوح — تُحفظ معه (ق-٤٠)."""
        self.path: Path | None = None
        """مسار ملف `.wo` المفتوح. None يعني أمر عمل جديد لم يُحفظ بعد."""
        self._rows: list[dict] = []
        self.result: dict = {"المواد": [], "أسعار_مفقودة": []}
        self.setWindowTitle("نظام أوامر العمل الكهربائية")
        self.resize(1500, 950)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setStyleSheet(STYLE)
        self._build()
        self.recalculate()
        self._refresh_title()

    def _build(self) -> None:
        self._build_menu()
        self.segments = SegmentsPanel(self.catalog)
        self.order_panel = OrderPanel()
        self.segments.changed.connect(self.recalculate)

        tabs = QTabWidget()
        tabs.addTab(self.segments, "المقاطع")
        tabs.addTab(self.order_panel, "أمر العمل")

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
        title.setObjectName("pane")
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
        title.setObjectName("pane")
        layout.addWidget(title)

        self.labour = QTableWidget(0, 4)
        self.labour.setHorizontalHeaderLabels(["البند", "الكمية", "السعر الوحدي", "الكلفة"])
        self._tune_table(self.labour)
        layout.addWidget(self.labour, stretch=2)

        self.warning = QLabel()
        self.warning.setWordWrap(True)
        self.warning.setObjectName("hint")
        self.warning.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.warning)

        totals = QHBoxLayout()
        self.total_mat = QLabel()
        self.total_lab = QLabel()
        self.total_all = QLabel()
        self.total_all.setObjectName("total")
        for w in (self.total_mat, self.total_lab, self.total_all):
            totals.addWidget(w)
        totals.addStretch(1)

        totals.addWidget(QLabel("القالب:"))
        self.template_box = QComboBox()
        for template in printing.available():
            self.template_box.addItem(template.name, template.key)
            self.template_box.setItemData(
                self.template_box.count() - 1,
                template.description,
                Qt.ItemDataRole.ToolTipRole,
            )
        self.template_box.setMinimumWidth(170)
        totals.addWidget(self.template_box)

        self.excel_button = QPushButton("تصدير إلى إكسل")
        self.excel_button.setToolTip(
            "ورقة عمل قابلة للتعديل: الكلفة معادلة لا رقماً، فتعديل أي كمية "
            "يُحدّثها ومجموعها داخل الإكسل بلا عودة إلى البرنامج."
        )
        self.print_button = QPushButton("طباعة  (PDF)")
        self.print_button.setObjectName("print")
        self.print_button.clicked.connect(self.export_pdf)
        self.excel_button.clicked.connect(self.export_excel)
        totals.addWidget(self.excel_button)
        totals.addWidget(self.print_button)
        layout.addLayout(totals)
        return pane

    # ──────────────────────── الملفّ ونسخة الأسعار ────────────────────────

    def _build_menu(self) -> None:
        """شريط «ملف» و«الأسعار» — حفظ أمر العمل وفتحه وإدارة الأسعار (ق-٦١، ق-٦٢)."""
        bar = self.menuBar()
        bar.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        menu = bar.addMenu("ملف")
        self.action_new = menu.addAction("أمر عمل جديد")
        self.action_new.setShortcut("Ctrl+N")
        self.action_new.triggered.connect(self.new_order)
        self.action_open = menu.addAction("فتح…")
        self.action_open.setShortcut("Ctrl+O")
        self.action_open.triggered.connect(self.open_order)
        menu.addSeparator()
        self.action_save = menu.addAction("حفظ")
        self.action_save.setShortcut("Ctrl+S")
        self.action_save.triggered.connect(self.save)
        self.action_save_as = menu.addAction("حفظ باسم…")
        self.action_save_as.setShortcut("Ctrl+Shift+S")
        self.action_save_as.triggered.connect(self.save_as)

        menu = bar.addMenu("الأسعار")
        self.action_prices = menu.addAction("إدارة الأسعار…")
        self.action_prices.triggered.connect(self.manage_prices)
        self.action_update_prices = menu.addAction("تحديث أسعار أمر العمل إلى الأحدث…")
        self.action_update_prices.triggered.connect(self.update_prices)

    def _refresh_title(self) -> None:
        """يُظهر اسم الملف ونسخة الأسعار في العنوان — فلا يلتبس أمر عمل بآخر."""
        name = self.path.name if self.path else "أمر عمل جديد (لم يُحفظ)"
        self.setWindowTitle(
            f"نظام أوامر العمل الكهربائية  —  {name}  —  أسعار {self.version}"
        )

    def project(self) -> Project:
        """المشروع كما هو في الواجهة الآن."""
        return Project(
            self.order_panel.project_name.text(),
            self.segments.segments(),
            **self.segments.street_crossings(),
        )

    def new_order(self) -> None:
        """يفرغ الواجهة لأمر عمل جديد — بعد تأكيد، فالمُدخَل يضيع بلا رجعة."""
        if self.segments.segments() and not self._confirm(
            "أمر عمل جديد",
            "سيُفرَّغ أمر العمل الحالي.\n\nاحفظه أولاً إن أردت الاحتفاظ به. أتابع؟"
        ):
            return
        self.segments.load(Project())
        self.order_panel.load(WorkOrder())
        self.path = None
        self.version = latest_catalog_version()
        self.catalog = load_catalog(self.version)
        self._retarget_catalog()
        self.recalculate()
        self._refresh_title()

    @staticmethod
    def _confirm(title: str, text: str) -> bool:
        answer = QMessageBox.question(
            None, title, text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def save_to(self, path: str | Path) -> Path:
        """يكتب ملف `.wo` بلا أي حوار — قابلة للاختبار والاستدعاء الآلي."""
        written = save_order(path, self.order_panel.order(), self.project(), self.version)
        self.path = written
        self._refresh_title()
        return written

    def save(self) -> Path | None:
        """حفظ في المسار الحالي، أو «حفظ باسم» إن لم يكن ثمّة مسار."""
        if self.path is None:
            return self.save_as()
        try:
            return self.save_to(self.path)
        except OSError as exc:
            QMessageBox.critical(self, "تعذّر الحفظ", f"لم يُكتب الملف:\n{exc}")
            return None

    def save_as(self) -> Path | None:
        number = self.order_panel.number.text().strip()
        suggested = f"أمر عمل {number}{EXTENSION}" if number else f"أمر عمل{EXTENSION}"
        path, _ = QFileDialog.getSaveFileName(self, "حفظ أمر العمل", suggested, WO_FILTER)
        if not path:
            return None
        try:
            written = self.save_to(path)
        except OSError as exc:
            QMessageBox.critical(self, "تعذّر الحفظ", f"لم يُكتب الملف:\n{exc}")
            return None
        QMessageBox.information(self, "تم الحفظ", f"حُفظ أمر العمل في:\n{written.name}")
        return written

    def load_from(self, path: str | Path) -> None:
        """يفتح ملف `.wo` ويستعيد الواجهة كلها منه — بلا أي حوار.

        **نسخة الأسعار تُستعاد من الملف** لا من أحدث نسخة: أمر عمل أُنشئ بأسعار آب
        يُعاد فتحه بأسعار آب (ق-٤٠). فإن غابت النسخة عن القرص أُبلغ عنها ولم
        تُستبدل صامتةً بغيرها.
        """
        order, project, version = load_order(path)
        if version:
            self.catalog = load_catalog(version)      # يرفع خطأً إن غابت النسخة
            self.version = version
            self._retarget_catalog()
        self.segments.load(project)
        self.order_panel.load(order)
        self.path = Path(path)
        self.recalculate()
        self._refresh_title()

    def open_order(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "فتح أمر عمل", "", WO_FILTER)
        if not path:
            return
        try:
            self.load_from(path)
        except (LoadError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "تعذّر الفتح", f"{exc}")
        except FileNotFoundError as exc:
            QMessageBox.critical(
                self, "نسخة الأسعار مفقودة",
                f"{exc}\n\nأمر العمل يشير إلى نسخة أسعار غير موجودة في مجلد "
                "البيانات. انسخها إلى المجلد ثم أعد الفتح."
            )

    def _retarget_catalog(self) -> None:
        """يوجّه اللوحات إلى نسخة الأسعار الحالية — الاقتراحات تقرأ منها."""
        self.segments.catalog = self.catalog
        for row in range(self.segments.list.count()):
            self.segments.editor(row).catalog = self.catalog

    # ─────────────────────────── إدارة الأسعار ───────────────────────────

    def manage_prices(self) -> None:
        """يفتح شاشة الأسعار، وينتقل إلى النسخة الجديدة إن اعتُمدت (ق-٦٢)."""
        version = open_prices(self, self.catalog, self.version)
        if version:
            self.switch_version(version)

    def switch_version(self, version: str) -> None:
        """ينقل أمر العمل المفتوح إلى نسخة أسعار أخرى ويُعيد الحساب."""
        self.catalog = load_catalog(version)
        self.version = version
        self._retarget_catalog()
        self.recalculate()
        self._refresh_title()

    def update_prices(self) -> None:
        """يحدّث أمر العمل المفتوح إلى أحدث نسخة أسعار — **بأمر صريح منك**.

        بنصّ المستخدم: «مع احتفاظ أوامر العمل القديمة بنفس سعر المواد والعمل في
        تاريخ إنشائها **إلا إذا أنا أعطيت أمراً بتغييرها وتحديثها**».

        فالتحديث لا يقع تلقائياً أبداً، ويُعرض أثره على الكلفة قبل وقوعه.
        """
        latest = latest_catalog_version()
        if latest == self.version:
            QMessageBox.information(
                self, "لا جديد",
                f"أمر العمل على أحدث نسخة أسعار أصلاً ({self.version})."
            )
            return

        newer = load_catalog(latest)
        diff = differences(self.catalog, newer)
        before = self.result.get("الكلفة_الكلية", 0)
        after = compute_project(self.project(), newer)["الكلفة_الكلية"]
        change = after - before
        sign = "+" if change > 0 else ""
        detail = "\n".join(
            f"• {d['الاسم']}: "
            f"{'غير مُسعَّر' if d['قبل'] is None else format(d['قبل'], ',.0f')}"
            f" ← {'غير مُسعَّر' if d['بعد'] is None else format(d['بعد'], ',.0f')}"
            for d in diff[:10]
        ) or "• لا فرق في الأسعار بين النسختين"
        more = f"\n… و{len(diff) - 10} غيرها" if len(diff) > 10 else ""

        if not self._confirm(
            "تحديث أسعار أمر العمل",
            f"من نسخة «{self.version}» إلى «{latest}» — {len(diff)} تغييراً:\n\n"
            f"{detail}{more}\n\n"
            f"الكلفة الكلية: {before:,.0f} ← {after:,.0f}  ({sign}{change:,.0f} دينار)"
            "\n\nأتابع؟"
        ):
            return
        self.switch_version(latest)

    # ─────────────────────────────── الطباعة ───────────────────────────────

    @property
    def template(self) -> printing.Template:
        """القالب المختار حالياً."""
        return printing.get(self.template_box.currentData())

    def write_order_pdf(self, path: str, template_key: str | None = None) -> str:
        """يكتب أمر العمل ملفَّ PDF بالقالب المختار ويعيد المسار.

        بلا أي حوار — الحوارات في `export_pdf` وحدها. الفصل مقصود: هذه الدالة
        قابلة للاختبار والاستدعاء آلياً، والنوافذ الحاجزة تُعطّل كليهما.
        """
        if not self.result["المواد"]:
            raise ValueError("جدول المواد فارغ — أدخل معطيات الشبكة أولاً.")
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        template = printing.get(template_key) if template_key else self.template
        template.write_pdf(self.order_panel.order(), self.result, path)
        return path

    def export_pdf(self) -> str | None:
        """معالج زرّ الطباعة: يتحقّق، يسأل عن المسار، يكتب، ثم يُعلم المستخدم."""
        if not self.result["المواد"]:
            QMessageBox.warning(self, "لا توجد مواد",
                                "أدخل معطيات الشبكة أولاً — جدول المواد فارغ.")
            return None

        number = self.order_panel.number.text().strip()
        stem = f"أمر عمل {number}" if number else "أمر عمل"
        if self.template.key != "iso":
            stem += f" - {self.template.name}"
        suggested = f"{stem}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "حفظ أمر العمل", suggested, "ملفات PDF (*.pdf)"
        )
        if not path:
            return None

        try:
            path = self.write_order_pdf(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "تعذّر الحفظ", f"لم يُكتب الملف:\n{exc}")
            return None

        missing = self.result["أسعار_مفقودة"]
        note = ""
        if missing:
            note = ("\n\nتنبيه: مواد بلا سعر لم تُحتسب كلفتها في المجموع:\n"
                    + "، ".join(missing))
        QMessageBox.information(
            self, "تم الحفظ",
            f"حُفظ بقالب «{self.template.name}» في:\n{Path(path).name}{note}")
        return path

    def write_order_xlsx(self, path: str) -> str:
        """يكتب أمر العمل ملفَّ إكسل ويعيد المسار — بلا أي حوار (ق-٥٧)."""
        from printing.spreadsheet import write_xlsx

        if not self.result["المواد"]:
            raise ValueError("جدول المواد فارغ — أدخل معطيات الشبكة أولاً.")
        return write_xlsx(self.order_panel.order(), self.result, path)

    def export_excel(self) -> str | None:
        """معالج زرّ التصدير إلى إكسل — نظير `export_pdf` تماماً."""
        if not self.result["المواد"]:
            QMessageBox.warning(self, "لا توجد مواد",
                                "أدخل معطيات الشبكة أولاً — جدول المواد فارغ.")
            return None

        number = self.order_panel.number.text().strip()
        suggested = f"أمر عمل {number}.xlsx" if number else "أمر عمل.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "تصدير إلى إكسل", suggested, "مصنَّف إكسل (*.xlsx)"
        )
        if not path:
            return None
        try:
            path = self.write_order_xlsx(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "تعذّر الحفظ", f"لم يُكتب الملف:\n{exc}")
            return None

        QMessageBox.information(
            self, "تم التصدير",
            f"صُدّر إلى:\n{Path(path).name}\n\n"
            "الكلفة في الملف **معادلة** لا رقماً — عدّل أي كمية أو سعر "
            "فيُحدَّث المجموع داخل الإكسل."
        )
        return path

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

    def add_segment(self, kind: SegmentKind, name: str | None = None):
        """يضيف مقطعاً ويعيد محرّره — طريق مختصر للواجهة وللاختبارات."""
        row = self.segments.add_segment(kind, name)
        return self.segments.editor(row)

    def recalculate(self) -> None:
        project = Project(
            self.order_panel.project_name.text(),
            self.segments.segments(),
            **self.segments.street_crossings(),
        )
        self.segments.refresh_street_hint(self.catalog)
        result = compute_project(project, self.catalog)
        self.result = result

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
            rate_text = "— بلا أجر —" if line.rate_missing else f"{line.rate:,.0f}"
            cost_text = "—" if line.rate_missing else f"{line.cost:,.0f}"
            cells = [line.name, f"{qty_text} {line.unit}", rate_text, cost_text]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.labour.setItem(r, c, item)

        notes = []
        if result["أسعار_مفقودة"]:
            notes.append("مواد بلا سعر: " + "، ".join(result["أسعار_مفقودة"]))
        if result.get("أجور_مفقودة"):
            notes.append("بنود بلا أجر: " + "، ".join(result["أجور_مفقودة"]))
        if notes:
            self.warning.setText("⚠️ غير محتسب في المجموع — " + " &nbsp;|&nbsp; ".join(notes))
            self.warning.setVisible(True)
        else:
            self.warning.setVisible(False)

        self._show_breakdown()
        self.total_mat.setText(f"كلفة المواد:  {result['كلفة_المواد']:,.0f}")
        self.total_lab.setText(f"أجور العمل:  {result['كلفة_العمل']:,.0f}")
        self.total_all.setText(f"الكلفة الكلية:  {result['الكلفة_الكلية']:,.0f} دينار")
