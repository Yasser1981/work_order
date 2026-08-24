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

    equipment: "Equipment" = field(default_factory=lambda: Equipment())
    """التجهيزات على الأعمدة: المحولة والفواصل والقفيص (ق-٢٣)."""


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


@dataclass
class Equipment:
    """التجهيزات المنصوبة على الأعمدة — لا تتبع طول المسار بل تُدخَل عدداً.

    كل تجهيز يجرّ خلفه مجموعة ملحقات ثابتة (المحولة 15 مادة، الفاصل ON-LOAD على
    رأس القابلو 9 مواد …)، وأجر عمله يشمل ملحقاته كلها فلا أجر مستقل لها (ق-٢٣).
    """

    transformers: dict = field(default_factory=dict)
    """عدد المحولات بكل سعة: {TransformerSize: العدد} — 250 و400 و630 (ق-٢٦)."""

    onload_11_mid: int = 0
    """فاصل ON-LOAD جهد 11 ك.ف في منتصف الشبكة — بلا مانعة صواعق (ق-٢٥)."""

    onload_11_head: int = 0
    """فاصل ON-LOAD جهد 11 ك.ف على رأس القابلو — مع مانعة، ونصف كمية القابلو."""

    isolator_33_mid: int = 0
    """فاصل هوائي 33 ك.ف في منتصف الشبكة — بلا مانعة صواعق."""

    isolator_33_head: int = 0
    """فاصل هوائي 33 ك.ف على رأس القابلو — مع مانعة، ونصف كمية القابلو."""

    lattice_cages: int = 0
    """قفيص عمود مشبك — كمية يدخلها المستخدم مباشرة، بلا ملحقات وبلا أجر."""

    def __bool__(self) -> bool:
        return any(
            (
                any(self.transformers.values()),
                self.onload_11_mid,
                self.onload_11_head,
                self.isolator_33_mid,
                self.isolator_33_head,
                self.lattice_cages,
            )
        )


class SegmentKind(Enum):
    """نوع المقطع — يُشتقّ من نوع محتواه فلا يمكن أن يتعارض معه."""

    HV11 = "شبكة هوائية 11 ك.ف"
    HV33 = "شبكة هوائية 33 ك.ف"
    LV = "شبكة ضغط واطئ"
    EQUIPMENT = "تجهيزات"
    UG11 = "شبكة أرضية 11 ك.ف"
    UG33 = "شبكة أرضية 33 ك.ف"


SegmentContent = "Network11kV | Network33kV | NetworkLV | Equipment"


@dataclass
class Segment:
    """مقطع واحد من المشروع.

    المشروع الواقعي نادراً ما يكون شبكة واحدة متجانسة: مقطع مزدوج، ومقطع مفرد،
    ومقطع ضغط واطئ بالقابلو المعلق، وآخر بالأسلاك. المقاطع تجعل ذلك قابلاً
    للإدخال بدل إجبار المستخدم على جمع الأطوال ذهنياً (ق-٢٤).
    """

    name: str
    content: object
    """Network11kV أو Network33kV أو NetworkLV أو Equipment."""

    @property
    def kind(self) -> SegmentKind:
        if isinstance(self.content, Network11kV):
            return SegmentKind.HV11
        if isinstance(self.content, Network33kV):
            return SegmentKind.HV33
        if isinstance(self.content, NetworkLV):
            return SegmentKind.LV
        if isinstance(self.content, Equipment):
            return SegmentKind.EQUIPMENT
        if isinstance(self.content, Underground11kV):
            return SegmentKind.UG11
        if isinstance(self.content, Underground33kV):
            return SegmentKind.UG33
        raise TypeError(f"محتوى مقطع غير معروف: {type(self.content).__name__}")


@dataclass
class Project:
    """مشروع = قائمة مقاطع. الكميات تُجمَّع من المقاطع كلها بمفتاح (المادة + الوحدة)."""

    name: str = ""
    segments: list = field(default_factory=list)

    street_crossing_secondary_m: float = 0.0
    """عبور الشوارع الفرعية — إجمالي للمشروع كله، لا لكل مقطع (بطلب المستخدم)."""

    street_crossing_main_m: float = 0.0
    """عبور الشوارع الرئيسية (حفر مخفي) — إجمالي للمشروع كله."""

    def of_kind(self, kind: SegmentKind) -> list:
        return [s for s in self.segments if s.kind is kind]


ORDINALS = [
    "الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس", "السابع",
    "الثامن", "التاسع", "العاشر", "الحادي عشر", "الثاني عشر", "الثالث عشر",
    "الرابع عشر", "الخامس عشر", "السادس عشر", "السابع عشر", "الثامن عشر",
    "التاسع عشر", "العشرون",
]


def segment_default_name(index: int) -> str:
    """اسم افتراضي للمقطع رقم `index` (يبدأ من صفر) — «المقطع الأول» وهكذا."""
    if index < len(ORDINALS):
        return f"المقطع {ORDINALS[index]}"
    return f"المقطع {index + 1}"


class SidewalkType(Enum):
    """نوع الرصيف الذي يمرّ فيه خندق القابلو الأرضي — يحدّد تعرفة الأعمال المدنية."""

    EARTH = "ترابي"
    PAVED = "مبلط"
    TERRAZZO = "مقرنص"


@dataclass
class Underground11kV:
    """مدخلات مقطع شبكة أرضية 11 ك.ف — قابلو 3×150 ملم² (ق-٣٠).

    التمييز الجوهري: **طول المسار** وحده يحدّد الأعمال المدنية وموادّ الخندق
    (الحفر خندق واحد بصرف النظر عن عدد المغذيات المارّة فيه)، بينما **طول المسار ×
    عدد المغذيات** يحدّد كمية القابلو نفسه وأجر مدّه (كل مغذٍّ يحتاج طوله الكامل).
    """

    route_length_m: float = 0.0
    """طول الخندق الجغرافي — يحدّد الأعمال المدنية وموادّ الخندق وحده."""

    feeder_count: int = 1
    """عدد المغذيات (القابلوات) المارّة في هذا الخندق — يضاعف كمية القابلو،
    ويحدّد تعرفة الأعمال المدنية (خندق أعرض كلما زاد العدد)."""

    sidewalk_type: SidewalkType = SidewalkType.EARTH

    length_includes_waste: bool = False
    waste_pct: float = 0.10

    drum_length_m: float | None = None
    """طول بكرة القابلو القياسي (م). None ← من الافتراضيات (ق-٢٠)."""

    straight_boxes: int = 0
    """صندوق مستقيم — استرشادي قابل للاعتماد: لكل مغذٍّ صناديقه الخاصة به."""

    end_boxes_internal: int = 0
    """صندوق نهاية داخلي — يدوي بحت، يربط نهاية القابلو بمحطة أو محولة أرضية."""

    end_boxes_external: int = 0
    """صندوق نهاية خارجي — يدوي بحت، يربط نهاية القابلو بشبكة هوائية."""


@dataclass
class Underground33kV:
    """مدخلات مقطع شبكة أرضية 33 ك.ف — قابلو 1×400 ملم² (ق-٣١).

    الفرق الجوهري عن 11 ك.ف: القابلو هنا **أحادي القلب** — كل مغذٍّ (دائرة) يحتاج
    **ثلاثة كابلات منفصلة**، طور مستقل لكل كابل، لا كابلاً واحداً ثلاثي القلب.
    فمُدخل «عدد المغذيات» في 11 ك.ف استُبدل هنا بـ`circuit` (مفردة/مزدوجة) —
    نفس تصنيف الشبكة الهوائية بالضبط — ويُشتقّ منه عدد الكابلات الفعلي (×3 أطوار).

    **للأعمال المدنية وحدها:** المغذي الواحد (بكابلاته الثلاثة معاً في خندق واحد)
    يُعامَل معاملة مغذٍّ واحد مماثل لـ11 ك.ف — أي أن عدد «الوحدات» الذي يُبحث به في
    تعرفة الرصيف هو عدد **الدوائر** (1 أو 2)، لا عدد الكابلات (3 أو 6). بتأكيد
    المستخدم صراحةً.
    """

    route_length_m: float = 0.0
    """طول الخندق الجغرافي — يحدّد الأعمال المدنية وموادّ الخندق وحده."""

    circuit: CircuitType = CircuitType.SINGLE
    """مفردة = 3 كابلات (مغذٍّ واحد)، مزدوجة = 6 كابلات (مغذّيان)."""

    sidewalk_type: SidewalkType = SidewalkType.EARTH

    length_includes_waste: bool = False
    waste_pct: float = 0.10

    drum_length_m: float | None = None
    """طول بكرة القابلو القياسي (م). None ← من الافتراضيات، عادة 500 م (ق-٢٠)."""

    straight_boxes: int = 0
    """صندوق مستقيم — استرشادي بالكامل، غير مُلزِم: لكل كابل (طور) صناديقه."""

    end_boxes_internal: int = 0
    """صندوق نهاية داخلي — يدوي بحت، لكل طور صندوقه الخاص عادة."""

    end_boxes_external: int = 0
    """صندوق نهاية خارجي — يدوي بحت."""
