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
from engine.version import VERSION
from engine.availability import selectable, unavailable_summary
from engine.overrides import apply as apply_overrides, ambiguous_labour, key_of
from engine.underground import CIVIL_GROUP
from engine.prices import differences
from engine.project import compute_project
from engine.store import EXTENSION, LoadError, load as load_order, save as save_order
from engine.workorder import WorkOrder
from engine.types import (
    CrossingKind,
    Project,
    SegmentKind,
    StreetCrossing,
    Underground11kV,
    Underground33kV,
)
import printing
from printing.amana_form import printed_labour_name, printed_unit

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


def migrate_project_crossings(project) -> list[str]:
    """ينقل عبور الشوارع من حقول المشروع القديمة إلى أول مقطعٍ أرضي (ق-٨٨).

    **ولماذا هذا لازمٌ لا تجميل:** بعد أن زالت حقول المشروع من الواجهة (بإذن
    المستخدم)، صار ملفٌ قديم يحمل عبوراً **يفقده عند الفتح وتنزل كلفته بصمت** —
    لأن الواجهة تبني المشروع من مقاطعها وحدها. والصمت هو الخطر، لا العبور.

    **والنقل لا يغيّر رقماً**: العبور القديم شارعٌ واحد (`count=1`)، وهي الحالة
    التي تعطي فيها صيغة ق-٨٧ ما كانت تعطيه صيغة ق-٤٥ حرفاً بحرف — وحارسٌ يثبّته.

    يعيد وصفاً لما نُقل (أو لما تعذّر نقله) ليُعرَض على المستخدم، فلا يقع شيء
    بلا علمه. والقائمة الفارغة تعني أن الملف لا عبور فيه.
    """
    moved: list[str] = []
    target = next((s for s in project.segments
                   if isinstance(s.content, (Underground11kV, Underground33kV))), None)
    for length_field, feeders_field, kind in (
        ("street_crossing_secondary_m", "street_crossing_secondary_feeders",
         CrossingKind.SECONDARY),
        ("street_crossing_main_m", "street_crossing_main_feeders", CrossingKind.MAIN),
    ):
        length = getattr(project, length_field)
        feeders = getattr(project, feeders_field)
        if not (length and feeders):
            continue
        where = f"«{target.name}»" if target else "— ولا مقطع أرضيّ في الملف"
        moved.append(f"{kind.value}: {length:,.0f} م × {feeders} مغذيات ← {where}")
        if target is None:
            continue
        target.content.crossings = list(target.content.crossings) + [
            StreetCrossing(kind=kind, count=1, street_length_m=length, feeders=feeders)
        ]
        setattr(project, length_field, 0.0)
    return moved


def _price_text(value) -> str:
    """سعرٌ للعرض في حوار التحديث. **يقبل ما ليس رقماً**."""
    return "غير مُسعَّر" if value is None else f"{value:,.0f}"


def _diff_line(d: dict) -> str:
    """سطرٌ واحد في حوار «تحديث أسعار أمر العمل».

    **البندُ المضاف أو المحذوف لا سعرَ له يُعرض**: `differences` تضع فيه «—» لا
    رقماً، فتنسيقه رقماً يرفع `ValueError` ويُسقط الحوار كلّه. وهذه ليست حالة
    نادرة: كل نسخة أسعار تُضاف فيها مادة جديدة تُنتجها — وق-٨٥ أضاف ثلاثاً،
    فصار كل أمر عمل قديم يتعذّر تحديثه.
    """
    if d["الحالة"] == "أُضيف":
        return f"• {d['الاسم']}: بندٌ جديد في نسخة الأسعار"
    if d["الحالة"] == "حُذف":
        return f"• {d['الاسم']}: حُذف من نسخة الأسعار"
    return f"• {d['الاسم']}: {_price_text(d['قبل'])} ← {_price_text(d['بعد'])}"


class MainWindow(QMainWindow):
    def __init__(self, catalog: dict, version: str | None = None) -> None:
        super().__init__()
        self.catalog = catalog
        self.version = version or latest_catalog_version()
        """نسخة الأسعار التي يُحسب بها أمر العمل المفتوح — تُحفظ معه (ق-٤٠)."""
        self.path: Path | None = None
        """مسار ملف `.wo` المفتوح. None يعني أمر عمل جديد لم يُحفظ بعد."""
        self._rows: list[dict] = []
        self.dirty = False
        """هل في أمر العمل تعديل لم يُحفظ بعد؟ (ق-٨٠)

        يُرفع مع أي تغيير في المقاطع أو في لوحة أمر العمل أو في نسخة الأسعار،
        ويُخفض عند الحفظ والفتح والبدء من جديد — أي عند كل لحظة يصير فيها ما
        على الشاشة مطابقاً لما على القرص.
        """
        self.manual_mode = False
        """هل أُذن بتحرير الكميات يدوياً؟ (ق-٨٢) — إذنٌ صريح لا حالة افتراضية."""
        self.material_overrides: dict[str, float] = {}
        self.labour_overrides: dict[str, float] = {}
        """الكميات التي عدّلها المستخدم بيده. المحسوب لا يُمسّ، وإفراغُها يعيده."""
        self.unavailable: set[str] = set()
        """المواد المؤشَّرة «غير متوفرة في المخازن» (ق-٧٦).

        تُحفَظ في الكائن لا في الجدول: الجدول يُعاد بناؤه عند كل حساب، ولو كان
        هو المرجع لضاع التأشير مع أول تعديل على المقاطع."""
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
        # التعديل غير المحفوظ يُرصد من مصدريه معاً — والمقاطع وحدها لا تكفي:
        # رقم أمر العمل واسم المشروع يُحفظان أيضاً (ق-٨٠)
        self.segments.changed.connect(self._mark_dirty)
        self.order_panel.changed.connect(self._mark_dirty)

        tabs = QTabWidget()
        tabs.addTab(self.segments, "المقاطع")
        tabs.addTab(self.order_panel, "أمر العمل")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(tabs)
        splitter.addWidget(self._results_pane())
        # الحدّ الأدنى الصريح يمنع محتوى اللوحة من تجميد المقبض (ق-٧٢): لوحات
        # الإدخال داخل مناطق تمرير، فتضييقها يُظهر شريط تمرير ولا يخفي حقلاً.
        tabs.setMinimumWidth(320)
        splitter.setSizes([680, 820])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

    MATERIAL_COLUMNS = ["المادة", "الوحدة", "الكمية", "الكمية المعدَّلة",
                        "سعر الوحدة", "الكلفة", "غير متوفرة"]
    UNAVAILABLE_COLUMN = 6
    """عمود تأشير المواد غير المتوفرة في المخازن (ق-٧٦)."""

    EDIT_COLUMN = 3
    """عمود الكمية المعدَّلة يدوياً — **بجانب المحسوبة** ليُقارَن الرقمان بنظرة
    واحدة، لا في آخر الجدول حيث يُقرأ وحده فيُظنّ هو الحساب (ق-٨٢)."""

    LABOUR_COLUMNS = ["البند", "الكمية", "الكمية المعدَّلة", "السعر الوحدي", "الكلفة"]
    LABOUR_EDIT_COLUMN = 2

    def _results_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        title = QLabel("جدول المواد")
        title.setObjectName("pane")
        layout.addWidget(title)

        self.materials = QTableWidget(0, len(self.MATERIAL_COLUMNS))
        self.materials.setHorizontalHeaderLabels(self.MATERIAL_COLUMNS)
        self._tune_table(self.materials)
        self.materials.itemSelectionChanged.connect(self._show_breakdown)
        self.materials.itemChanged.connect(self._on_availability_change)
        self.materials.itemChanged.connect(self._on_material_edit)
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

        self.labour = QTableWidget(0, len(self.LABOUR_COLUMNS))
        self.labour.setHorizontalHeaderLabels(self.LABOUR_COLUMNS)
        self._tune_table(self.labour)
        self.labour.itemChanged.connect(self._on_labour_edit)
        layout.addWidget(self.labour, stretch=2)

        # شريط التعديلات اليدوية: ظاهرٌ ما دام هناك تعديل، ومعه زرّ إلغائها (ق-٨٢)
        self.manual_bar = QHBoxLayout()
        self.manual_note = QLabel()
        self.manual_note.setObjectName("hint")
        self.manual_note.setTextFormat(Qt.TextFormat.RichText)
        self.manual_note.setMinimumWidth(1)
        self.clear_manual = QPushButton("إلغاء كل التعديلات اليدوية")
        self.clear_manual.setToolTip(
            "يعيد كل كمية إلى ما حسبه البرنامج. والمحسوب لم يُمسّ أصلاً."
        )
        self.clear_manual.clicked.connect(self.clear_overrides)
        self.manual_bar.addWidget(self.manual_note, stretch=1)
        self.manual_bar.addWidget(self.clear_manual)
        layout.addLayout(self.manual_bar)

        self.warning = QLabel()
        self.warning.setWordWrap(True)
        self.warning.setObjectName("hint")
        self.warning.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.warning)

        # سطران لا سطر واحد: المجاميع أعلى والأزرار أسفل. وسطرٌ واحد يجمعهما
        # يجعل الحدّ الأدنى لعرض اللوحة = عرضهما معاً، فيتجمّد مقبض المُقسِّم (ق-٧٢).
        totals = QHBoxLayout()
        self.total_mat = QLabel()
        self.total_lab = QLabel()
        self.total_all = QLabel()
        self.total_all.setObjectName("total")
        # حصص العرض: للكلفة الكلية ضعف حصّة غيرها، فسطرها أطول (فيه «دينار»
        # وخطّه عريض)، ولولا ذلك للفَّ وحده وفي الصفّ متّسع.
        for w, share in ((self.total_mat, 1), (self.total_lab, 1), (self.total_all, 2)):
            # لفّ الكلام لا قصّه: عند التضييق ينزل الرقم سطراً ولا يُبتَر منه
            # خانة، فلا يُقرأ مبلغٌ ناقص على أنه المبلغ. واللفّ يجعل الحدّ الأدنى
            # للعرض مستقلاً عن طول الرقم، فلا تضيق سعة سحب المقبض كلّما كبرت
            # كلفة المشروع (ق-٧٢). والحصص أعلاه تمنع اللفّ ما دام في الصفّ متّسع.
            w.setWordWrap(True)
            totals.addWidget(w, stretch=share)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(QLabel("القالب:"))
        self.template_box = QComboBox()
        for template in printing.available():
            self.template_box.addItem(template.name, template.key)
            self.template_box.setItemData(
                self.template_box.count() - 1,
                template.description,
                Qt.ItemDataRole.ToolTipRole,
            )
        self.template_box.setMinimumWidth(170)
        actions.addWidget(self.template_box)

        self.excel_button = QPushButton("تصدير إلى إكسل")
        self.excel_button.setToolTip(
            "ورقة عمل قابلة للتعديل: الكلفة معادلة لا رقماً، فتعديل أي كمية "
            "يُحدّثها ومجموعها داخل الإكسل بلا عودة إلى البرنامج."
        )
        self.print_button = QPushButton("طباعة  (PDF)")
        self.print_button.setObjectName("print")
        self.print_button.clicked.connect(self.export_pdf)
        self.excel_button.clicked.connect(self.export_excel)
        actions.addWidget(self.excel_button)
        actions.addWidget(self.print_button)
        layout.addLayout(totals)
        layout.addLayout(actions)
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

        menu = bar.addMenu("الكميات")
        self.action_manual = menu.addAction("تحرير الكميات يدوياً")
        self.action_manual.setCheckable(True)
        self.action_manual.toggled.connect(self.set_manual_mode)
        self.action_clear_manual = menu.addAction("إلغاء كل التعديلات اليدوية")
        self.action_clear_manual.triggered.connect(self.clear_overrides)

        menu = bar.addMenu("الأسعار")
        self.action_prices = menu.addAction("إدارة الأسعار…")
        self.action_prices.triggered.connect(self.manage_prices)
        self.action_update_prices = menu.addAction("تحديث أسعار أمر العمل إلى الأحدث…")
        self.action_update_prices.triggered.connect(self.update_prices)

    def _mark_dirty(self) -> None:
        """يرفع علم التعديل ويُظهر نجمته في العنوان."""
        if not self.dirty:
            self.dirty = True
            self._refresh_title()

    def _mark_clean(self) -> None:
        """ما على الشاشة صار مطابقاً لما على القرص."""
        self.dirty = False
        self._refresh_title()

    def closeEvent(self, event) -> None:
        """يمنع الخروج الصامت على عملٍ لم يُحفظ (ق-٨٠).

        بطلب المستخدم: «في حال غلق البرنامج قبل إجراء عملية حفظ تظهر رسالة
        لتنبيه المستخدم على ضرورة الحفظ قبل الخروج».

        **وثلاثة خيارات لا اثنان:** «حفظ» و«خروج بلا حفظ» و«إلغاء». ولو كان
        السؤال «أتخرج؟ نعم/لا» لاضطرّ من أراد الحفظ أن يُلغي ثم يبحث عن الأمر
        بنفسه. والافتراضي «حفظ» — أسلم الثلاثة عند نقرة سهو.

        وإن أُلغي حوار «حفظ باسم» أو فشلت الكتابة **يبقى البرنامج مفتوحاً**:
        فالخروج حينها يضيّع العمل الذي طُلب حفظه.
        """
        if not self.dirty:
            event.accept()
            return

        name = self.path.name if self.path else "أمر عمل جديد لم يُحفظ بعد"
        answer = QMessageBox.question(
            self, "تعديلات لم تُحفظ",
            f"في «{name}» تعديلات لم تُحفظ.\n\nأحفظها قبل الخروج؟",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if answer == QMessageBox.StandardButton.Save and self.save() is None:
            event.ignore()               # أُلغي الحفظ أو فشل — لا يُغلَق البرنامج
            return
        event.accept()

    def _refresh_title(self) -> None:
        """يُظهر اسم الملف ونسخة الأسعار في العنوان — فلا يلتبس أمر عمل بآخر."""
        name = self.path.name if self.path else "أمر عمل جديد (لم يُحفظ)"
        star = "•  " if self.dirty else ""     # نجمة التعديل غير المحفوظ (ق-٨٠)
        self.setWindowTitle(
            f"{star}نظام أوامر العمل الكهربائية {VERSION}  —  {name}"
            f"  —  أسعار {self.version}"
        )

    def order(self) -> WorkOrder:
        """أمر العمل كما هو في الواجهة — بحقول اللوحة **وتأشير المواد** معاً.

        التأشير يعيش في جدول النتائج لا في لوحة أمر العمل، فيُضمّ هنا في مكان
        واحد. ولو ضُمّ في كل موضع على حدة (حفظ، طباعة، إكسل) لسقط من أحدها
        يوماً بلا أن يظهر أثرُ سقوطه إلا في ورقة مطبوعة.
        """
        wo = self.order_panel.order()
        wo.unavailable_materials = sorted(self.unavailable)
        wo.material_overrides = dict(self.material_overrides)
        wo.labour_overrides = dict(self.labour_overrides)
        return wo

    def project(self) -> Project:
        """المشروع كما هو في الواجهة الآن."""
        return Project(
            self.order_panel.project_name.text(),
            self.segments.segments(),
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
        self.unavailable = set()
        self.material_overrides = {}
        self.labour_overrides = {}
        self.path = None
        self.version = latest_catalog_version()
        self.catalog = load_catalog(self.version)
        self._retarget_catalog()
        self.recalculate()
        self._mark_clean()

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
        written = save_order(path, self.order(), self.project(), self.version)
        self.path = written
        self._mark_clean()
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
        moved = migrate_project_crossings(project)
        self.segments.load(project)
        self.order_panel.load(order)
        self.unavailable = set(order.unavailable_materials)
        self.material_overrides = dict(order.material_overrides)
        self.labour_overrides = dict(order.labour_overrides)
        self.path = Path(path)
        self.recalculate()
        self._mark_clean()
        self.migrated_crossings = moved
        """ما نُقل من عبور المشروع عند آخر فتح — يعرضه `open_order` (ق-٨٨).

        **ولا تعرضه هذه الدالّة**: عقدها أنها بلا أي حوار، فتبقى قابلة للاختبار
        وللاستدعاء الآلي — والنوافذ الحاجزة تعطّل كليهما.
        """

    def _report_migrated_crossings(self) -> None:
        """يعرض ما نُقل من عبور المشروع عند الفتح — إن كان ثمّة ما نُقل."""
        moved = getattr(self, "migrated_crossings", [])
        if moved:
            QMessageBox.information(
                self, "عبور الشوارع نُقل إلى مقطعه",
                "هذا الملف يحمل عبور شوارع على مستوى المشروع، وهو موضعٌ لم يعد "
                "في الواجهة (ق-٨٨):\n\n• " + "\n• ".join(moved)
                + "\n\nوالكلفة لم تتغيّر. راجعه في جدول العبور داخل المقطع."
                + ("" if "ولا مقطع" not in " ".join(moved) else
                   "\n\n⚠️ ولا مقطع أرضيّ في هذا الملف، فلم يُنقل العبور ولم "
                   "يعد يُحتسب. أضف مقطعاً أرضياً وأدخله فيه.")
            )

    def open_order(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "فتح أمر عمل", "", WO_FILTER)
        if not path:
            return
        try:
            self.load_from(path)
            self._report_migrated_crossings()
        # الأخصّ أولاً: FileNotFoundError فرعٌ من OSError، فلو تأخّر لصار فرعاً
        # ميتاً لا يُبلَغ منه شيء — وهذه أكثر حالة يقع فيها من يعمل على أكثر من
        # حاسبة، إذ تُنشأ نسخة الأسعار على حاسبة ويُفتح أمر العمل على غيرها.
        except FileNotFoundError as exc:
            QMessageBox.critical(
                self, "نسخة الأسعار مفقودة",
                f"{exc}\n\nأمر العمل يشير إلى نسخة أسعار غير موجودة في مجلد "
                "البيانات. انسخ ملف catalog_<النسخة>.json من الحاسبة التي "
                "أُنشئ عليها إلى مجلد data هنا، ثم أعد الفتح."
            )
        except (LoadError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "تعذّر الفتح", f"{exc}")

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
        """ينقل أمر العمل المفتوح إلى نسخة أسعار أخرى ويُعيد الحساب.

        **ويُعدّ تعديلاً غير محفوظ** (ق-٨٠): اسم النسخة يُحفظ داخل ملف أمر
        العمل، فتغييره يجعل ما على الشاشة مخالفاً لما على القرص.
        """
        self.catalog = load_catalog(version)
        self.version = version
        self._retarget_catalog()
        self.recalculate()
        self._mark_dirty()
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
        detail = "\n".join(_diff_line(d) for d in diff[:10]) \
            or "• لا فرق في الأسعار بين النسختين"
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
        template.write_pdf(self.order(), self.result, path)
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

    def write_order_xlsx(self, path: str, template_key: str | None = None) -> str:
        """يكتب أمر العمل ملفَّ إكسل **بالقالب المختار** ويعيد المسار (ق-٥٧، ق-٧٦)."""
        if not self.result["المواد"]:
            raise ValueError("جدول المواد فارغ — أدخل معطيات الشبكة أولاً.")
        template = printing.get(template_key) if template_key else self.template
        return template.write_xlsx(self.order(), self.result, path)

    def export_excel(self) -> str | None:
        """معالج زرّ التصدير إلى إكسل — نظير `export_pdf` تماماً."""
        if not self.result["المواد"]:
            QMessageBox.warning(self, "لا توجد مواد",
                                "أدخل معطيات الشبكة أولاً — جدول المواد فارغ.")
            return None

        number = self.order_panel.number.text().strip()
        stem = f"أمر عمل {number}" if number else "أمر عمل"
        if self.template.key != "iso":
            stem += f" - {self.template.name}"
        suggested = f"{stem}.xlsx"
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
        # التحرير مسموح **بعلَم الخلية** وحده: لا خلية قابلة للتحرير إلا خانة
        # «الكمية المعدَّلة» وبإذن صريح (ق-٨٢)
        table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked
                              | QTableWidget.EditTrigger.EditKeyPressed)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    # ─────────────────────────────── الحساب ───────────────────────────────

    @staticmethod
    def _fmt(value: float) -> str:
        return f"{value:,.3f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"

    @staticmethod
    def _rate_reason(line) -> str:
        """لماذا اختلف سعر هذا البند عن نظيره — يُشرَح **في البرنامج وحده** (ق-٧٦).

        بطلب المستخدم: تعدّد المسار (عدد المغذيات في الخندق الواحد) يغيّر سعر
        الحفر وإعادة المسار، ولا يُذكر في المطبوع. فلولا هذا الشرح لبقي سببُ
        اختلاف سعرين لبندين متشابهَي الاسم **بلا تفسير في أي مكان**.
        """
        if "×" in line.unit:
            return (
                f"الوحدة «{line.unit}»: الكمية = طول العبور × عدد المغذيات "
                "المارّة فيه، لأن التعرفة لمغذٍّ واحد ولمتر واحد (ق-٤٥).\n\n"
                f"وفي المطبوع تظهر الوحدة «{printed_unit(line.unit)}» والكمية "
                "كما هي — بطلبك."
            )
        if line.group != CIVIL_GROUP or "مسار" not in line.name:
            return ""
        return (
            f"سعر هذا البند يتبع نوع الرصيف و«تعدّد المسار» — أي عدد المغذيات في "
            "الخندق الواحد: مفرد = مغذٍّ، ثنائي = مغذيان، ثلاثي = ثلاثة.\n"
            "ولذلك يختلف سعره عن سعر البند نفسه في مسار آخر.\n\n"
            f"وفي المطبوع يظهر باسم «{printed_labour_name(line.name)}» بلا ذكر "
            "التعدّد — بطلبك."
        )

    # ─────────────────── التعديل اليدوي على الكميات (ق-٨٢) ───────────────────

    def set_manual_mode(self, enabled: bool) -> None:
        """يفتح تحرير الكميات أو يغلقه — بإذن صريح في أول مرّة.

        **والإغلاق لا يمسح التعديلات**: هو إذنُ تحريرٍ لا مفتاحُ تشغيل. ومن
        أراد إزالتها فله زرّ صريح يقول ذلك باسمه.
        """
        if enabled and not self._confirm(
            "تحرير الكميات يدوياً",
            "ستتمكّن من كتابة كمية بيدك بدل ما حسبه البرنامج.\n\n"
            "• الرقم المحسوب لا يُمحى — يبقى معروضاً بجانب تعديلك\n"
            "• كل سطر معدَّل يُميَّز بلون، ويظهر عددها فوق المجاميع\n"
            "• «إلغاء كل التعديلات اليدوية» يعيد كل شيء إلى الحساب\n\n"
            "أتابع؟",
        ):
            self.action_manual.setChecked(False)
            return
        self.manual_mode = enabled
        if self.action_manual.isChecked() != enabled:
            self.action_manual.setChecked(enabled)
        self.recalculate()

    def clear_overrides(self) -> None:
        """يعيد كل كمية إلى ما حسبه المحرك."""
        if not (self.material_overrides or self.labour_overrides):
            return
        self.material_overrides.clear()
        self.labour_overrides.clear()
        self._mark_dirty()
        self.recalculate()

    def _edit_cell(self, key: str, value, *, blocked: str = "") -> QTableWidgetItem:
        """خلية «الكمية المعدَّلة» لسطر واحد.

        فارغةٌ ما لم يُعدَّل السطر، ولا تُحرَّر إلا بالإذن — فلا يتغيّر رقم
        بنقرةٍ سهو على جدول يُقرأ أكثر ممّا يُكتب.
        """
        item = QTableWidgetItem("" if value is None else self._fmt(value))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if blocked:
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setToolTip(blocked)
            return item
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self.manual_mode:
            flags |= Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        item.setData(Qt.ItemDataRole.UserRole, key)
        if value is not None:
            item.setForeground(QColor("#b45309"))
            if key not in self.material_overrides and key not in self.labour_overrides:
                item.setToolTip("تبعت مادتها المعدَّلة — اكتب رقماً هنا لتعديلها وحدها.")
        elif self.manual_mode:
            item.setToolTip("اكتب كمية لتحلّ محلّ المحسوبة، وأفرغ الخانة للعودة إليها.")
        return item

    def _apply_edit(self, item: QTableWidgetItem, store: dict) -> None:
        """يقرأ ما كُتب في خلية التعديل ويُحدّث مخزن التعديلات."""
        key = item.data(Qt.ItemDataRole.UserRole)
        if key is None:
            return
        text = (item.text() or "").strip().replace(",", "").replace("،", "")
        if not text:
            removed = store.pop(key, None)
            if removed is not None:
                self._mark_dirty()
                self.recalculate()
            return
        try:
            value = float(text)
        except ValueError:
            QMessageBox.warning(self, "كمية غير صالحة",
                                f"«{text}» ليس رقماً. أُبقيت الكمية كما كانت.")
            self.recalculate()
            return
        if value < 0:
            QMessageBox.warning(self, "كمية غير صالحة", "الكمية لا تكون سالبة.")
            self.recalculate()
            return
        if store.get(key) == value:
            return
        store[key] = value
        self._mark_dirty()
        self.recalculate()

    def _on_material_edit(self, item: QTableWidgetItem) -> None:
        if item.column() == self.EDIT_COLUMN:
            self._apply_edit(item, self.material_overrides)

    def _on_labour_edit(self, item: QTableWidgetItem) -> None:
        if item.column() == self.LABOUR_EDIT_COLUMN:
            self._apply_edit(item, self.labour_overrides)

    def _refresh_manual_bar(self) -> None:
        """شريطٌ ظاهر ما دام في الجدول رقمٌ ليس من حساب البرنامج."""
        summary = self.result.get("تعديلات_يدوية") or {"العدد": 0}
        count = summary["العدد"]
        names = (summary.get("المواد", []) + summary.get("الأجور", []))[:3]
        tail = "…" if len(summary.get("المواد", []) + summary.get("الأجور", [])) > 3 else ""
        self.manual_note.setText(
            f"✎ <b>{count}</b> كمية معدَّلة يدوياً — ليست من حساب البرنامج: "
            f"{'، '.join(names)}{tail}" if count else ""
        )
        self.manual_note.setVisible(bool(count))
        self.clear_manual.setVisible(bool(count))
        self.action_clear_manual.setEnabled(bool(count))

    def _mark(self, row: dict) -> QTableWidgetItem:
        """خلية تأشير «غير متوفرة» لمادة واحدة (ق-٧٦).

        المادة التي كلفتها ضمن الأجور **لا تُؤشَّر**: بنصّ المستخدم «هذه المواد
        تعتبر متوفرة دائماً». ولو أُتيح تأشيرها لأضافت صفراً إلى كلفة غير
        المتوفرة بلا أن ينبّه شيء.
        """
        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if not selectable(row):
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setText("متوفرة دائماً")
            item.setForeground(QColor("#6b7280"))
            item.setToolTip("كلفتها ضمن أجور العمل، فهي متوفرة دائماً ولا تُؤشَّر.")
            return item
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        item.setCheckState(
            Qt.CheckState.Checked if row["المادة"] in self.unavailable
            else Qt.CheckState.Unchecked
        )
        if row["سعر_مفقود"]:
            item.setToolTip("هذه المادة بلا سعر — تأشيرها لا يزيد كلفة غير "
                            "المتوفرة شيئاً.")
        return item

    def _on_availability_change(self, item: QTableWidgetItem) -> None:
        """يزامن مجموعة المؤشَّر عليها مع الجدول، ثم يُحدّث التحذيرات."""
        if item.column() != self.UNAVAILABLE_COLUMN:
            return
        row = self._rows[item.row()]
        if item.checkState() == Qt.CheckState.Checked:
            self.unavailable.add(row["المادة"])
        else:
            self.unavailable.discard(row["المادة"])
        self._refresh_warning()

    def _refresh_warning(self) -> None:
        """سطر التحذير: أسعار وأجور مفقودة، ومؤشَّرٌ بلا سعر (ق-٧٦)."""
        result = self.result
        notes = []
        if result.get("أسعار_مفقودة"):
            notes.append("مواد بلا سعر: " + "، ".join(result["أسعار_مفقودة"]))
        if result.get("أجور_مفقودة"):
            notes.append("بنود بلا أجر: " + "، ".join(result["أجور_مفقودة"]))
        text = ("⚠️ غير محتسب في المجموع — " + " &nbsp;|&nbsp; ".join(notes)
                if notes else "")

        summary = unavailable_summary(
            [r for r in result.get("المواد", []) if r["الكمية"] > 0], self.unavailable
        )
        if summary["بلا_سعر"]:
            unpriced = "، ".join(summary["بلا_سعر"])
            text += ("<br>" if text else "") + (
                "⚠️ مواد أُشّرت «غير متوفرة» وهي <b>بلا سعر</b>، فلا تزيد كلفة "
                f"غير المتوفرة شيئاً: {unpriced}"
            )
        self.warning.setText(text)
        self.warning.setVisible(bool(text))

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
        )
        # **المحرك أولاً، ثم طبقة التعديل اليدوي فوقه** (ق-٨٢): `compute_project`
        # لا يعرف بالتعديلات شيئاً، فإلغاؤها يعيد رقمه كما هو.
        computed = compute_project(project, self.catalog)
        result = apply_overrides(computed, self.material_overrides,
                                 self.labour_overrides)
        self.result = result
        blocked_labour = ambiguous_labour(result)

        rows = result["المواد"]
        self._rows = rows
        # بناء الجدول يُطلق `itemChanged` لكل خلية. والمعالج **لا يفسد شيئاً**
        # لو وصلته: كل خلية تأشير تُبنى على حالتها الصحيحة أصلاً، فيُعيد كتابة
        # ما هو مكتوب. جُرِّب حذف الكتم بالطفرة فلم يسقط اختبار (ق-٧٦).
        # ويبقى الكتم لأنه يُجنّب مئات النداءات في كل إعادة حساب — كلٌّ منها
        # يُعيد حساب سطر التحذير على الجدول كلّه.
        self.materials.blockSignals(True)
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
            manual = row.get("معدَّل_يدوياً", False)
            # العمود «الكمية» يبقى **المحسوب دائماً** ولو عُدِّل السطر، فالرقمان
            # يُقرآن معاً ولا يحلّ أحدهما محلّ الآخر بصمت (ق-٨٢)
            if manual:
                qty_text = self._fmt(row.get("الكمية_المحسوبة", row["الكمية"]))
            key = key_of(row["المادة"], row["الوحدة"])
            cells = [name, row["الوحدة"], qty_text, None, price_text, cost_text]
            for c, text in enumerate(cells):
                if c == self.EDIT_COLUMN:
                    self.materials.setItem(
                        r, c, self._edit_cell(key, self.material_overrides.get(key)))
                    continue
                item = QTableWidgetItem(text)
                if c:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if row["سعر_مفقود"]:
                    item.setForeground(QColor("#b45309"))
                elif row["كمية_فقط"]:
                    item.setForeground(QColor("#6b7280"))
                if manual:
                    item.setBackground(QColor("#fff7ed"))
                self.materials.setItem(r, c, item)
            self.materials.setItem(r, self.UNAVAILABLE_COLUMN, self._mark(row))
        self.materials.blockSignals(False)

        labour = result["أجور_العمل"]
        self.labour.blockSignals(True)
        self.labour.setRowCount(len(labour))
        for r, line in enumerate(labour):
            shown = line.computed_qty if line.manual else line.qty
            qty_text = f"{shown:,.0f}" if shown % 1 == 0 else f"{shown:,.2f}"
            rate_text = "— بلا أجر —" if line.rate_missing else f"{line.rate:,.0f}"
            cost_text = "—" if line.rate_missing else f"{line.cost:,.0f}"
            key = key_of(line.name, line.unit)
            cells = [line.name, f"{qty_text} {line.unit}", None, rate_text, cost_text]
            tip = self._rate_reason(line)
            for c, text in enumerate(cells):
                if c == self.LABOUR_EDIT_COLUMN:
                    # البند الذي تبع تعديل مادته تظهر كميته الفعلية هنا أيضاً،
                    # وإلا قُرئ سطرٌ كميته 2,475 وكلفته على 3,000 (ق-٨٢)
                    shown_edit = self.labour_overrides.get(
                        key, line.qty if line.manual else None)
                    self.labour.setItem(r, c, self._edit_cell(
                        key, shown_edit,
                        blocked=("بندان بهذا الاسم وسعران مختلفان — التعديل ملتبس، "
                                 "فعدّل مُدخَلات المقطع بدله (ق-٨٢)."
                                 if key in blocked_labour else ""),
                    ))
                    continue
                item = QTableWidgetItem(text)
                if c:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if tip:
                    item.setToolTip(tip)
                if line.manual:
                    item.setBackground(QColor("#fff7ed"))
                self.labour.setItem(r, c, item)
        self.labour.blockSignals(False)

        self._refresh_manual_bar()
        self._refresh_warning()

        self._show_breakdown()
        self.total_mat.setText(f"كلفة المواد:  {result['كلفة_المواد']:,.0f}")
        self.total_lab.setText(f"أجور العمل:  {result['كلفة_العمل']:,.0f}")
        self.total_all.setText(f"الكلفة الكلية:  {result['الكلفة_الكلية']:,.0f} دينار")
