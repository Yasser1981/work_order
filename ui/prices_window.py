# -*- coding: utf-8 -*-
"""شاشة إدارة الأسعار — تحرير أسعار المواد والأجور من داخل البرنامج (ق-٦٢).

**القاعدة التي تحكم هذه الشاشة:** الاعتماد يُنشئ **نسخة أسعار جديدة** ولا يُعدّل
نسخةً قائمة. فأمر عمل قديم يشير إلى «2026-08» يبقى على أسعار آب حرفياً، لأن ملف
آب نفسه لم يُمسّ. ولو حُرّر مكانه لتغيّرت كلفة كل أمر عمل قديم بلا أن ينبّه أحد.

والشاشة تعرض **ما سيتغيّر قبل أن يتغيّر**: جدول المقارنة يُظهر السعر قبل وبعد
ومقدار الفرق، فلا يُعتمد تعديل على غير بصيرة.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engine.prices import (
    LABOUR,
    MATERIALS,
    apply_edits,
    differences,
    editable_rows,
    next_version,
    save_as_new_version,
)

from .widgets import HintLabel

UNPRICED = "— غير مُسعَّر —"
"""نصّ السعر الغائب. الفراغ في الخانة يعني «غير مُسعَّر»، لا صفراً (ق-٩)."""


class PricesWindow(QDialog):
    """جدول الأسعار قابلاً للتحرير، والاعتماد يُصدر نسخة جديدة."""

    def __init__(self, catalog: dict, version: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.original = catalog
        self.version = version
        self.new_version: str | None = None
        self.setWindowTitle(f"إدارة الأسعار  —  النسخة الحالية {version}")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1000, 700)
        self._rows = editable_rows(catalog)
        self._build()
        self._fill()

    # ─────────────────────────────── البناء ───────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(HintLabel(
            "عدّل السعر في عمود <b>السعر الجديد</b>. والاعتماد <b>لا يغيّر النسخة "
            "الحالية</b> بل يُنشئ نسخة جديدة، فتبقى أوامر العمل القديمة على "
            "أسعارها كما أُنشئت (ق-٤٠).<br>"
            "اترك الخانة <b>فارغة</b> لتجعل البند «غير مُسعَّر» — فيظهر تحذيراً "
            "أصفر ولا يُحتسب صفراً بصمت.<br>"
            "<b>المادة المشتقّة</b> (كالعمود العاري) تُعرض ولا تُحرَّر: سعرها يتبع "
            "أصله، فحرِّر الأصل ويتبعه المشتقّ (ق-٥٨)."
        ))

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("بحث في أسماء المواد والأجور…")
        self.filter.textChanged.connect(self._apply_filter)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("بحث:"))
        bar.addWidget(self.filter, stretch=1)
        self.counter = QLabel()
        bar.addWidget(self.counter)
        layout.addLayout(bar)

        self.table = QTableWidget(len(self._rows), 5)
        self.table.setHorizontalHeaderLabels(
            ["الباب", "البند", "الوحدة", "السعر الحالي", "السعر الجديد"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (0, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._on_edit)
        layout.addWidget(self.table, stretch=1)

        self.summary = HintLabel()
        layout.addWidget(self.summary)

        buttons = QDialogButtonBox()
        self.apply_button = buttons.addButton(
            "اعتماد وإصدار نسخة جديدة", QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton("إلغاء", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.commit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _fill(self) -> None:
        self.table.blockSignals(True)
        for r, row in enumerate(self._rows):
            for c, text in enumerate((
                "مادة" if row["الباب"] == MATERIALS else "أجر",
                row["الاسم"],
                row["الوحدة"],
                UNPRICED if row["السعر"] is None else f"{row['السعر']:,.0f}",
            )):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c in (0, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if row["السعر"] is None:
                    item.setForeground(QColor("#b45309"))
                if row["ملاحظة"]:
                    item.setToolTip(row["ملاحظة"])
                self.table.setItem(r, c, item)

            new = QTableWidgetItem("" if row["السعر"] is None else f"{row['السعر']:.0f}")
            new.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if not row["محرَّر"]:
                new.setFlags(new.flags() & ~Qt.ItemFlag.ItemIsEditable)
                new.setText("مشتقّ")
                new.setForeground(QColor("#6b7280"))
                new.setToolTip(row["ملاحظة"] or "سعر مشتقّ — يتبع أصله ولا يُحرَّر.")
            self.table.setItem(r, 4, new)
        self.table.blockSignals(False)
        self._apply_filter("")      # يُظهر العدد الكلّي قبل أي بحث
        self._refresh_summary()

    # ─────────────────────────────── السلوك ───────────────────────────────

    NEW_COLUMN = 4

    def _apply_filter(self, text: str) -> None:
        needle = text.strip()
        shown = 0
        for r, row in enumerate(self._rows):
            hidden = bool(needle) and needle not in row["الاسم"]
            self.table.setRowHidden(r, hidden)
            shown += not hidden
        self.counter.setText(f"{shown} من {len(self._rows)}")

    def _on_edit(self, item: QTableWidgetItem) -> None:
        if item.column() == self.NEW_COLUMN:
            self._refresh_summary()

    def _parse(self, row: int) -> float | None | str:
        """السعر المُدخل في السطر: رقم، أو None لغير المُسعَّر، أو نصّ خطأ."""
        if not self._rows[row]["محرَّر"]:
            return self._rows[row]["السعر"]
        text = (self.table.item(row, self.NEW_COLUMN).text() or "").strip()
        text = text.replace(",", "").replace("،", "").replace("٬", "")
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return f"«{text}» ليس رقماً"
        if value < 0:
            return "السعر لا يكون سالباً"
        return value

    def edits(self) -> tuple[list[dict], list[str]]:
        """التعديلات المطلوبة وأخطاء الإدخال — لا يُعتمد شيء وفيها خطأ."""
        changes, errors = [], []
        for r, row in enumerate(self._rows):
            if not row["محرَّر"]:
                continue
            value = self._parse(r)
            if isinstance(value, str):
                errors.append(f"{row['الاسم']}: {value}")
                continue
            if value != row["السعر"]:
                changes.append({**row, "السعر": value, "السعر_السابق": row["السعر"]})
        return changes, errors

    def _refresh_summary(self) -> None:
        changes, errors = self.edits()
        if errors:
            self.summary.setText(
                "⚠️ <b>أخطاء إدخال تمنع الاعتماد:</b><br>" + "<br>".join(errors[:6])
                + (f"<br>… و{len(errors) - 6} غيرها" if len(errors) > 6 else "")
            )
            self.apply_button.setEnabled(False)
            return
        self.apply_button.setEnabled(bool(changes))
        if not changes:
            self.summary.setText("لا تعديل بعد — عدّل سعراً ليُفعَّل زرّ الاعتماد.")
            return
        lines = []
        for change in changes[:8]:
            before = "غير مُسعَّر" if change["السعر_السابق"] is None else \
                f"{change['السعر_السابق']:,.0f}"
            after = "غير مُسعَّر" if change["السعر"] is None else f"{change['السعر']:,.0f}"
            lines.append(f"• <b>{change['الاسم']}</b>: {before} ← {after}")
        more = f"<br>… و{len(changes) - 8} تعديلاً آخر" if len(changes) > 8 else ""
        self.summary.setText(
            f"<b>{len(changes)}</b> تعديلاً سيصدر في نسخة جديدة:<br>"
            + "<br>".join(lines) + more
        )

    # ─────────────────────────────── الاعتماد ───────────────────────────────

    def commit(self) -> str | None:
        """يطبّق التعديلات ويكتب نسخة جديدة، ويعيد اسمها — أو None عند الإلغاء."""
        changes, errors = self.edits()
        if errors:
            QMessageBox.warning(self, "إدخال غير صالح",
                                "صحّح ما يلي قبل الاعتماد:\n" + "\n".join(errors))
            return None
        if not changes:
            QMessageBox.information(self, "لا تعديل", "لم يتغيّر أي سعر.")
            return None

        edited = apply_edits(self.original, changes)
        diff = differences(self.original, edited)
        version = next_version()
        detail = "\n".join(
            f"• {d['الاسم']}: "
            f"{'غير مُسعَّر' if d['قبل'] is None else format(d['قبل'], ',.0f')}"
            f" ← {'غير مُسعَّر' if d['بعد'] is None else format(d['بعد'], ',.0f')}"
            for d in diff[:12]
        )
        more = f"\n… و{len(diff) - 12} غيرها" if len(diff) > 12 else ""
        answer = QMessageBox.question(
            self, "اعتماد نسخة أسعار جديدة",
            f"ستُنشَأ نسخة أسعار جديدة باسم «{version}» فيها {len(diff)} تغييراً:\n\n"
            f"{detail}{more}\n\n"
            f"والنسخة الحالية «{self.version}» تبقى كما هي، فلا تتغيّر كلفة أي "
            "أمر عمل قديم يشير إليها.\n\nأتابع؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return None

        try:
            path = save_as_new_version(edited, version)
        except (OSError, FileExistsError) as exc:
            QMessageBox.critical(self, "تعذّر الحفظ", str(exc))
            return None

        self.new_version = version
        QMessageBox.information(
            self, "صدرت نسخة جديدة",
            f"حُفظت النسخة «{version}» في:\n{path.name}\n\n"
            "أمر العمل المفتوح انتقل إليها. والأوامر القديمة تبقى على نسخها."
        )
        self.accept()
        return version


def open_prices(parent, catalog: dict, version: str) -> str | None:
    """يفتح الشاشة ويعيد اسم النسخة الجديدة إن اعتُمدت، وإلا None."""
    dialog = PricesWindow(catalog, version, parent)
    dialog.exec()
    return dialog.new_version
