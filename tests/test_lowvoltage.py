# -*- coding: utf-8 -*-
"""اختبارات محرك الضغط الواطئ — ق-٢٢."""

import math

import pytest

from engine import load_catalog
from engine.lowvoltage import (
    conductor_quantity,
    count_poles_lv,
    labour_lv,
    materials_lv,
)
from engine.overhead import aggregate, compute
from engine.types import (
    LVNetworkType,
    Network11kV,
    NetworkLV,
    OverheadProject,
)

WIRES, CABLE = LVNetworkType.BARE_WIRES, LVNetworkType.BUNDLED_CABLE


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def qty_of(lines, name):
    for (n, _u), q in aggregate(lines).items():
        if n == name:
            return q
    return 0


# ═══════════════════════ ١. كمية الموصل ═══════════════════════


def test_bare_wires_multiply_by_four_conductors():
    """ثلاثة أطوار حارة وواحد بارد."""
    assert conductor_quantity(NetworkLV(route_length_m=1000, kind=WIRES)) == 4400


def test_bundled_cable_is_not_multiplied():
    """القابلو المعلق كابل واحد يضمّ الموصلات — لا يُضرب."""
    assert conductor_quantity(NetworkLV(route_length_m=1000, kind=CABLE)) == 1100


def test_waste_already_included_skips_the_uplift():
    net = NetworkLV(route_length_m=1000, kind=WIRES, length_includes_waste=True)
    assert conductor_quantity(net) == 4000


def test_conductor_quantity_rounds_up():
    net = NetworkLV(route_length_m=333, kind=WIRES)
    assert conductor_quantity(net) == math.ceil(333 * 4 * 1.1)


def test_each_kind_produces_its_own_material():
    wires = materials_lv(NetworkLV(route_length_m=500, kind=WIRES))
    cable = materials_lv(NetworkLV(route_length_m=500, kind=CABLE))
    assert qty_of(wires, "سلك ألمنيوم 95 ملم²") > 0
    assert qty_of(wires, "قابلو ألمنيوم معلق 3×120+95+16 ملم²") == 0
    assert qty_of(cable, "قابلو ألمنيوم معلق 3×120+95+16 ملم²") > 0
    assert qty_of(cable, "سلك ألمنيوم 95 ملم²") == 0


# ═══════════════════════ ٢. حساب الأعمدة ═══════════════════════


def test_pole_count_uses_lv_spans():
    """20 م بين الأعمدة، وعمود شد كل 100 م."""
    result = count_poles_lv(1000, span=20, tension_span=100)
    assert result.total == 51                       # ceil(1000/20) + 1
    assert result.lattice == 11                     # كل خامس عمود = 100 م
    assert result.round_ == 40


def test_ends_are_always_lattice():
    for length in (137, 340, 500, 1000):
        r = count_poles_lv(length, 20, 100)
        assert r.lattice >= 2
        assert r.lattice + r.round_ == r.total


def test_spans_are_user_editable(catalog):
    """المسافات استرشادية قابلة للتعديل كما في الجهدين الأعلى (ق-٢٠)."""
    default = count_poles_lv(1000, 20, 100)
    wider = count_poles_lv(1000, 25, 150)
    assert wider.total < default.total
    assert (wider.lattice, wider.round_) != (default.lattice, default.round_)


# ═══════════════════════ ٣. ملحقات الأعمدة ═══════════════════════


def test_bare_wire_accessories_match_the_original():
    """بوكس كلامب 8 لكل مشبك و4 لكل مدوّر — ومعدات الربط للمشبك وحده."""
    lines = materials_lv(NetworkLV(kind=WIRES, poles_lattice=10, poles_round=40))
    assert qty_of(lines, "بوكس كلامب (أسلاك)") == 10 * 8 + 40 * 4      # 240
    assert qty_of(lines, "معدات ربط ألمنيوم – ألمنيوم") == 10 * 8      # 80


def test_bundled_cable_accessories_match_the_original():
    """المشبك للشد (كلامب شد) والمدوّر للتعليق (كلامب تعليق)."""
    lines = materials_lv(NetworkLV(kind=CABLE, poles_lattice=10, poles_round=40))
    assert qty_of(lines, "هوك تعليق (قابلو)") == 10 * 2 + 40 * 1       # 60
    assert qty_of(lines, "كلامب شد (قابلو)") == 10 * 2                 # 20
    assert qty_of(lines, "كلامب تعليق (قابلو)") == 40 * 1              # 40


def test_accessories_never_cross_between_kinds():
    """شبكة الأسلاك لا تُنتج كلامبات القابلو، والعكس."""
    wires = materials_lv(NetworkLV(kind=WIRES, poles_lattice=10, poles_round=40))
    cable = materials_lv(NetworkLV(kind=CABLE, poles_lattice=10, poles_round=40))
    for name in ("هوك تعليق (قابلو)", "كلامب شد (قابلو)", "كلامب تعليق (قابلو)"):
        assert qty_of(wires, name) == 0
    assert qty_of(cable, "بوكس كلامب (أسلاك)") == 0


def test_cable_connector_is_for_lattice_poles_only():
    """كونكتر القابلو يمثّل نهاية بكرة — للأعمدة المشبكة وحدها."""
    lines = materials_lv(NetworkLV(kind=CABLE, poles_lattice=10, poles_round=40))
    assert qty_of(lines, "كونكتر قابلو معلق (ألمنيوم – ألمنيوم)") == 10 * 5

    only_round = materials_lv(NetworkLV(kind=CABLE, poles_round=40))
    assert qty_of(only_round, "كونكتر قابلو معلق (ألمنيوم – ألمنيوم)") == 0


def test_no_cable_connector_for_bare_wire_network():
    lines = materials_lv(NetworkLV(kind=WIRES, poles_lattice=10))
    assert qty_of(lines, "كونكتر قابلو معلق (ألمنيوم – ألمنيوم)") == 0


def test_lv_uses_no_insulators():
    """الضغط الواطئ يستخدم كلامبات لا عوازل."""
    for kind in (WIRES, CABLE):
        lines = materials_lv(NetworkLV(kind=kind, poles_lattice=10, poles_round=40))
        for name in ("عازل دبوسي مع السبندل", "عازل قرصي مع الملحقات"):
            assert qty_of(lines, name) == 0


# ═══════════════════════ ٤. التأريض والكونكريت ═══════════════════════


def test_earthing_and_concrete_do_not_depend_on_kind():
    a = materials_lv(NetworkLV(kind=WIRES, poles_lattice=10, poles_round=40))
    b = materials_lv(NetworkLV(kind=CABLE, poles_lattice=10, poles_round=40))
    for name in ("سلك نحاس 50 ملم2", "ترمنل 50 ملم²", "كونكريت أساسات الأعمدة"):
        assert qty_of(a, name) == qty_of(b, name)


def test_concrete_coefficients_match_the_original():
    """0.63 للمشبك و0.45 للمدوّر — كما في مدخلات!I23."""
    lines = materials_lv(NetworkLV(poles_lattice=10, poles_round=40))
    assert qty_of(lines, "كونكريت أساسات الأعمدة") == math.ceil(10 * 0.63 + 40 * 0.45)


def test_earthing_is_per_pole():
    lines = materials_lv(NetworkLV(poles_lattice=11, poles_round=40))
    assert qty_of(lines, "سلك نحاس 50 ملم2") == 51 * 1.5
    assert qty_of(lines, "ترمنل 50 ملم²") == 51


# ═══════════ ٥. الشبكة على أعمدة الضغط العالي ═══════════


def test_lv_on_hv_poles_adds_clamps_only():
    """الأعمدة قائمة أو محسوبة في قسم الضغط العالي — تُضاف الكلامبات وحدها."""
    net = NetworkLV(on_hv_poles=True, hv_kind=CABLE,
                    hv_poles_lattice=5, hv_poles_round=16)
    lines = materials_lv(net)
    assert qty_of(lines, "هوك تعليق (قابلو)") == 5 * 2 + 16 * 1
    assert qty_of(lines, "كلامب شد (قابلو)") == 5 * 2
    assert qty_of(lines, "كلامب تعليق (قابلو)") == 16
    # لا أعمدة ولا تأريض ولا كونكريت
    for name in ("عمود 9م مشبك", "عمود 9م مدوّر", "سلك نحاس 50 ملم2",
                 "ترمنل 50 ملم²", "كونكريت أساسات الأعمدة"):
        assert qty_of(lines, name) == 0


def test_hv_pole_coefficients_equal_the_9m_ones():
    """معاملات أعمدة 11م تطابق معاملات أعمدة 9م — نفس الجدول."""
    own = materials_lv(NetworkLV(kind=CABLE, poles_lattice=5, poles_round=16))
    on_hv = materials_lv(NetworkLV(on_hv_poles=True, hv_kind=CABLE,
                                   hv_poles_lattice=5, hv_poles_round=16))
    for name in ("هوك تعليق (قابلو)", "كلامب شد (قابلو)", "كلامب تعليق (قابلو)"):
        assert qty_of(own, name) == qty_of(on_hv, name)


def test_hv_kind_can_differ_from_the_main_kind():
    """قد تكون الشبكة على أعمدة الضغط العالي بنوع مختلف عن الشبكة الأساسية."""
    net = NetworkLV(kind=WIRES, poles_lattice=10,
                    on_hv_poles=True, hv_kind=CABLE, hv_poles_lattice=5)
    lines = materials_lv(net)
    assert qty_of(lines, "بوكس كلامب (أسلاك)") == 10 * 8    # الأساسية أسلاك
    assert qty_of(lines, "كلامب شد (قابلو)") == 5 * 2        # وعلى أعمدة ض.ع قابلو


def test_hv_section_is_ignored_when_switched_off():
    net = NetworkLV(on_hv_poles=False, hv_poles_lattice=5, hv_poles_round=16)
    assert materials_lv(net) == []


# ═══════════════════════ ٦. المستهلكون ═══════════════════════


def test_one_connector_per_consumer(catalog):
    """ق-٢٢: كونكتر ربط مشتركين واحد لكل مستهلك."""
    lines = materials_lv(NetworkLV(consumers=25))
    assert qty_of(lines, "كونكتر ربط مشتركين") == 25


def test_consumer_connector_price_is_pending_not_zero(catalog):
    """السعر غير محدَّد بعد — يُبلَّغ عنه ولا يُحتسب صفراً بصمت."""
    result = compute(OverheadProject(netlv=NetworkLV(consumers=25)), catalog)
    assert "كونكتر ربط مشتركين" in result["أسعار_مفقودة"]
    row = next(r for r in result["المواد"] if r["المادة"] == "كونكتر ربط مشتركين")
    assert row["الكمية"] == 25
    assert row["الكلفة"] == 0
    assert row["سعر_مفقود"] is True


def test_consumer_labour_rate_is_pending(catalog):
    """أجر ربط المستهلكين يُترك فارغاً حالياً ويُبلَّغ عنه (ق-٢٢)."""
    result = compute(OverheadProject(netlv=NetworkLV(consumers=25)), catalog)
    assert "ربط المستهلكين" in result["أجور_مفقودة"]
    line = next(l for l in result["أجور_العمل"] if l.name == "ربط المستهلكين")
    assert line.rate_missing is True
    assert line.cost == 0


def test_pending_rate_does_not_corrupt_the_total(catalog):
    """البند بلا أجر لا يُسقط المجموع ولا يضيف صفراً خاطئاً."""
    without = compute(OverheadProject(netlv=NetworkLV(poles_lattice=5)), catalog)
    with_consumers = compute(
        OverheadProject(netlv=NetworkLV(poles_lattice=5, consumers=100)), catalog
    )
    assert with_consumers["كلفة_العمل"] == without["كلفة_العمل"]


# ═══════════════════════ ٧. الأجور ═══════════════════════


def test_wiring_labour_follows_the_kind(catalog):
    rates = catalog["أجور_العمل"]
    wires = labour_lv(NetworkLV(route_length_m=1000, kind=WIRES), rates)
    cable = labour_lv(NetworkLV(route_length_m=1000, kind=CABLE), rates)

    assert wires[0].name == "تسليك شبكة الضغط الواطئ (أسلاك)"
    assert wires[0].cost == 4400 * 500
    assert cable[0].name == "تسليك شبكة الضغط الواطئ (قابلو معلق مبروم)"
    assert cable[0].cost == 1100 * 1500


def test_pole_installation_rates(catalog):
    lines = labour_lv(NetworkLV(poles_lattice=11, poles_round=40), catalog["أجور_العمل"])
    costs = {l.name: l.cost for l in lines}
    assert costs["نصب عمود مشبك 9م"] == 11 * 185_000
    assert costs["نصب عمود مدور 9م"] == 40 * 160_000


# ═══════════════════════ ٨. التكامل ═══════════════════════


def test_lv_aggregates_with_the_overhead_networks(catalog):
    """سلك النحاس والكونكريت يُدمجان عبر الجهود الثلاثة."""
    project = OverheadProject(
        net11=Network11kV(poles_lattice=5, poles_round=16),
        netlv=NetworkLV(poles_lattice=11, poles_round=40),
    )
    result = compute(project, catalog)
    copper = next(r for r in result["المواد"] if r["المادة"] == "سلك نحاس 50 ملم2")
    assert copper["الكمية"] == (21 + 51) * 1.5
    assert copper["مجمَّع"] is True
    sources = [p["المصدر"] for p in copper["تفصيل"]]
    assert any("11م" in s for s in sources)
    assert any("ض.و" in s for s in sources)


def test_project_without_lv_is_unaffected(catalog):
    """المشاريع التي لا تتضمّن ضغطاً واطئاً لا تتغيّر نتائجها."""
    project = OverheadProject(net11=Network11kV(route_length_m=500, poles_lattice=5,
                                                poles_round=16))
    assert project.netlv is None
    result = compute(project, catalog)
    assert result["كلفة_المواد"] > 0
    assert not any("ض.و" in m["المادة"] for m in result["المواد"])


def test_empty_lv_network_produces_nothing():
    assert materials_lv(NetworkLV()) == []
