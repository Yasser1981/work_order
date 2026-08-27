# -*- coding: utf-8 -*-
"""لوحات الإدخال — 11 ك.ف و33 ك.ف والضغط الواطئ والتجهيزات."""

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

from engine.equipment import (
    CABLE_HEAD_M,
    CAGES_PER_CABLE_HEAD_POLE,
    M_BRACKET_21,
    CABLE_MID_NETWORK_M,
    ISOLATOR_KITS,
    TRANSFORMER_KITS,
    TRANSFORMER_OUTPUTS,
    TRANSFORMER_SIZES_BY_VOLTAGE,
    TransformerVoltage,
    suggest_lattice_cages,
)
from engine.lowvoltage import conductor_quantity, count_poles_lv
from engine.underground import (
    BOXES_PER_END_SET_33,
    cable_count_33,
    cable_quantity,
    cable_quantity_33,
    civil_tariff_parts,
    is_wide_trench,
    trench_materials,
    trench_width_m,
    suggest_straight_boxes,
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
    Equipment,
    LVNetworkType,
    Network11kV,
    Network33kV,
    NetworkLV,
    SidewalkType,
    SupplyForm,
    Underground11kV,
    Underground33kV,
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
        form.addRow("براكيت جنل 1.2م إضافي:", self.extra_12)
        form.addRow("براكيت جنل 1.4م إضافي:", self.extra_14)
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

    def content(self) -> Network11kV:
        return self.network()

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
        form.addRow("براكيت جنل 2م إضافي:", self.extra_2)
        form.addRow("براكيت جنل 2.5م إضافي:", self.extra_25)
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

    def content(self) -> Network33kV:
        return self.network()

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
            f"براكيت جنل 2م: الحاجة {need} − المرفق {included} = <b>{buy}</b> للشراء"
            + (f" (فائض {included - need} مُهمَل)" if included > need else "")
        )
        self.stay_hint.setText(
            f"واير ستي = {self.stay.value()} × 15 م = <b>{self.stay.value() * 15:,} م</b>"
        )


class PanelLV(QWidget):
    """مدخلات شبكة الضغط الواطئ (ق-٢٢).

    داخل مقطع (`as_segment=True`) يختفي مربّع «المشروع يتضمّن شبكة ضغط واطئ»:
    وجود المقطع نفسه هو التفعيل، ومربّع تفعيل ثانٍ فوقه يُربك لا أكثر (ق-٢٤).
    """

    changed = pyqtSignal()

    def __init__(self, catalog: dict, as_segment: bool = False) -> None:
        super().__init__()
        self.catalog = catalog
        self.as_segment = as_segment
        self._build()
        if as_segment:
            self.enabled.setChecked(True)
            self.enabled.setVisible(False)
        self._connect()
        self.refresh_hints()

    def _build(self) -> None:
        body, layout = scroll_body()

        box, form = section("المسار والموصل")
        self.enabled = QCheckBox("المشروع يتضمّن شبكة ضغط واطئ")
        self.route = number_field(0, 500_000, 0, suffix="م")
        self.kind = _combo([LVNetworkType.BARE_WIRES, LVNetworkType.BUNDLED_CABLE])
        self.waste_included = QCheckBox("الطول المُدخل يشمل نسبة الزيادة")
        self.waste_pct = number_field(0, 100, 10, decimals=1, step=0.5, suffix="%")
        form.addRow(self.enabled)
        form.addRow("طول مسار الشبكة:", self.route)
        form.addRow("نوع الشبكة:", self.kind)
        form.addRow("", self.waste_included)
        form.addRow("نسبة الزيادة:", self.waste_pct)
        self.wire_hint = HintLabel()
        form.addRow(self.wire_hint)
        layout.addWidget(box)

        box, form = section("أعمدة 9م  —  الحساب استرشادي وغير مُلزِم")
        self.span = number_field(1, 500, 20, suffix="م")
        self.tension_span = number_field(1, 5000, 100, suffix="م")
        form.addRow("المسافة بين الأعمدة:", self.span)
        form.addRow("المسافة بين أعمدة الشد:", self.tension_span)
        self.poles_hint = HintLabel()
        form.addRow(self.poles_hint)
        self.adopt = QPushButton("اعتماد القيم المقترحة  ↓")
        form.addRow(self.adopt)
        self.lattice = number_field(0, 100_000, 0)
        self.round_ = number_field(0, 100_000, 0)
        form.addRow("عدد أعمدة 9م مشبك:", self.lattice)
        form.addRow("عدد أعمدة 9م مدوّر:", self.round_)
        self.accessory_hint = HintLabel()
        form.addRow(self.accessory_hint)
        layout.addWidget(box)

        box, form = section("الشبكة على أعمدة الضغط العالي")
        self.on_hv = QCheckBox("تمرّ شبكة الضغط الواطئ على أعمدة الضغط العالي")
        self.hv_kind = _combo([LVNetworkType.BUNDLED_CABLE, LVNetworkType.BARE_WIRES])
        self.hv_lattice = number_field(0, 100_000, 0)
        self.hv_round = number_field(0, 100_000, 0)
        form.addRow(self.on_hv)
        form.addRow("نوع الشبكة على تلك الأعمدة:", self.hv_kind)
        form.addRow("عدد أعمدة ض.ع مشبك:", self.hv_lattice)
        form.addRow("عدد أعمدة ض.ع مدوّر:", self.hv_round)
        self.hv_hint = HintLabel()
        form.addRow(self.hv_hint)
        layout.addWidget(box)

        box, form = section("المستهلكون")
        self.consumers = number_field(0, 100_000, 0)
        form.addRow("عدد المستهلكين:", self.consumers)
        self.consumer_hint = HintLabel()
        form.addRow(self.consumer_hint)
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
                  self.lattice, self.round_, self.hv_lattice, self.hv_round,
                  self.consumers):
            w.valueChanged.connect(self._on_change)
        for w in (self.kind, self.hv_kind):
            w.currentIndexChanged.connect(self._on_change)
        for w in (self.enabled, self.waste_included, self.on_hv):
            w.toggled.connect(self._on_change)
        self.adopt.clicked.connect(self._adopt_suggestion)

    def _on_change(self) -> None:
        self.refresh_hints()
        self.changed.emit()

    def _adopt_suggestion(self) -> None:
        net = self.network() or self._raw_network()
        span, tension = self.span.value(), self.tension_span.value()
        result = count_poles_lv(net.route_length_m, span, tension)
        self.lattice.setValue(result.lattice)
        self.round_.setValue(result.round_)

    def _raw_network(self) -> NetworkLV:
        """الشبكة كما تصفها الحقول، بصرف النظر عن مربّع التفعيل."""
        return NetworkLV(
            route_length_m=self.route.value(),
            kind=self.kind.currentData(),
            length_includes_waste=self.waste_included.isChecked(),
            waste_pct=self.waste_pct.value() / 100.0,
            span_m=self.span.value(),
            tension_span_m=self.tension_span.value(),
            poles_lattice=self.lattice.value(),
            poles_round=self.round_.value(),
            consumers=self.consumers.value(),
            on_hv_poles=self.on_hv.isChecked(),
            hv_kind=self.hv_kind.currentData(),
            hv_poles_lattice=self.hv_lattice.value(),
            hv_poles_round=self.hv_round.value(),
        )

    def content(self) -> NetworkLV:
        """محتوى المقطع — وجود المقطع نفسه هو التفعيل، فلا يمرّ عبر مربّع الاختيار."""
        return self._raw_network()

    def network(self) -> NetworkLV | None:
        """None حين لا يتضمّن المشروع شبكة ضغط واطئ."""
        return self._raw_network() if self.enabled.isChecked() else None

    def refresh_hints(self) -> None:
        net = self._raw_network()
        on = self.enabled.isChecked()
        for w in (self.route, self.kind, self.waste_included, self.waste_pct,
                  self.span, self.tension_span, self.adopt, self.lattice,
                  self.round_, self.on_hv, self.consumers):
            w.setEnabled(on)
        self.waste_pct.setEnabled(on and not net.length_includes_waste)
        for w in (self.hv_kind, self.hv_lattice, self.hv_round):
            w.setEnabled(on and self.on_hv.isChecked())

        factor = 1.0 if net.length_includes_waste else 1 + net.waste_pct
        qty = conductor_quantity(net)
        material = ("سلك ألمنيوم 95 ملم²" if net.kind is LVNetworkType.BARE_WIRES
                    else "قابلو ألمنيوم معلق")
        self.wire_hint.setText(
            f"{material} = {net.route_length_m:,.0f} × {net.kind.conductors}"
            f" × {factor:g} = <b>{qty:,} م</b>"
            + ("<br>الأسلاك 4 موصلات: 3 حارة و1 بارد."
               if net.kind is LVNetworkType.BARE_WIRES
               else "<br>القابلو المعلق كابل واحد يضمّ الموصلات — لا يُضرب.")
        )

        s = count_poles_lv(net.route_length_m, self.span.value(), self.tension_span.value())
        step = int(self.tension_span.value() // self.span.value()) or 1
        self.poles_hint.setText(
            f"المقترح: <b>{s.total}</b> عموداً — <b>{s.lattice}</b> مشبك و<b>{s.round_}</b> مدوّر."
            f"<br>عمود شد كل {step} أعمدة ({step * self.span.value():g} م)."
        )

        lat, rnd = net.poles_lattice, net.poles_round
        if net.kind is LVNetworkType.BARE_WIRES:
            self.accessory_hint.setText(
                f"بوكس كلامب = {lat}×8 + {rnd}×4 = <b>{lat * 8 + rnd * 4:,}</b>"
                f" &nbsp;·&nbsp; معدات ربط ألمنيوم = {lat}×8 = <b>{lat * 8:,}</b>"
            )
        else:
            self.accessory_hint.setText(
                f"هوك تعليق = {lat}×2 + {rnd}×1 = <b>{lat * 2 + rnd:,}</b>"
                f" &nbsp;·&nbsp; كلامب شد = <b>{lat * 2:,}</b>"
                f" &nbsp;·&nbsp; كلامب تعليق = <b>{rnd:,}</b>"
                f"<br>كونكتر القابلو = {lat}×5 = <b>{lat * 5:,}</b> (نهايات بكرة — للمشبك فقط)"
            )

        self.hv_hint.setText(
            "تُضاف الكلامبات وحدها — الأعمدة قائمة أصلاً أو محسوبة في قسم الضغط العالي، "
            "فلا تُحتسب أعمدة ولا تأريض ولا كونكريت."
        )
        self.consumer_hint.setText(
            f"كونكتر ربط مشتركين = {self.consumers.value()} × 1 = "
            f"<b>{self.consumers.value():,}</b> &nbsp;—&nbsp; السعر والأجر غير محدَّدين بعد."
        )


class PanelEquipment(QWidget):
    """مدخلات التجهيزات على الأعمدة — المحولة والفواصل والقفيص (ق-٢٣).

    لا تتبع طول المسار، فليس فيها اقتراح ولا زرّ اعتماد: يُدخل المستخدم العدد،
    وتُعرض تحته قائمة الملحقات التي يجرّها كي يرى ما دخل التخمين قبل الطباعة.
    """

    changed = pyqtSignal()

    def __init__(self, catalog: dict) -> None:
        super().__init__()
        self.catalog = catalog
        self._build()
        self._connect()
        self.refresh_hints()

    def _build(self) -> None:
        body, layout = scroll_body()

        # صندوق لكل جهد تحويلي، وسعة لكل صفّ داخله (ق-٣٧).
        # قاطع الدورة يتبع السعة رقماً برقم ولا يتبع الجهد (ق-٢٦).
        self.transformers = {}
        for voltage, sizes in TRANSFORMER_SIZES_BY_VOLTAGE.items():
            box, form = section(f"المحولات  —  جهد {voltage.value}")
            for size in sizes:
                outputs, amps = TRANSFORMER_OUTPUTS[size]
                field = number_field(0, 1000, 0)
                self.transformers[(voltage, size)] = field
                form.addRow(
                    f"عدد محولات {size.label}   ({outputs} × قاطع {amps} أمبير):",
                    field,
                )
            if voltage is TransformerVoltage.KV33:
                form.addRow(
                    HintLabel(
                        "مانعة الصواعق وفاصل الفيوز <b>33 ك.ف</b>، أما قاعدة "
                        "المانعة وقواطع الدورة فهي نفسها.<br>"
                        "سعة 250 متاحة بهذا الجهد أيضاً — <b>نادرة</b> لا ممتنعة."
                    )
                )
            layout.addWidget(box)
        self.transformer_hint = HintLabel()
        box, form = section("ملحقات المحولات")
        form.addRow(self.transformer_hint)
        layout.addWidget(box)

        # الفاصل نوعان بالجهد وحالتان بالموقع — أربعة حقول لا ثلاثة (ق-٢٥)
        box, form = section("الفواصل  —  الجهد × الموقع")
        self.isolators = {}
        labels = {
            "onload_11_mid": "فاصل هوائي 11 ك.ف ON LOAD 11 ك.ف — منتصف الشبكة:",
            "onload_11_head": "فاصل هوائي 11 ك.ف ON LOAD 11 ك.ف — على رأس القابلو:",
            "isolator_33_mid": "فاصل هوائي 33 ك.ف ON LOAD — منتصف الشبكة:",
            "isolator_33_head": "فاصل هوائي 33 ك.ف ON LOAD — على رأس القابلو:",
        }
        for attr, label in labels.items():
            field = number_field(0, 1000, 0)
            self.isolators[attr] = field
            setattr(self, attr, field)
            form.addRow(label, field)
        self.isolator_hint = HintLabel()
        form.addRow(self.isolator_hint)
        layout.addWidget(box)

        box, form = section("قفيص العمود المشبك  —  استرشادي وغير مُلزِم")
        self.cage_hint = HintLabel()
        form.addRow(self.cage_hint)
        self.adopt_cages = QPushButton("اعتماد القيمة المقترحة  ↓")
        form.addRow(self.adopt_cages)
        self.cages = number_field(0, 100_000, 0)
        form.addRow("عدد أقفاص العمود المشبك:", self.cages)
        layout.addWidget(box)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _connect(self) -> None:
        for w in (self.cages, *self.transformers.values(), *self.isolators.values()):
            w.valueChanged.connect(self._on_change)
        self.adopt_cages.clicked.connect(self._adopt_cages)

    def _adopt_cages(self) -> None:
        self.cages.setValue(suggest_lattice_cages(self.equipment()))

    def _on_change(self) -> None:
        self.refresh_hints()
        self.changed.emit()

    def content(self) -> Equipment:
        return self.equipment()

    def equipment(self) -> Equipment:
        return Equipment(
            transformers={
                key: field.value()
                for key, field in self.transformers.items()
                if field.value()
            },
            lattice_cages=self.cages.value(),
            **{attr: field.value() for attr, field in self.isolators.items()},
        )

    @staticmethod
    def _kit_text(kit: list, count: int) -> str:
        """يعرض ملحقات المجموعة الواحدة — مصدر السطور لا نتيجتها فقط."""
        return "<br>".join(
            f"&nbsp;&nbsp;– {name}: <b>{per * count:g}</b>" for (name, _unit), per in kit
        )

    def refresh_hints(self) -> None:
        eq = self.equipment()

        rows = []
        for key, count in eq.transformers.items():
            kit, label = TRANSFORMER_KITS[key]
            rows.append(f"<b>{label} × {count}</b><br>" + self._kit_text(kit, count))
        if not rows:
            rows.append(
                "<b>عدد المخارج يحكم القاطع والقابلو</b>، ولا قاطع رئيسي:<br>"
                "&nbsp;&nbsp;– 250 و400 KVA: مخرجان، قاطعان بسعة المحولة، "
                "وقابلو 1×150 بطول 80 م<br>"
                "&nbsp;&nbsp;– 630 KVA: <b>أربعة مخارج</b>، أربعة قواطع "
                "<b>400 أمبير</b> (لا 630)، وقابلو <b>160 م</b><br>"
                "وكل محولة تجرّ قاعدتها ولنك الفيوز ومانعة الصواعق والتأريض "
                "والترمنلات — وأجر نصبها يشملها كلها.<br>"
                "سعة 1000 KVA لا تُستخدم هوائياً — أرضية فقط."
            )
        self.transformer_hint.setText("<br>".join(rows))

        rows = []
        for attr, (kit, label) in ISOLATOR_KITS.items():
            count = getattr(eq, attr)
            if count:
                rows.append(f"<b>{label}</b><br>" + self._kit_text(kit, count))
        if not rows:
            rows.append(
                "منتصف الشبكة: <b>بلا مانعة صواعق</b>، وقابلو بطول "
                f"{CABLE_MID_NETWORK_M} م.<br>"
                "على رأس القابلو: <b>مع مانعة صواعق</b> وتأريضها، وقابلو "
                f"<b>{CABLE_HEAD_M} م</b> — نصف الكمية، لأن الربط بالشبكة الهوائية "
                "من جهة واحدة والجهة الثانية يربطها القابلو الأرضي."
            )
        rows.append(
            f"<b>{M_BRACKET_21[0]}</b>: واحد لكل فاصل في الجهدين معاً، "
            "وأجر تركيبه ضمن أجر نصب الفاصل (ق-٢٧)."
        )
        self.isolator_hint.setText("<br>".join(rows))

        heads = eq.onload_11_head + eq.isolator_33_head
        suggested = suggest_lattice_cages(eq)
        self.cage_hint.setText(
            f"<b>{CAGES_PER_CABLE_HEAD_POLE}</b> أقفاص لكل عمود مشبك عليه رأس قابلو."
            f"<br>أعمدة رأس القابلو = الفواصل على رأس القابلو في الجهدين:"
            f" <b>{heads}</b> ← المقترح <b>{suggested} قفيص</b>."
            "<br>بلا ملحقات وبلا أجر مستقل — يُركَّب مع العمود."
        )


def _trench_hint_text(feeder_count, route_length_m, catalog) -> str:
    """تلميح موادّ الخندق — يُظهر عرض الخندق ومصدر الكميات الثلاث (ق-٤٣).

    العرض هو الرقم الذي لا يراه المستخدم في أي حقل، ومع ذلك يحكم كمية الرمل
    وتضاعف الشتايكر والشريط. فعرضُه هنا يمنع أن يمرّ خطأ في عدد المغذيات صامتاً.
    """
    width = trench_width_m(feeder_count, catalog)
    if width is None:
        return f"⚠️ لا عرض خندق لـ{feeder_count} مغذيات في الجدول — الكميات لم تُحسب."
    lines = [f"عرض الخندق لـ<b>{feeder_count}</b> مغذيات = <b>{width:g} م</b>"]
    if route_length_m > 0:
        for line in trench_materials(route_length_m, feeder_count, catalog):
            lines.append(
                f"&nbsp;&nbsp;– {line.name}: <b>{line.qty:g}</b> {line.unit}"
                f" &nbsp;<span style='color:#666'>({line.source})</span>"
            )
    if is_wide_trench(width):
        lines.append(
            f"الخندق <b>عريض</b> (≥ 1 م): الشتايكر قطعتان متجاورتان، "
            "والشريط لفّتان."
        )
    lines.append("<i>هذه الثلاث كمية بلا كلفة — ضمن أجر الأعمال المدنية.</i>")
    return "<br>".join(lines)


def _civil_hint_text(sidewalk_type, count, route_length_m, catalog) -> str:
    """نصّ تلميح الأعمال المدنية — يعرض **المكوّنين** ومجموعهما لا الإجمالي وحده.

    المقصد أن يرى المستخدم من أين جاء الرقم: حفر الخندق كذا، وإعادة المسار كذا
    (ق-٣٨). ما دام العدد خارج الجدول يُعرض تحذير بدل رقم مخمَّن.
    """
    parts = civil_tariff_parts(sidewalk_type, count, catalog)
    if any(rate is None for _name, rate in parts):
        return (
            f"⚠️ لا تعرفة لـ «{sidewalk_type.value} × {count}» — "
            "عدد المغذيات خارج الجدول (1 إلى 5)."
        )
    rows = [
        f"&nbsp;&nbsp;– {name}: {route_length_m:,.0f} م × {rate:,.0f} د/م = "
        f"<b>{route_length_m * rate:,.0f} د</b>"
        for name, rate in parts
    ]
    total = sum(rate for _name, rate in parts)
    rows.append(
        f"&nbsp;&nbsp;<b>المجموع: {total:,.0f} د/م = "
        f"{route_length_m * total:,.0f} د</b>"
    )
    if len(parts) == 1:
        rows.insert(0, "⚠️ لم يصلنا تفصيل هذا العدد إلى «حفر» و«إعادة مسار» بعد:")
    return "<br>".join(rows)


class PanelUnderground11kV(QWidget):
    """مدخلات مقطع شبكة أرضية 11 ك.ف — قابلو 3×150 ملم² (ق-٣٠).

    التمييز الجوهري الذي تعرضه الحقول: **طول المسار** وحده يحدّد الأعمال المدنية
    وموادّ الخندق، و**طول المسار × عدد المغذيات** يحدّد كمية القابلو وأجر مدّه.
    """

    changed = pyqtSignal()

    def __init__(self, catalog: dict) -> None:
        super().__init__()
        self.catalog = catalog
        self._build()
        self._connect()
        self.refresh_hints()

    def _build(self) -> None:
        body, layout = scroll_body()

        box, form = section("المسار والمغذيات")
        self.route = number_field(0, 500_000, 0, suffix="م")
        self.feeders = number_field(1, 100, 1)
        self.waste_included = QCheckBox("الطول المُدخل يشمل نسبة الزيادة")
        self.waste_pct = number_field(0, 100, 10, decimals=1, step=0.5, suffix="%")
        form.addRow("طول المسار (طول الخندق):", self.route)
        form.addRow("عدد المغذيات في هذا الخندق:", self.feeders)
        form.addRow("", self.waste_included)
        form.addRow("نسبة الزيادة:", self.waste_pct)
        self.cable_hint = HintLabel()
        form.addRow(self.cable_hint)
        layout.addWidget(box)

        box, form = section("الأعمال المدنية — تعتمد على طول المسار وحده")
        self.sidewalk = _combo(list(SidewalkType))
        form.addRow("نوع الرصيف:", self.sidewalk)
        self.civil_hint = HintLabel()
        form.addRow(self.civil_hint)
        layout.addWidget(box)

        box, form = section("موادّ الخندق  —  كمية بلا كلفة")
        self.trench_hint = HintLabel()
        form.addRow(self.trench_hint)
        layout.addWidget(box)

        box, form = section("الصندوق المستقيم  —  استرشادي لكل مغذٍّ على حدة")
        self.drum_length = number_field(1, 5000, 250, suffix="م")
        form.addRow("طول بكرة القابلو:", self.drum_length)
        self.box_hint = HintLabel()
        form.addRow(self.box_hint)
        self.adopt = QPushButton("اعتماد القيم المقترحة  ↓")
        form.addRow(self.adopt)
        self.straight_boxes = number_field(0, 10_000, 0)
        form.addRow("عدد الصناديق المستقيمة:", self.straight_boxes)
        layout.addWidget(box)

        box, form = section("صناديق النهاية  —  إدخال يدوي بحت")
        self.end_internal = number_field(0, 10_000, 0)
        self.end_external = number_field(0, 10_000, 0)
        form.addRow("صندوق نهاية داخلي (لمحطة/محولة أرضية):", self.end_internal)
        form.addRow("صندوق نهاية خارجي (لشبكة هوائية):", self.end_external)
        layout.addWidget(box)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _connect(self) -> None:
        for w in (self.route, self.feeders, self.waste_pct, self.drum_length,
                  self.straight_boxes, self.end_internal, self.end_external):
            w.valueChanged.connect(self._on_change)
        self.sidewalk.currentIndexChanged.connect(self._on_change)
        self.waste_included.toggled.connect(self._on_change)
        self.adopt.clicked.connect(self._adopt_suggestion)

    def _on_change(self) -> None:
        self.refresh_hints()
        self.changed.emit()

    def _adopt_suggestion(self) -> None:
        self.straight_boxes.setValue(
            suggest_straight_boxes(
                self.route.value(), self.feeders.value(), self.drum_length.value()
            )
        )

    def content(self) -> Underground11kV:
        return Underground11kV(
            route_length_m=self.route.value(),
            feeder_count=self.feeders.value(),
            sidewalk_type=self.sidewalk.currentData(),
            length_includes_waste=self.waste_included.isChecked(),
            waste_pct=self.waste_pct.value() / 100.0,
            drum_length_m=self.drum_length.value(),
            straight_boxes=self.straight_boxes.value(),
            end_boxes_internal=self.end_internal.value(),
            end_boxes_external=self.end_external.value(),
        )

    def refresh_hints(self) -> None:
        net = self.content()
        self.waste_pct.setEnabled(not net.length_includes_waste)

        waste = 1.0 if net.length_includes_waste else 1.0 + net.waste_pct
        qty = cable_quantity(net)
        self.cable_hint.setText(
            f"قابلو 3×150: {net.route_length_m:,.0f} × {net.feeder_count} مغذٍّ"
            f" × {waste:g} زيادة = <b>{qty:,} م</b>"
        )

        self.civil_hint.setText(
            _civil_hint_text(
                net.sidewalk_type, net.feeder_count, net.route_length_m, self.catalog
            )
        )
        self.trench_hint.setText(
            _trench_hint_text(net.feeder_count, net.route_length_m, self.catalog)
        )

        suggested = suggest_straight_boxes(
            net.route_length_m, net.feeder_count, net.drum_length_m
        )
        self.box_hint.setText(
            f"لكل مغذٍّ: ⌈{net.route_length_m:,.0f} ÷ {net.drum_length_m:,.0f}⌉ − 1،"
            f" × {net.feeder_count} مغذٍّ = <b>{suggested} صندوق</b> مقترح"
        )


class PanelUnderground33kV(QWidget):
    """مدخلات مقطع شبكة أرضية 33 ك.ف — قابلو 1×400 ملم² (ق-٣١).

    الفرق عن 11 ك.ف: القابلو أحادي القلب — كل دائرة تحتاج ثلاثة كابلات منفصلة،
    فالمُدخل هنا **مفردة/مزدوجة** لا عدد مغذيات مباشر. وللأعمال المدنية وحدها،
    المغذي الواحد (بكابلاته الثلاثة) يُعامَل معاملة مغذٍّ واحد مماثل لـ11 ك.ف.
    """

    changed = pyqtSignal()

    def __init__(self, catalog: dict) -> None:
        super().__init__()
        self.catalog = catalog
        self._build()
        self._connect()
        self.refresh_hints()

    def _build(self) -> None:
        body, layout = scroll_body()

        box, form = section("المسار والدائرة")
        self.route = number_field(0, 500_000, 0, suffix="م")
        self.circuit = _combo([CircuitType.SINGLE, CircuitType.DOUBLE])
        self.waste_included = QCheckBox("الطول المُدخل يشمل نسبة الزيادة")
        self.waste_pct = number_field(0, 100, 10, decimals=1, step=0.5, suffix="%")
        form.addRow("طول المسار (طول الخندق):", self.route)
        form.addRow("نوع الدائرة:", self.circuit)
        form.addRow("", self.waste_included)
        form.addRow("نسبة الزيادة:", self.waste_pct)
        self.cable_hint = HintLabel()
        form.addRow(self.cable_hint)
        layout.addWidget(box)

        box, form = section("الأعمال المدنية — تعتمد على طول المسار وحده")
        self.sidewalk = _combo(list(SidewalkType))
        form.addRow("نوع الرصيف:", self.sidewalk)
        self.civil_hint = HintLabel()
        form.addRow(self.civil_hint)
        layout.addWidget(box)

        box, form = section("موادّ الخندق  —  كمية بلا كلفة")
        self.trench_hint = HintLabel()
        form.addRow(self.trench_hint)
        layout.addWidget(box)

        box, form = section("الصندوق المستقيم  —  استرشادي لكل كابل (طور) على حدة")
        self.drum_length = number_field(1, 5000, 500, suffix="م")
        form.addRow("طول بكرة القابلو:", self.drum_length)
        self.box_hint = HintLabel()
        form.addRow(self.box_hint)
        self.adopt = QPushButton("اعتماد القيم المقترحة  ↓")
        form.addRow(self.adopt)
        self.straight_boxes = number_field(0, 10_000, 0)
        form.addRow("عدد الصناديق المستقيمة:", self.straight_boxes)
        layout.addWidget(box)

        box, form = section("صناديق النهاية  —  إدخال يدوي، والسيت 3 صناديق")
        self.end_internal = number_field(0, 10_000, 0)
        self.end_external = number_field(0, 10_000, 0)
        form.addRow("نهايات داخلية (سيت — لمحطة/محولة أرضية):", self.end_internal)
        form.addRow("نهايات خارجية (سيت — لشبكة هوائية):", self.end_external)
        self.end_box_hint = HintLabel()
        form.addRow(self.end_box_hint)
        layout.addWidget(box)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _connect(self) -> None:
        for w in (self.route, self.waste_pct, self.drum_length,
                  self.straight_boxes, self.end_internal, self.end_external):
            w.valueChanged.connect(self._on_change)
        for w in (self.circuit, self.sidewalk):
            w.currentIndexChanged.connect(self._on_change)
        self.waste_included.toggled.connect(self._on_change)
        self.adopt.clicked.connect(self._adopt_suggestion)

    def _on_change(self) -> None:
        self.refresh_hints()
        self.changed.emit()

    def _adopt_suggestion(self) -> None:
        net = self.content()
        self.straight_boxes.setValue(
            suggest_straight_boxes(
                net.route_length_m, cable_count_33(net), self.drum_length.value()
            )
        )

    def content(self) -> Underground33kV:
        return Underground33kV(
            route_length_m=self.route.value(),
            circuit=self.circuit.currentData(),
            sidewalk_type=self.sidewalk.currentData(),
            length_includes_waste=self.waste_included.isChecked(),
            waste_pct=self.waste_pct.value() / 100.0,
            drum_length_m=self.drum_length.value(),
            straight_boxes=self.straight_boxes.value(),
            end_boxes_internal=self.end_internal.value(),
            end_boxes_external=self.end_external.value(),
        )

    def refresh_hints(self) -> None:
        net = self.content()
        self.waste_pct.setEnabled(not net.length_includes_waste)

        waste = 1.0 if net.length_includes_waste else 1.0 + net.waste_pct
        cables = cable_count_33(net)
        qty = cable_quantity_33(net)
        self.cable_hint.setText(
            f"قابلو 1×400: {net.route_length_m:,.0f} × {cables} كابل"
            f" ({net.circuit.value}) × {waste:g} زيادة = <b>{qty:,} م</b>"
            "<br>أحادي القلب — كل دائرة 3 كابلات منفصلة، طور لكل كابل."
        )

        self.trench_hint.setText(
            _trench_hint_text(net.circuit.circuits, net.route_length_m, self.catalog)
        )
        self.civil_hint.setText(
            "المغذي الواحد يُعامَل معاملة مغذٍّ واحد مماثل لـ11 ك.ف:<br>"
            + _civil_hint_text(
                net.sidewalk_type,
                net.circuit.circuits,
                net.route_length_m,
                self.catalog,
            )
        )

        suggested = suggest_straight_boxes(net.route_length_m, cables, net.drum_length_m)
        self.box_hint.setText(
            f"لكل كابل (طور): ⌈{net.route_length_m:,.0f} ÷ {net.drum_length_m:,.0f}⌉ − 1،"
            f" × {cables} كابل = <b>{suggested} صندوق</b> مقترح"
        )

        internal = net.end_boxes_internal * BOXES_PER_END_SET_33
        external = net.end_boxes_external * BOXES_PER_END_SET_33
        self.end_box_hint.setText(
            f"السيت الواحد <b>{BOXES_PER_END_SET_33} صناديق</b> — صندوق لكل طور."
            f"<br>داخلية: {net.end_boxes_internal} سيت ← <b>{internal} صندوق</b>"
            f" &nbsp;|&nbsp; خارجية: {net.end_boxes_external} سيت ← <b>{external} صندوق</b>"
        )
