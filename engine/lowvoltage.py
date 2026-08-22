# -*- coding: utf-8 -*-
"""محرك حساب شبكة الضغط الواطئ.

نوعان: **أسلاك ألمنيوم 95 ملم²** و**قابلو ألمنيوم معلق مبروم**. يختلفان في كمية
الموصل وفي ملحقات كل عمود اختلافاً تاماً.

الضغط الواطئ لا يستخدم عوازل — بل كلامبات: **بوكس كلامب** للأسلاك، و**هوك تعليق**
مع **كلامب شد** (للمشبك) أو **كلامب تعليق** (للمدوّر) للقابلو المعلق. والتمييز يتبع
نفس منطق الجهدين الأعلى: المشبك للشد والمدوّر للتعليق.

المرجع: ق-٢٢ في docs/سجل_القرارات.md
"""

from __future__ import annotations

from .overhead import (
    EARTH_TERMINAL_PER_POLE,
    EARTH_WIRE_PER_POLE,
    M_AL_FITTINGS_11,
    M_CONCRETE,
    M_EARTH_TERMINAL,
    M_EARTH_WIRE,
    _roundup,
    count_poles_spanned,
)
from .types import LabourLine, LVNetworkType, MaterialLine, NetworkLV, PoleCount11

# ─────────────────────────────── ثوابت المواصفة ───────────────────────────────

CONCRETE_9_LATTICE = 0.63
CONCRETE_9_ROUND = 0.45

CONNECTORS_PER_CABLE_DRUM_END = 5
"""كونكتر قابلو معلق لكل عمود مشبك — يمثّل نهاية بكرة القابلو."""

CONSUMER_CONNECTORS_EACH = 1
"""كونكتر ربط مشتركين لكل مستهلك (ق-٢٢)."""

# أسماء المواد — تطابق الملف الأصلي حرفياً
M_WIRE_LV = ("سلك ألمنيوم 95 ملم²", "متر")
M_BUNDLED_CABLE = ("قابلو ألمنيوم معلق 3×120+95+16 ملم²", "متر")
M_POLE_9_LATTICE = ("عمود 9م مشبك", "عدد")
M_POLE_9_ROUND = ("عمود 9م مدوّر", "عدد")
M_BOX_CLAMP = ("بوكس كلامب (أسلاك)", "عدد")
M_SUSPENSION_HOOK = ("هوك تعليق (قابلو)", "عدد")
M_TENSION_CLAMP = ("كلامب شد (قابلو)", "عدد")
M_SUSPENSION_CLAMP = ("كلامب تعليق (قابلو)", "عدد")
M_CABLE_CONNECTOR = ("كونكتر قابلو معلق (ألمنيوم – ألمنيوم)", "عدد")
M_CONSUMER_CONNECTOR = ("كونكتر ربط مشتركين", "عدد")

# ملحقات كل عمود حسب نوع الشبكة ونوع العمود.
# القيم مطابقة للملف الأصلي، وهي نفسها سواء كان العمود 9م أو عمود ضغط عالٍ 11م
# تمرّ عليه الشبكة الواطئة — وهو ما يجعل الحالتين تتقاسمان دالة واحدة.
ACCESSORIES = {
    LVNetworkType.BARE_WIRES: {
        "lattice": [(M_BOX_CLAMP, 8), (M_AL_FITTINGS_11, 8)],
        "round": [(M_BOX_CLAMP, 4)],
    },
    LVNetworkType.BUNDLED_CABLE: {
        "lattice": [(M_SUSPENSION_HOOK, 2), (M_TENSION_CLAMP, 2)],
        "round": [(M_SUSPENSION_HOOK, 1), (M_SUSPENSION_CLAMP, 1)],
    },
}


def count_poles_lv(route_length_m: float, span: float, tension_span: float) -> PoleCount11:
    """يقترح أعمدة الضغط الواطئ — نفس خوارزمية 11 ك.ف بمسافات مختلفة.

    عمود كل `span` متراً (افتراضي 20)، وعمود شد مشبك كل `tension_span` متراً
    (افتراضي 100)، وطرفا الخط مشبكان إلزاماً.
    """
    return count_poles_spanned(route_length_m, span, tension_span)


def conductor_quantity(net: NetworkLV) -> int:
    """كمية الموصل: الأسلاك × 4 أطوار، والقابلو المعلق × 1.

    الطور الرابع في الأسلاك هو المحايد (ثلاثة حارة وواحد بارد). والقابلو المعلق
    كابل واحد يضمّ الموصلات كلها فلا يُضرب.
    """
    if net.route_length_m <= 0:
        return 0
    waste = 1.0 if net.length_includes_waste else 1.0 + net.waste_pct
    return _roundup(net.route_length_m * net.kind.conductors * waste)


def _accessory_lines(
    kind: LVNetworkType, lattice: int, round_: int, label: str
) -> list[MaterialLine]:
    """أسطر ملحقات مجموعة أعمدة — سطر مستقل لكل مصدر ليبقى التتبّع ممكناً."""
    lines: list[MaterialLine] = []
    for pole_key, count, pole_label in (
        ("lattice", lattice, "مشبك"),
        ("round", round_, "مدوّر"),
    ):
        if not count:
            continue
        for material, per_pole in ACCESSORIES[kind][pole_key]:
            lines.append(
                MaterialLine(
                    *material,
                    count * per_pole,
                    f"{label} {pole_label} ({kind.value}): {count} × {per_pole}",
                )
            )
    return lines


def materials_lv(net: NetworkLV) -> list[MaterialLine]:
    """يولّد أسطر مواد شبكة الضغط الواطئ."""
    lines: list[MaterialLine] = []
    add = lines.append
    lat, rnd = net.poles_lattice, net.poles_round
    poles = lat + rnd

    # الموصل
    qty = conductor_quantity(net)
    if qty:
        waste = 1.0 if net.length_includes_waste else 1.0 + net.waste_pct
        material = M_WIRE_LV if net.kind is LVNetworkType.BARE_WIRES else M_BUNDLED_CABLE
        add(
            MaterialLine(
                *material,
                qty,
                f"مسار ض.و ({net.kind.value}): {net.route_length_m:,.0f}"
                f" × {net.kind.conductors} × {waste:g} زيادة",
            )
        )

    # الأعمدة
    if lat:
        add(MaterialLine(*M_POLE_9_LATTICE, lat, f"أعمدة ض.و: {lat} مشبك"))
    if rnd:
        add(MaterialLine(*M_POLE_9_ROUND, rnd, f"أعمدة ض.و: {rnd} مدوّر"))

    # ملحقات أعمدة 9م
    lines.extend(_accessory_lines(net.kind, lat, rnd, "أعمدة ض.و 9م"))

    # كونكتر القابلو المعلق — للأعمدة المشبكة فقط، لأنه يمثّل نهاية بكرة القابلو
    if net.kind is LVNetworkType.BUNDLED_CABLE and lat:
        add(
            MaterialLine(
                *M_CABLE_CONNECTOR,
                lat * CONNECTORS_PER_CABLE_DRUM_END,
                f"نهايات بكرة القابلو — أعمدة ض.و مشبك: {lat}"
                f" × {CONNECTORS_PER_CABLE_DRUM_END}",
            )
        )

    # التأريض والكونكريت — لا يتغيّران بنوع الشبكة
    if poles:
        add(
            MaterialLine(
                *M_EARTH_WIRE,
                poles * EARTH_WIRE_PER_POLE,
                f"تأريض أعمدة ض.و: {poles} عموداً × {EARTH_WIRE_PER_POLE}",
            )
        )
        add(
            MaterialLine(
                *M_EARTH_TERMINAL,
                poles * EARTH_TERMINAL_PER_POLE,
                f"تأريض أعمدة ض.و: {poles} عموداً × {EARTH_TERMINAL_PER_POLE}",
            )
        )
        concrete = lat * CONCRETE_9_LATTICE + rnd * CONCRETE_9_ROUND
        add(
            MaterialLine(
                *M_CONCRETE,
                _roundup(concrete),
                f"أساسات أعمدة ض.و: {lat} × {CONCRETE_9_LATTICE:g}"
                f" + {rnd} × {CONCRETE_9_ROUND:g} = {concrete:,.3f} ← مقرَّب لأعلى",
            )
        )

    # الشبكة المارّة على أعمدة الضغط العالي: كلامبات فقط.
    # لا أعمدة ولا تأريض ولا كونكريت — الأعمدة قائمة أصلاً أو محسوبة في قسم الضغط العالي.
    if net.on_hv_poles:
        lines.extend(
            _accessory_lines(
                net.hv_kind, net.hv_poles_lattice, net.hv_poles_round,
                "ش.ض.و على أعمدة ض.ع",
            )
        )

    # كونكتر ربط المشتركين — واحد لكل مستهلك
    if net.consumers:
        add(
            MaterialLine(
                *M_CONSUMER_CONNECTOR,
                net.consumers * CONSUMER_CONNECTORS_EACH,
                f"ربط المستهلكين: {net.consumers} × {CONSUMER_CONNECTORS_EACH}",
            )
        )

    return lines


def labour_lv(net: NetworkLV, rates: dict) -> list[LabourLine]:
    """أجور الضغط الواطئ."""
    out: list[LabourLine] = []
    qty = conductor_quantity(net)
    if qty:
        label = (
            "تسليك شبكة الضغط الواطئ (أسلاك)"
            if net.kind is LVNetworkType.BARE_WIRES
            else "تسليك شبكة الضغط الواطئ (قابلو معلق مبروم)"
        )
        entry = rates[label]
        out.append(LabourLine(label, entry["الوحدة"], qty, entry["السعر"]))

    for label, count in (
        ("نصب عمود مشبك 9م", net.poles_lattice),
        ("نصب عمود مدور 9م", net.poles_round),
        ("ربط المستهلكين", net.consumers),
    ):
        if count:
            entry = rates[label]
            out.append(LabourLine(label, entry["الوحدة"], count, entry["السعر"]))
    return out
