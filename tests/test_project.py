# -*- coding: utf-8 -*-
"""اختبارات نموذج المقاطع (ق-٢٤).

المشروع الواقعي مقاطع لا شبكة واحدة. المثال الذي وصفه المستخدم:
مقطع أرضي (مؤجَّل)، ومقطع هوائي مزدوج، ومقطع هوائي مفرد، ومقطع مفرد مع ضغط واطئ
على أعمدته، ومقطع ضغط واطئ بالقابلو المعلق، ومقطع ضغط واطئ بالأسلاك.
"""

import pytest

from engine import load_catalog
from engine.overhead import compute
from engine.project import aggregate_labour, compute_project, labour_of, materials_of
from engine.types import (
    CircuitType,
    Equipment,
    LabourLine,
    LVNetworkType,
    Network11kV,
    Network33kV,
    NetworkLV,
    OverheadProject,
    Project,
    Segment,
    SegmentKind,
    segment_default_name,
)


@pytest.fixture
def catalog():
    return load_catalog()


def material(result, name):
    return next(m for m in result["المواد"] if m["المادة"] == name)


def labour(result, name):
    return next(l for l in result["أجور_العمل"] if l.name == name)


# ═══════════════════ نوع المقطع ═══════════════════


def test_segment_kind_is_derived_from_its_content():
    """النوع مشتقّ لا مُدخَل — فلا يمكن أن يتعارض مع المحتوى."""
    assert Segment("أ", Network11kV()).kind is SegmentKind.HV11
    assert Segment("ب", Network33kV()).kind is SegmentKind.HV33
    assert Segment("ج", NetworkLV()).kind is SegmentKind.LV
    assert Segment("د", Equipment()).kind is SegmentKind.EQUIPMENT


def test_unknown_content_is_rejected_loudly():
    with pytest.raises(TypeError):
        Segment("هـ", "نصّ").kind


def test_default_names_follow_the_users_wording():
    assert segment_default_name(0) == "المقطع الأول"
    assert segment_default_name(5) == "المقطع السادس"
    assert segment_default_name(19) == "المقطع العشرون"
    assert segment_default_name(20) == "المقطع 21"


# ═══════════════════ الوسم والتتبّع ═══════════════════


def test_segment_name_is_stamped_on_every_source(catalog):
    """اسم المقطع يظهر في مصدر كل سطر — بلا ذلك يستحيل تدقيق مشروع متعدد المقاطع."""
    segment = Segment("المقطع الثاني", Network11kV(route_length_m=500))
    assert all(line.source.startswith("المقطع الثاني ← ") for line in materials_of(segment))


def test_an_unnamed_segment_adds_no_prefix():
    """المشروع البسيط يمرّ بمقاطع بلا أسماء فلا يتلوّث مصدره بوسم فارغ."""
    segment = Segment("", Network11kV(route_length_m=500))
    assert not any("←" in line.source for line in materials_of(segment))


def test_the_breakdown_shows_which_segment_each_number_came_from(catalog):
    project = Project(
        "مشروع",
        [
            Segment("المقطع الأول", Network11kV(route_length_m=300)),
            Segment("المقطع الثاني", Network11kV(route_length_m=700)),
        ],
    )
    result = compute_project(project, catalog)
    wire = material(result, "سلك ألمنيوم 120/20 ملم²")
    assert wire["مجمَّع"] is True
    sources = [p["المصدر"] for p in wire["تفصيل"]]
    assert any(s.startswith("المقطع الأول ←") for s in sources)
    assert any(s.startswith("المقطع الثاني ←") for s in sources)


# ═══════════════════ التجميع ═══════════════════


def test_linear_quantities_add_up_across_segments(catalog):
    """كمية السلك في مقطعين 300+700 = كميتها في مسار واحد 1000."""
    split = compute_project(
        Project(segments=[
            Segment("أ", Network11kV(route_length_m=300)),
            Segment("ب", Network11kV(route_length_m=700)),
        ]),
        catalog,
    )
    whole = compute(OverheadProject(net11=Network11kV(route_length_m=1000)), catalog)
    assert material(split, "سلك ألمنيوم 120/20 ملم²")["الكمية"] == \
        material(whole, "سلك ألمنيوم 120/20 ملم²")["الكمية"]


def test_single_and_double_segments_keep_their_own_circuit_type(catalog):
    """المزدوج يضاعف سلكه والمفرد لا — وهذا كل سبب وجود المقاطع."""
    project = Project(segments=[
        Segment("مزدوج", Network11kV(route_length_m=1000, circuit=CircuitType.DOUBLE)),
        Segment("مفرد", Network11kV(route_length_m=1000, circuit=CircuitType.SINGLE)),
    ])
    result = compute_project(project, catalog)
    # 1000×6×1.1 = 6600  و 1000×3×1.1 = 3300
    assert material(result, "سلك ألمنيوم 120/20 ملم²")["الكمية"] == 9900


def test_mixed_low_voltage_is_now_expressible(catalog):
    """الشبكة المختلطة: مقطع بالأسلاك ومقطع بالقابلو المعلق في مشروع واحد.

    هذا ما كان مستحيلاً قبل المقاطع — النموذج القديم يقبل نوعاً واحداً للمشروع كله.
    """
    project = Project(segments=[
        Segment("قابلو", NetworkLV(route_length_m=400, kind=LVNetworkType.BUNDLED_CABLE,
                                   poles_lattice=5, poles_round=16)),
        Segment("أسلاك", NetworkLV(route_length_m=600, kind=LVNetworkType.BARE_WIRES,
                                   poles_lattice=7, poles_round=24)),
    ])
    result = compute_project(project, catalog)
    names = [m["المادة"] for m in result["المواد"]]
    assert "قابلو ألمنيوم معلق 3×120+95+16 ملم²" in names
    assert "سلك ألمنيوم 95 ملم²" in names
    # الكلامبات تتبع كل مقطع نوعه: بوكس كلامب للأسلاك، وهوك وكلامبات للقابلو
    assert material(result, "بكرة عازلة ض.و مع الملحقات")["الكمية"] == 7 * 8 + 24 * 4
    assert material(result, "هوك تعليق")["الكمية"] == 5 * 2 + 16 * 1


# ═══════════════════ أجور العمل ═══════════════════


def test_identical_labour_items_merge_into_one_row(catalog):
    """بند الأجر لا يتكرّر ثلاث مرات في مشروع من ثلاثة مقاطع."""
    project = Project(segments=[
        Segment(f"م{i}", Network11kV(route_length_m=200, poles_lattice=2, poles_round=6))
        for i in range(3)
    ])
    result = compute_project(project, catalog)
    rows = [l for l in result["أجور_العمل"] if l.name == "نصب عمود مشبك 11م"]
    assert len(rows) == 1
    assert rows[0].qty == 6


def test_labour_with_different_rates_stays_separate(catalog):
    """أجر عمود 14م يختلف بين المفرد (260,000) والمزدوج (450,000) — لا يُدمجان."""
    project = Project(segments=[
        Segment("مفرد", Network33kV(poles_suspension=4, circuit=CircuitType.SINGLE)),
        Segment("مزدوج", Network33kV(poles_suspension=4, circuit=CircuitType.DOUBLE)),
    ])
    result = compute_project(project, catalog)
    rows = [l for l in result["أجور_العمل"] if l.name == "نصب عمود مشبك تعليق 14م"]
    assert sorted(l.rate for l in rows) == [260_000, 450_000]
    assert sum(l.cost for l in rows) == 4 * 260_000 + 4 * 450_000


def test_merged_labour_keeps_both_sources():
    a = LabourLine("نصب عمود مشبك 11م", "عمود", 2, 215_000, "المقطع الأول")
    b = LabourLine("نصب عمود مشبك 11م", "عمود", 3, 215_000, "المقطع الثاني")
    merged = aggregate_labour([a, b])
    assert len(merged) == 1
    assert merged[0].qty == 5
    assert merged[0].source == "المقطع الأول + المقطع الثاني"


def test_a_missing_rate_survives_the_merge(catalog):
    """بند بلا أجر يبقى بلا أجر بعد الدمج — لا يتحوّل إلى صفر.

    بأجر **مُحقون**: بعد ق-٣٦ صارت كل البنود مسعّرة، فربط الاختبار ببند بعينه
    يجعله يفشل مع كل تحديث أسعار.
    """
    import copy

    catalog = copy.deepcopy(catalog)
    catalog["أجور_العمل"]["ربط المستهلكين"]["السعر"] = None

    project = Project(segments=[
        Segment("أ", NetworkLV(consumers=5)),
        Segment("ب", NetworkLV(consumers=7)),
    ])
    result = compute_project(project, catalog)
    row = labour(result, "ربط المستهلكين")
    assert row.qty == 12
    assert row.rate_missing
    assert "ربط المستهلكين" in result["أجور_مفقودة"]


# ═══════════════════ مثال المستخدم ═══════════════════


def test_the_users_six_segment_example(catalog):
    """المثال الذي وصفه المستخدم — بلا المقطع الأرضي، فهو مؤجَّل بـ ق-١٢."""
    project = Project(
        "مشروع متعدد المقاطع",
        [
            Segment(
                segment_default_name(1),
                Network11kV(route_length_m=800, circuit=CircuitType.DOUBLE,
                            poles_lattice=8, poles_round=25),
            ),
            Segment(
                segment_default_name(2),
                Network11kV(route_length_m=600, circuit=CircuitType.SINGLE,
                            poles_lattice=6, poles_round=19),
            ),
            Segment(
                segment_default_name(3),
                Network11kV(route_length_m=500, circuit=CircuitType.SINGLE,
                            poles_lattice=5, poles_round=16),
            ),
            Segment(
                segment_default_name(3) + " — ض.و على أعمدته",
                NetworkLV(route_length_m=500, kind=LVNetworkType.BUNDLED_CABLE,
                          on_hv_poles=True, hv_kind=LVNetworkType.BUNDLED_CABLE,
                          hv_poles_lattice=5, hv_poles_round=16),
            ),
            Segment(
                segment_default_name(4),
                NetworkLV(route_length_m=400, kind=LVNetworkType.BUNDLED_CABLE,
                          poles_lattice=5, poles_round=16),
            ),
            Segment(
                segment_default_name(5),
                NetworkLV(route_length_m=700, kind=LVNetworkType.BARE_WIRES,
                          poles_lattice=8, poles_round=28),
            ),
        ],
    )
    result = compute_project(project, catalog)

    assert len(result["المقاطع"]) == 6
    assert result["الكلفة_الكلية"] > 0

    # المقطع الرابع لا ينصب أعمدة: يستغلّ أعمدة الضغط العالي القائمة
    poles_9m = [m for m in result["المواد"] if m["المادة"].startswith("عمود 9م")]
    assert sum(m["الكمية"] for m in poles_9m) == 5 + 16 + 8 + 28

    # كل مادة مجمَّعة تحمل تفصيل مصادرها
    for row in result["المواد"]:
        assert row["تفصيل"]
        assert all(p["المصدر"] for p in row["تفصيل"])


def test_an_empty_project_produces_nothing(catalog):
    result = compute_project(Project(), catalog)
    assert result["المواد"] == []
    assert result["أجور_العمل"] == []
    assert result["الكلفة_الكلية"] == 0


def test_segment_order_is_preserved(catalog):
    """ترتيب المقاطع ترتيب المستخدم — يظهر كما أدخله في التفصيل والطباعة."""
    names = ["ج", "أ", "ب"]
    project = Project(segments=[Segment(n, Network11kV(route_length_m=100)) for n in names])
    result = compute_project(project, catalog)
    assert [s.name for s in result["المقاطع"]] == names
    wire = material(result, "سلك ألمنيوم 120/20 ملم²")
    assert [p["المصدر"].split(" ←")[0] for p in wire["تفصيل"]] == names


def test_simple_project_and_one_segment_project_agree(catalog):
    """المشروع البسيط ومشروع من مقطع واحد يعطيان الرقم نفسه — مسار حساب واحد."""
    net = Network11kV(route_length_m=1000, poles_lattice=9, poles_round=32, stay_rod_sets=2)
    simple = compute(OverheadProject(net11=net), catalog)
    segmented = compute_project(Project(segments=[Segment("", net)]), catalog)
    assert simple["الكلفة_الكلية"] == segmented["الكلفة_الكلية"]
    assert [m["الكمية"] for m in simple["المواد"]] == \
        [m["الكمية"] for m in segmented["المواد"]]


# ═══════════════════ عمود الوصل بين مقطعين ═══════════════════


def test_contiguous_segments_suggest_one_extra_pole_at_the_junction():
    """مسار 1000م يقترح 41 عموداً، ومقطعان 500+500 يقترحان 42.

    الفارق عمود شد واحد عند نقطة الوصل: كل مقطع يُنهي نفسه بعمود شد، والمقطعان
    المتلاصقان يتقاسمان عموداً واحداً فعلياً. المحرك لا يعرف أمتلاصقان هما أم
    فرعان منفصلان، فيُبقي الرقم الأكبر (الآمن) ويُنبّه المستخدم ليخصم بنفسه.
    الأعداد مُدخَلات قابلة للتعديل في كل الأحوال (ق-١٠).
    """
    from engine.overhead import count_poles_spanned

    whole = count_poles_spanned(1000, 25, 125)
    half = count_poles_spanned(500, 25, 125)

    assert (whole.lattice, whole.round_, whole.total) == (9, 32, 41)
    assert (half.lattice, half.round_, half.total) == (5, 16, 21)
    assert half.total * 2 - whole.total == 1
    assert half.lattice * 2 - whole.lattice == 1   # الفارق كله في عمود الشد
    assert half.round_ * 2 == whole.round_
