# -*- coding: utf-8 -*-
"""لوحة المقاطع — المشروع قائمة مقاطع لا شبكة واحدة (ق-٢٤).

المشروع الواقعي: مقطع مزدوج، ومقطع مفرد، ومقطع ضغط واطئ على أعمدة الضغط العالي،
ومقطع ضغط واطئ بالقابلو المعلق، وآخر بالأسلاك. كل مقطع يُحرَّر بنفس اللوحة التي
كانت لوحة المشروع كله، ثم تُجمَّع الكميات من المقاطع جميعاً.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from engine.types import (
    Equipment,
    Network11kV,
    Network33kV,
    NetworkLV,
    Segment,
    SegmentKind,
    Underground11kV,
    Underground33kV,
    segment_default_name,
)

from .panels import (
    Panel11kV,
    Panel33kV,
    PanelEquipment,
    PanelLV,
    PanelUnderground11kV,
    PanelUnderground33kV,
)
from .widgets import HintLabel, number_field, section

EDITORS = {
    SegmentKind.HV11: Panel11kV,
    SegmentKind.HV33: Panel33kV,
    SegmentKind.LV: PanelLV,
    SegmentKind.EQUIPMENT: PanelEquipment,
    SegmentKind.UG11: PanelUnderground11kV,
    SegmentKind.UG33: PanelUnderground33kV,
}

JUNCTION_NOTE = (
    "المقطعان المتلاصقان يتقاسمان عمود شد واحداً عند نقطة الوصل، والاقتراح يحسبه "
    "في كلٍّ منهما — <b>فيزيد عموداً لكل وصلة، وهذا مقصود</b> (ق-٤٤): الاقتراح "
    "كشف تخميني، والتنفيذ في الأرض قد يتغيّر قليلاً، فالزيادة أسلم من النقص. "
    "الأعداد مُدخَلات في كل الأحوال، فاخصمه إن شئت (ق-١٠)."
)


class SegmentsPanel(QWidget):
    """قائمة مقاطع المشروع ومحرّر المقطع المحدَّد."""

    changed = pyqtSignal()

    def __init__(self, catalog: dict) -> None:
        super().__init__()
        self.catalog = catalog
        self._names: list[str] = []
        self._kinds: list[SegmentKind] = []
        self._build()
        self._connect()

    # ─────────────────────────────── البناء ───────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        bar = QHBoxLayout()
        self.kind = QComboBox()
        for kind in SegmentKind:
            self.kind.addItem(kind.value, kind)
        self.add = QPushButton("إضافة مقطع  +")
        self.remove = QPushButton("حذف")
        self.up = QPushButton("▲")
        self.down = QPushButton("▼")
        for w in (self.up, self.down):
            w.setMaximumWidth(40)
        bar.addWidget(QLabel("النوع:"))
        bar.addWidget(self.kind, stretch=1)
        bar.addWidget(self.add)
        bar.addWidget(self.remove)
        bar.addWidget(self.up)
        bar.addWidget(self.down)
        outer.addLayout(bar)

        self.list = QListWidget()
        self.list.setMaximumHeight(120)
        outer.addWidget(self.list)

        rename = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("اسم المقطع — يظهر في تفصيل كل كمية")
        rename.addWidget(QLabel("اسم المقطع:"))
        rename.addWidget(self.name, stretch=1)
        outer.addLayout(rename)

        self.stack = QStackedWidget()
        self.empty = HintLabel(
            "لا مقاطع بعد. اختر النوع من الأعلى واضغط «إضافة مقطع».<br><br>"
            "المشروع الواحد قد يضمّ مقطعاً مزدوجاً وآخر مفرداً ومقطع ضغط واطئ "
            "بالقابلو المعلق وآخر بالأسلاك — كلٌّ بحساباته، ثم تُجمَّع الكميات."
        )
        self.empty.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.stack.addWidget(self.empty)      # الفهرس صفر: لا مقطع محدَّد
        outer.addWidget(self.stack, stretch=1)

        self.note = HintLabel(JUNCTION_NOTE)
        outer.addWidget(self.note)

        # عبور الشوارع: رقم إجمالي للمشروع كله لا لكل مقطع (بطلب المستخدم، ق-٣٠)
        box, form = section("عبور الشوارع  —  إجمالي للمشروع كله")
        self.street_secondary = number_field(0, 100_000, 0, suffix="م")
        self.street_secondary_feeders = number_field(1, 100, 1)
        self.street_main = number_field(0, 100_000, 0, suffix="م")
        self.street_main_feeders = number_field(1, 100, 1)
        form.addRow("طول عبور الشوارع الفرعية:", self.street_secondary)
        form.addRow("عدد المغذيات العابرة (فرعية):", self.street_secondary_feeders)
        form.addRow("طول عبور الشوارع الرئيسية (حفر مخفي):", self.street_main)
        form.addRow("عدد المغذيات العابرة (رئيسية):", self.street_main_feeders)
        self.street_hint = HintLabel()
        form.addRow(self.street_hint)
        outer.addWidget(box)

        self._sync_controls()

    def _connect(self) -> None:
        self.add.clicked.connect(self._add_segment)
        self.remove.clicked.connect(self._remove_segment)
        self.up.clicked.connect(lambda: self._move(-1))
        self.down.clicked.connect(lambda: self._move(+1))
        for widget in (
            self.street_secondary, self.street_secondary_feeders,
            self.street_main, self.street_main_feeders,
        ):
            widget.valueChanged.connect(self.changed)
        self.list.currentRowChanged.connect(self._on_selection)
        self.name.textEdited.connect(self._rename_current)

    # ─────────────────────────────── العمليات ───────────────────────────────

    def add_segment(self, kind: SegmentKind, name: str | None = None) -> int:
        """يضيف مقطعاً ويعيد فهرسه. اللوحة المناسبة تُبنى مرّة وتبقى."""
        index = len(self._names)
        editor = EDITORS[kind](self.catalog, as_segment=True) \
            if kind is SegmentKind.LV else EDITORS[kind](self.catalog)
        editor.changed.connect(self.changed)
        self.stack.addWidget(editor)

        self._names.append(name or segment_default_name(index))
        self._kinds.append(kind)
        self.list.addItem("")
        self._refresh_labels()
        self.list.setCurrentRow(index)
        self.changed.emit()
        return index

    def _add_segment(self) -> None:
        self.add_segment(self.kind.currentData())

    def _remove_segment(self, confirm: bool = True) -> None:
        """يحذف المقطع المحدَّد بعد تأكيد المستخدم (ق-٥٧).

        الحذف **لا رجعة فيه** — لا تراجع في البرنامج، ولا حفظ للمشروع بعد.
        فمقطع أُدخلت معطياته في دقائق يضيع بنقرة واحدة. `confirm=False`
        للاستدعاء الآلي من الاختبارات، فالنوافذ الحاجزة تُعطّلها.
        """
        row = self.list.currentRow()
        if row < 0:
            return
        if confirm and not self._confirm_removal(row):
            return
        editor = self.stack.widget(row + 1)
        self.stack.removeWidget(editor)
        editor.deleteLater()
        del self._names[row]
        del self._kinds[row]
        self.list.takeItem(row)
        self._refresh_labels()
        self.list.setCurrentRow(min(row, len(self._names) - 1))
        self._sync_controls()
        self.changed.emit()

    def _confirm_removal(self, row: int) -> bool:
        """يسأل قبل الحذف ويسمّي المقطع — لئلا يُحذف غير المقصود."""
        answer = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"حذف «{self._names[row]}»؟\n\n"
            "تُفقَد معطياته كلها ولا يمكن التراجع.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,          # الافتراضي «لا» — نقرة سهوٍ لا تحذف
        )
        return answer == QMessageBox.StandardButton.Yes

    def _move(self, delta: int) -> None:
        """ينقل المقطع المحدَّد صعوداً أو نزولاً — الترتيب ترتيب المستخدم."""
        row = self.list.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < len(self._names):
            return
        editor = self.stack.widget(row + 1)
        self.stack.removeWidget(editor)
        self.stack.insertWidget(target + 1, editor)
        self._names.insert(target, self._names.pop(row))
        self._kinds.insert(target, self._kinds.pop(row))
        self.list.insertItem(target, self.list.takeItem(row))
        self._refresh_labels()
        self.list.setCurrentRow(target)
        self.changed.emit()

    def _rename_current(self, text: str) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        self._names[row] = text
        self._refresh_labels()
        self.changed.emit()

    # ─────────────────────────────── العرض ───────────────────────────────

    def _refresh_labels(self) -> None:
        for row, (name, kind) in enumerate(zip(self._names, self._kinds)):
            self.list.item(row).setText(f"{name}  —  {kind.value}")

    def _on_selection(self, row: int) -> None:
        self.stack.setCurrentIndex(row + 1 if row >= 0 else 0)
        self.name.blockSignals(True)
        self.name.setText(self._names[row] if row >= 0 else "")
        self.name.blockSignals(False)
        self._sync_controls()

    def _sync_controls(self) -> None:
        row = self.list.currentRow()
        has = row >= 0
        self.remove.setEnabled(has)
        self.name.setEnabled(has)
        self.up.setEnabled(has and row > 0)
        self.down.setEnabled(has and row < len(self._names) - 1)
        self.note.setVisible(len(self._names) > 1)

    # ─────────────────────────────── المخرجات ───────────────────────────────

    def editor(self, row: int) -> QWidget:
        """محرّر المقطع رقم `row` — للاختبارات وللوصول البرمجي."""
        return self.stack.widget(row + 1)

    def segments(self) -> list[Segment]:
        return [
            Segment(self._names[row], self.editor(row).content())
            for row in range(len(self._names))
        ]

    def street_crossings(self) -> dict:
        """أطوال عبور الشوارع وأعداد مغذياتها — للمشروع كله (ق-٣٠، ق-٤٥)."""
        return {
            "street_crossing_secondary_m": self.street_secondary.value(),
            "street_crossing_secondary_feeders": self.street_secondary_feeders.value(),
            "street_crossing_main_m": self.street_main.value(),
            "street_crossing_main_feeders": self.street_main_feeders.value(),
        }

    def refresh_street_hint(self, catalog: dict) -> None:
        """يُظهر أن التعرفة **لمغذٍّ ولمتر**، وأن الأنبوب لا يتبع المغذيات (ق-٤٥)."""
        from engine.underground import PIPE_LENGTH_M, SPARE_PIPES

        rates = catalog["أجور_العمل"]
        rows = []
        for length, feeders, label, has_pipes in (
            (self.street_secondary.value(), self.street_secondary_feeders.value(),
             "عبور الشوارع الفرعية", True),
            (self.street_main.value(), self.street_main_feeders.value(),
             "عبور الشوارع الرئيسية – حفر مخفي", False),
        ):
            if not (length and feeders):
                continue
            rate = rates[label]["السعر"]
            row = (
                f"<b>{label}</b>: {length:,.0f} م × {feeders} مغذيات"
                f" × {rate:,.0f} = <b>{length * feeders * rate:,.0f} د</b>"
            )
            if has_pipes:
                per_feeder = math.ceil(round(length / PIPE_LENGTH_M, 9))
                row += (
                    f"<br>&nbsp;&nbsp;– أنبوب 8 انج: ⌈{length:,.0f} ÷ {PIPE_LENGTH_M}⌉"
                    f" × {feeders} + {SPARE_PIPES} احتياط ="
                    f" <b>{per_feeder * feeders + SPARE_PIPES}</b>"
                    " &nbsp;<i>(كمية بلا كلفة)</i>"
                )
            else:
                row += "<br>&nbsp;&nbsp;<i>حفر مخفي — بلا أنبوب</i>"
            rows.append(row)
        self.street_hint.setText(
            "<br>".join(rows)
            or "التعرفة <b>لمغذٍّ واحد ولمتر واحد</b> — تُضرب بالطول وبعدد المغذيات."
        )
