# -*- coding: utf-8 -*-
"""أنواع البيانات الأساسية لمحرك حساب الشبكة الهوائية.

المرجع: docs/مواصفة_الشبكة_الهوائية.md
"""

from dataclasses import dataclass, field
from enum import Enum


class CircuitType(Enum):
    """نوع الدائرة."""

    SINGLE = "مفردة"
    DOUBLE = "مزدوجة"

    @property
    def circuits(self) -> int:
        """عدد الدوائر — يُضرب به عدد الأطوار لحساب كمية السلك."""
        return 1 if self is CircuitType.SINGLE else 2


class SupplyForm(Enum):
    """شكل توريد العمود من المخزن (ق-٥، ق-١٣)."""

    WITH_ACCESSORIES = "مع الملحقات"
    WITHOUT_ACCESSORIES = "بدون ملحقات"

    @property
    def includes_bracket(self) -> bool:
        return self is SupplyForm.WITH_ACCESSORIES


class BracketPattern(Enum):
    """نمط البراكيت في الشبكة المزدوجة لجهد 11 ك.ف.

    القياسي: 1.2م في الأعلى والأسفل و1.4م في الوسط (شكل المثلث أو المعين).
    البديل:  المدور 3× 1.2م — المشبك 6× 1.4م.
    """

    STANDARD = "قياسي"
    ALTERNATIVE = "بديل"


class PoleType11(Enum):
    """نوع عمود 11 م. المدور للتعليق والمشبك للشد."""

    LATTICE = "مشبك"
    ROUND = "مدوّر"


@dataclass(frozen=True)
class MaterialLine:
    """سطر مادة مولّد من المحرك — يقابل سطراً في RAW_تفصيلي في الملف الأصلي."""

    name: str
    unit: str
    qty: float
    source: str = ""
    """مصدر التوليد — للتتبّع وشرح الرقم للمستخدم."""


@dataclass(frozen=True)
class LabourLine:
    """سطر أجر عمل."""

    name: str
    unit: str
    qty: float
    rate: float | None
    """None تعني أن الأجر غير محدَّد بعد — يُبلَّغ عنه ولا يُحتسب صفراً بصمت."""

    source: str = ""

    @property
    def rate_missing(self) -> bool:
        return self.rate is None

    @property
    def cost(self) -> float:
        return 0.0 if self.rate is None else self.qty * self.rate


@dataclass
class PoleCount11:
    """نتيجة حساب أعمدة 11 ك.ف الاسترشادي."""

    total: int
    lattice: int
    round_: int
    end_converted: bool
    """هل حُوِّل العمود الأخير من مدور إلى مشبك ليكون طرف الخط مشبكاً؟"""


@dataclass
class PoleCount33:
    """نتيجة حساب أعمدة 33 ك.ف الاسترشادي."""

    positions: int
    suspension: int
    mid_anchors: int
    end_anchors: int

    @property
    def anchors_total(self) -> int:
        return self.mid_anchors + self.end_anchors

    @property
    def poles_total(self) -> int:
        """كل ركيزة عمودان مشبكان 14م."""
        return self.suspension + self.anchors_total * 2


@dataclass
class Network11kV:
    """مدخلات شبكة 11 ك.ف الهوائية."""

    route_length_m: float = 0.0
    circuit: CircuitType = CircuitType.SINGLE
    length_includes_waste: bool = False
    waste_pct: float = 0.10

    span_m: float | None = None
    """المسافة العامة بين الأعمدة (م). None ← تُقرأ من الافتراضيات في ملف البيانات (ق-٢٠)."""

    tension_span_m: float | None = None
    """المسافة بين أعمدة الشد المشبكة (م). None ← تُقرأ من الافتراضيات (ق-٢٠)."""

    poles_lattice: int = 0
    poles_round: int = 0

    lattice_supply: SupplyForm = SupplyForm.WITHOUT_ACCESSORIES
    round_supply: SupplyForm = SupplyForm.WITHOUT_ACCESSORIES
    bracket_pattern: BracketPattern = BracketPattern.STANDARD

    extra_bracket_12: int = 0
    extra_bracket_14: int = 0

    stay_rod_sets: int = 0
    """عدد أطقم ستي رود على أعمدة 11م — واير ستي 12 م لكل طقم (ق-١٨)."""


@dataclass
class Network33kV:
    """مدخلات شبكة 33 ك.ف الهوائية."""

    route_length_m: float = 0.0
    circuit: CircuitType = CircuitType.SINGLE
    length_includes_waste: bool = False
    waste_pct: float = 0.10

    span_m: float | None = None
    """المسافة بين أعمدة التعليق 14م (م). None ← تُقرأ من الافتراضيات (ق-٢٠)."""

    tension_span_m: float | None = None
    """المسافة بين الركائز الوسطية (م). None ← تُقرأ من الافتراضيات (ق-٢٠)."""

    poles_suspension: int = 0
    anchors_mid: int = 0
    anchors_end: int = 0

    pole_supply: SupplyForm = SupplyForm.WITHOUT_ACCESSORIES
    """خيار واحد لكل أعمدة «مشبك 14م» — تعليق وركائز معاً (ق-١٣)."""

    extra_bracket_2: int = 0
    extra_bracket_25: int = 0

    stay_rod_sets: int = 0
    """عدد أطقم ستي رود على أعمدة 14م — واير ستي 15 م لكل طقم (ق-١٨)."""


@dataclass
class OverheadProject:
    """مشروع — قد يضمّ الجهود الثلاثة معاً."""

    name: str = ""
    net11: Network11kV = field(default_factory=Network11kV)
    net33: Network33kV = field(default_factory=Network33kV)
    netlv: "NetworkLV | None" = None
    """شبكة الضغط الواطئ — None حين لا يتضمّنها المشروع."""


class LVNetworkType(Enum):
    """نوع شبكة الضغط الواطئ."""

    BARE_WIRES = "أسلاك"
    BUNDLED_CABLE = "قابلو معلق مبروم"

    @property
    def conductors(self) -> int:
        """عدد الموصلات التي يُضرب بها المسار.

        الأسلاك 4 (ثلاثة حارة وواحد بارد)، والقابلو المعلق 1 لأنه كابل واحد يضمّ
        الموصلات كلها.
        """
        return 4 if self is LVNetworkType.BARE_WIRES else 1


@dataclass
class NetworkLV:
    """مدخلات شبكة الضغط الواطئ."""

    route_length_m: float = 0.0
    kind: LVNetworkType = LVNetworkType.BARE_WIRES
    length_includes_waste: bool = False
    waste_pct: float = 0.10

    span_m: float | None = None
    """المسافة العامة بين أعمدة 9م (م). None ← من الافتراضيات (20 م)."""

    tension_span_m: float | None = None
    """المسافة بين أعمدة الشد المشبكة (م). None ← من الافتراضيات (100 م)."""

    poles_lattice: int = 0
    """عدد أعمدة 9م مشبك."""

    poles_round: int = 0
    """عدد أعمدة 9م مدوّر."""

    consumers: int = 0
    """عدد المستهلكين — كونكتر ربط مشتركين واحد لكل مستهلك (ق-٢٢)."""

    # ── حالة مرور الشبكة على أعمدة الضغط العالي القائمة ──
    on_hv_poles: bool = False
    """أحياناً لا حاجة لنصب أعمدة: تُستغلّ أعمدة الضغط العالي القائمة أو الجديدة."""

    hv_kind: LVNetworkType = LVNetworkType.BUNDLED_CABLE
    """نوع الشبكة المارّة على أعمدة الضغط العالي — قد يختلف عن نوع الشبكة الأساسي."""

    hv_poles_lattice: int = 0
    hv_poles_round: int = 0
