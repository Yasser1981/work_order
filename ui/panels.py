# -*- coding: utf-8 -*-
"""لوحتا إدخال الشبكة الهوائية — 11 ك.ف و33 ك.ف."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from engine.overhead import (
    resolve_spans,
    suggest_poles_11kv,
    suggest_poles_33kv,
    wire_quantity,
)
from engine.types import (
    BracketPattern,
    CircuitType,
    Network11kV,
    Network33kV,
    SupplyForm,
)

from .widgets import HintLabel, number_field, scroll_body, section


def _combo(options: list) -> QComboBox:
    box = QComboBox()
    for opt in options:
        box.addItem(opt.value, opt)
    return box


class Panel11kV(QWidget):
    """مدخلات شبكة 11 ك.ف الهوائية."""

    changed = pyqtSignal()

    def __init__(self, catalog: dict) -> None:
        super().__init__()
        self.catalog = catalog
        self._build()
        self._connect()
        self.refresh_hints()

    # ─────────────────────────────── البناء ───────────────────────────────

    def _build(self) -> None:
        body, layout = scroll_body()

        # المسار والسلك
        box, form = section("المسار والسلك")
        self.route = number_field(0, 500_000, 500, suffix="م")
        self.circuit = _combo([CircuitType.SINGLE, CircuitType.DOUBLE])
        self.waste_included = QCheckBox("الطول المُدخل يشمل نسبة الزيادة")
        self.waste_pct = number_field(0, 100, 10, decimals=1, step=0.5, suffix="%")
        form.addRow("طول مسار الشبكة:", self.route)
        form.addRow("نوع الدائرة:", self.circuit)
        form.addRow("", self.waste_included)
        form.addRow("نسبة الزيادة:", self.waste_pct)
        self.wire_hint = HintLabel()
        form.addRow(self.wire_hint)
        layout.addWidget(box)

        # الأعمدة
        box, form = section("الأعمدة  —  الحساب استرشادي وغير مُلزِم")
        self.span = number_field(1, 500, 25, suffix="م")
        self.tension_span = number_field(1, 5000, 125, suffix="م")
        form.addRow("المسافة بين الأعمدة:", self.span)
        form.addRow("المسافة بين أعمدة الشد:", self.tension_span)
        self.poles_hint = HintLabel()
        form.addRow(self.poles_hint)
        self.adopt = QPushButton("اعتماد القيم المقترحة  ↓")
        form.addRow(self.adopt)
        self.lattice = number_field(0, 100_000, 5)
        self.round_ = number_field(0, 100_000, 20)
        form.addRow("عدد أعمدة مشبك 11م:", self.lattice)
        form.addRow("عدد أعمدة مدوّر 11م:", self.round_)
        layout.addWidget(box)

        # التوريد والبراكيت
        box, form = section("شكل التوريد والبراكيت")
        self.lattice_supply = _combo(
            [SupplyForm.WITHOUT_ACCESSORIES, SupplyForm.WITH_ACCESSORIES]
        )
        self.round_supply = _combo(
            [SupplyForm.WITHOUT_ACCESSORIES, SupplyForm.WITH_ACCESSORIES]
        )
        self.pattern = _combo([BracketPattern.STANDARD, BracketPattern.ALTERNATIVE])
        self.extra_12 = number_field(0, 10_000, 0)
        self.extra_14 = number_field(0, 10_000, 0)
        form.addRow("شكل العمود المشبك:", self.lattice_supply)
        form.addRow("شكل العمود المدوّر:", self.round_supply)
        form.addRow("نمط البراكيت (للمزدوجة):", self.pattern)
        self.bracket_hint = HintLabel()
        form.addRow(self.bracket_hint)
        form.addRow("براكيت 1.2م إضافي:", self.extra_12)
        form.addRow("براكيت 1.4م إضافي:", self.extra_14)
        layout.addWidget(box)

        # ستي رود
        box, form = section("ستي رود")
        self.stay = number_field(0, 10_000, 0)
        form.addRow("عدد الأطقم على أعمدة 11م:", self.stay)
        self.stay_hint = HintLabel()
        form.addRow(self.stay_hint)
        layout.addWidget(box)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _connect(self) -> None:
        for w in (self.route, self.waste_pct, self.span, self.tension_span,
                  self.lattice, self.round_, self.extra_12, self.extra_14, self.stay):
            w.valueChanged.connect(self._on_change)
        for w in (self.circuit, self.lattice_supply, self.round_supply, self.pattern):
            w.currentIndexChanged.connect(self._on_change)
        self.waste_included.toggled.connect(self._on_change)
        self.adopt.clicked.connect(self._adopt_suggestion)

    # ─────────────────────────────── السلوك ───────────────────────────────

    def _on_change(self) -> None:
        self.refresh_hints()
        self.changed.emit()

    def _adopt_suggestion(self) -> None:
        """ق-١٠: ينقل المقترح الاسترشادي إلى الأعداد المعتمدة."""
        result = suggest_poles_11kv(self.network(), self.catalog)
        self.lattice.setValue(result.lattice)
        self.round_.setValue(result.round_)

    def network(self) -> Network11kV:
        return Network11kV(
            route_length_m=self.route.value(),
            circuit=self.circuit.currentData(),
            length_includes_waste=self.waste_included.isChecked(),
            waste_pct=self.waste_pct.value() / 100.0,
            span_m=self.span.value(),
            tension_span_m=self.tension_span.value(),
            poles_lattice=self.lattice.value(),
            poles_round=self.round_.value(),
            lattice_supply=self.lattice_supply.currentData(),
            round_supply=self.round_supply.currentData(),
            bracket_pattern=self.pattern.currentData(),
            extra_bracket_12=self.extra_12.value(),
            extra_bracket_14=self.extra_14.value(),
            stay_rod_sets=self.stay.value(),
        )

    def refresh_hints(self) -> None:
        net = self.network()
        double = net.circuit is CircuitType.DOUBLE
        self.waste_pct.setEnabled(not net.length_includes_waste)
        self.pattern.setEnabled(double)

        # سطر حساب السلك
        factor = 1.0 if net.length_includes_waste else 1 + net.waste_pct
        qty = wire_quantity(
            net.route_length_m, net.circuit, net.length_includes_waste, net.waste_pct
        )
        self.wire_hint.setText(
            f"كمية السلك = {net.route_length_m:,.0f} × 3 أطوار × {net.circuit.circuits} دائرة"
            f" × {factor:g} = <b>{qty:,} م</b>"
        )

        # سطر اقتراح الأعمدة
        span, tension = resolve_spans(net, self.catalog)
        s = suggest_poles_11kv(net, self.catalog)
        step = int(tension // span) or 1
        note = " — حُوِّل العمود الأخير إلى مشبك" if s.end_converted else ""
        self.poles_hint.setText(
            f"المقترح: <b>{s.total}</b> عموداً — <b>{s.lattice}</b> مشبك و<b>{s.round_}</b> مدوّر."
            f"<br>عمود شد كل {step} أعمدة ({step * span:g} م){note}."
        )

        # سطر البراكيت
        if double:
            std = net.bracket_pattern is BracketPattern.STANDARD
            self.bracket_hint.setText(
                "مزدوجة قياسي: مدوّر 2×1.2 + 1×1.4 — مشبك 4×1.2 + 2×1.4"
                if std
                else "مزدوجة بديل: مدوّر 3×1.2 — مشبك 6×1.4"
            )
        else:
            self.bracket_hint.setText("مفردة: مدوّر 1×1.2 — مشبك 2×1.4")

        self.stay_hint.setText(
            f"واير ستي = {self.stay.value()} × 12 م = <b>{self.stay.value() * 12:,} م</b>"
        )


class Panel33kV(QWidget):
    """مدخلات شبكة 33 ك.ف الهوائية."""

    changed = pyqtSignal()

    def __init__(self, catalog: dict) -> None:
        super().__init__()
        self.catalog = catalog
        self._build()
        self._connect()
        self.refresh_hints()

    def _build(self) -> None:
        body, layout = scroll_body()

        box, form = section("المسار والسلك")
        self.route = number_field(0, 500_000, 0, suffix="م")
        self.circuit = _combo([CircuitType.SINGLE, CircuitType.DOUBLE])
        self.waste_included = QCheckBox("الطول المُدخل يشمل نسبة الزيادة")
        self.waste_pct = number_field(0, 100, 10, decimals=1, step=0.5, suffix="%")
        form.addRow("طول مسار الشبكة:", self.route)
        form.addRow("نوع الدائرة:", self.circuit)
        form.addRow("", self.waste_included)
        form.addRow("نسبة الزيادة:", self.waste_pct)
        self.wire_hint = HintLabel()
        form.addRow(self.wire_hint)
        layout.addWidget(box)

        box, form = section("الأعمدة والركائز  —  الحساب استرشادي وغير مُلزِم")
        self.span = number_field(1, 500, 65, suffix="م")
        self.tension_span = number_field(1, 5000, 650, suffix="م")
        self.end_anchors = number_field(0, 2, 2)
        form.addRow("المسافة بين أعمدة التعليق:", self.span)
        form.addRow("المسافة بين الركائز الوسطية:", self.tension_span)
        form.addRow("ركيزة بداية ونهاية:", self.end_anchors)
        self.poles_hint = HintLabel()
        form.addRow(self.poles_hint)
        self.adopt = QPushButton("اعتماد القيم المقترحة  ↓")
        form.addRow(self.adopt)
        self.suspension = number_field(0, 100_000, 0)
        self.anchors_mid = number_field(0, 10_000, 0)
        self.anchors_end = number_field(0, 10_000, 0)
        form.addRow("عدد أعمدة 14م تعليق:", self.suspension)
        form.addRow("عدد ركائز شد وسطية:", self.anchors_mid)
        form.addRow("عدد ركائز بداية ونهاية:", self.anchors_end)
        layout.addWidget(box)

        box, form = section("شكل التوريد والبراكيت")
        self.supply = _combo(
            [SupplyForm.WITHOUT_ACCESSORIES, SupplyForm.WITH_ACCESSORIES]
        )
        self.extra_2 = number_field(0, 10_000, 0)
        self.extra_25 = number_field(0, 10_000, 0)
        form.addRow("شكل عمود مشبك 14م:", self.supply)
        self.bracket_hint = HintLabel()
        form.addRow(self.bracket_hint)
        form.addRow("براكيت 2م إضافي:", self.extra_2)
        form.addRow("براكيت 2.5م إضافي:", self.extra_25)
        layout.addWidget(box)

        box, form = section("ستي رود")
        self.stay = number_field(0, 10_000, 0)
        form.addRow("عدد الأطقم على أعمدة 14م:", self.stay)
        self.stay_hint = HintLabel()
        form.addRow(self.stay_hint)
        layout.addWidget(box)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _connect(self) -> None:
        for w in (self.route, self.waste_pct, self.span, self.tension_span,
                  self.end_anchors, self.suspension, self.anchors_mid,
                  self.anchors_end, self.extra_2, self.extra_25, self.stay):
            w.valueChanged.connect(self._on_change)
        for w in (self.circuit, self.supply):
            w.currentIndexChanged.connect(self._on_change)
        self.waste_included.toggled.connect(self._on_change)
        self.adopt.clicked.connect(self._adopt_suggestion)

    def _on_change(self) -> None:
        self.refresh_hints()
        self.changed.emit()

    def _adopt_suggestion(self) -> None:
        s = suggest_poles_33kv(self.network(), self.catalog, self.end_anchors.value())
        self.suspension.setValue(s.suspension)
        self.anchors_mid.setValue(s.mid_anchors)
        self.anchors_end.setValue(s.end_anchors)

    def network(self) -> Network33kV:
        return Network33kV(
            route_length_m=self.route.value(),
            circuit=self.circuit.currentData(),
            length_includes_waste=self.waste_included.isChecked(),
            waste_pct=self.waste_pct.value() / 100.0,
            span_m=self.span.value(),
            tension_span_m=self.tension_span.value(),
            poles_suspension=self.suspension.value(),
            anchors_mid=self.anchors_mid.value(),
            anchors_end=self.anchors_end.value(),
            pole_supply=self.supply.currentData(),
            extra_bracket_2=self.extra_2.value(),
            extra_bracket_25=self.extra_25.value(),
            stay_rod_sets=self.stay.value(),
        )

    def refresh_hints(self) -> None:
        net = self.network()
        double = net.circuit is CircuitType.DOUBLE
        self.waste_pct.setEnabled(not net.length_includes_waste)

        factor = 1.0 if net.length_includes_waste else 1 + net.waste_pct
        qty = wire_quantity(
            net.route_length_m, net.circuit, net.length_includes_waste, net.waste_pct
        )
        self.wire_hint.setText(
            f"كمية السلك = {net.route_length_m:,.0f} × 3 أطوار × {net.circuit.circuits} دائرة"
            f" × {factor:g} = <b>{qty:,} م</b>"
        )

        span, tension = resolve_spans(net, self.catalog)
        s = suggest_poles_33kv(net, self.catalog, self.end_anchors.value())
        self.poles_hint.setText(
            f"المقترح: <b>{s.positions}</b> موقعاً — <b>{s.suspension}</b> عمود تعليق،"
            f" <b>{s.mid_anchors}</b> ركيزة وسطية، <b>{s.end_anchors}</b> ركيزة بداية ونهاية."
            f"<br>مجموع أعمدة 14م = <b>{s.poles_total}</b> (كل ركيزة عمودان)."
        )

        need = net.poles_suspension * (3 if double else 1)
        included = (net.poles_suspension + (net.anchors_mid + net.anchors_end) * 2) \
            if net.pole_supply.includes_bracket else 0
        buy = max(0, need - included)
        self.bracket_hint.setText(
            f"براكيت 2م: الحاجة {need} − المرفق {included} = <b>{buy}</b> للشراء"
            + (f" (فائض {included - need} مُهمَل)" if included > need else "")
        )
        self.stay_hint.setText(
            f"واير ستي = {self.stay.value()} × 15 م = <b>{self.stay.value() * 15:,} م</b>"
        )
