# -*- coding: utf-8 -*-
"""اختبارات محرك الشبكة الأرضية 11 ك.ف (ق-٣٠).

القاعدة الحاكمة تحت الاختبار في كل مكان هنا: **طول المسار وحده** يحدّد الأعمال
المدنية وموادّ الخندق، و**طول المسار × عدد المغذيات** يحدّد كمية القابلو وأجر مدّه.
"""

import pytest

from engine import load_catalog
from engine.project import compute_project
from engine.types import Project, Segment, SidewalkType, Underground11kV
from engine.underground import (
    cable_quantity,
    civil_works_rate,
    materials_underground11,
    resolve_drum_length,
    suggest_straight_boxes,
)


@pytest.fixture
def catalog():
    return load_catalog()


def qty(lines, name):
    return sum(l.qty for l in lines if l.name == name)


# ═══════════════════ كمية القابلو ═══════════════════


def test_cable_quantity_is_route_times_feeders_times_waste():
    net = Underground11kV(route_length_m=1000, feeder_count=3)
    assert cable_quantity(net) == 3300          # 1000 × 3 × 1.1


def test_single_feeder_matches_the_simple_case():
    net = Underground11kV(route_length_m=500, feeder_count=1)
    assert cable_quantity(net) == 550


def test_waste_included_flag_skips_the_10_percent():
    net = Underground11kV(route_length_m=1000, feeder_count=2, length_includes_waste=True)
    assert cable_quantity(net) == 2000


def test_zero_route_length_produces_nothing():
    assert cable_quantity(Underground11kV(route_length_m=0, feeder_count=5)) == 0


# ═══════════════════ الصندوق المستقيم — لكل مغذٍّ على حدة ═══════════════════


def test_the_users_own_examples():
    """350÷250 → 1، و600÷250 → 2 — الأمثلة التي ذكرها المستخدم حرفياً."""
    assert suggest_straight_boxes(350, 1, 250) == 1
    assert suggest_straight_boxes(600, 1, 250) == 2


def test_multiple_feeders_multiply_the_per_feeder_count():
    """3 مغذيات بطول 260م لكل واحد: صندوق واحد لكل مغذٍّ × 3 = 3 — لا من المجموع."""
    assert suggest_straight_boxes(260, 3, 250) == 3


def test_the_per_feeder_rule_is_the_exact_sum_of_independent_feeders():
    """الصيغة الصحيحة فيزيائياً: مجموع احتياج كل مغذٍّ مستقلاً — لا تقريب مجمَّع.

    قد يقع المجموع فوق أو تحت ما ينتجه حساب «الكمية المجمَّعة» في الملف الأصلي
    (700م × 5 مغذيات بطول بكرة 300م: هنا 10، والمجمَّع 11) — والمعيار الصحيح هو
    استقلال كل مغذٍّ لا القرب من رقم الملف الأصلي غير الصحيح أصلاً.
    """
    for route, feeders, drum, expected in [
        (350, 1, 250, 1),
        (700, 5, 300, 10),          # 5 × (⌈700/300⌉ − 1) = 5 × 2 = 10
        (1000, 2, 400, 4),          # 2 × (⌈1000/400⌉ − 1) = 2 × 2 = 4
    ]:
        assert suggest_straight_boxes(route, feeders, drum) == expected


def test_route_shorter_than_one_drum_needs_no_box():
    assert suggest_straight_boxes(200, 4, 250) == 0


def test_zero_inputs_produce_zero_boxes():
    assert suggest_straight_boxes(0, 3, 250) == 0
    assert suggest_straight_boxes(500, 0, 250) == 0
    assert suggest_straight_boxes(500, 3, 0) == 0


def test_drum_length_resolves_from_catalog_when_unset(catalog):
    assert resolve_drum_length(Underground11kV(), catalog) == 250


def test_drum_length_user_value_overrides_the_default(catalog):
    net = Underground11kV(drum_length_m=300)
    assert resolve_drum_length(net, catalog) == 300


# ═══════════════════ المواد ═══════════════════


def test_materials_match_the_users_worked_example():
    net = Underground11kV(
        route_length_m=600, feeder_count=2, straight_boxes=4,
        end_boxes_internal=1, end_boxes_external=1,
    )
    lines = materials_underground11(net)
    assert qty(lines, "قابلو 3×150 ملم2 جهد 11 ك.ف") == 1320       # 600×2×1.1
    assert qty(lines, "صندوق مستقيم 3×150 ملم2 جهد 11 ك.ف") == 4
    assert qty(lines, "صندوق نهاية داخلي 3×150 ملم2 جهد 11 ك.ف") == 1
    assert qty(lines, "صندوق نهاية خارجي 3×150 ملم2 جهد 11 ك.ف") == 1


def test_trench_materials_depend_on_route_length_only_not_on_feeder_count():
    """الشتايكر والرمل والشريط لا يتضاعفون بعدد المغذيات — خندق واحد."""
    single = materials_underground11(Underground11kV(route_length_m=500, feeder_count=1))
    triple = materials_underground11(Underground11kV(route_length_m=500, feeder_count=3))
    for name in ("شتايكر 50×50×5 سم", "رمل نهري", "شريط تحذير"):
        assert qty(single, name) == qty(triple, name)


def test_staker_formula():
    lines = materials_underground11(Underground11kV(route_length_m=1000, feeder_count=1))
    assert qty(lines, "شتايكر 50×50×5 سم") == 2000        # 1000 / 0.5


def test_sand_formula():
    lines = materials_underground11(Underground11kV(route_length_m=1000, feeder_count=1))
    assert qty(lines, "رمل نهري") == 240                  # 1000 × 0.6 × 0.4


def test_warning_tape_formula():
    lines = materials_underground11(Underground11kV(route_length_m=1000, feeder_count=1))
    assert qty(lines, "شريط تحذير") == 12                 # ⌈1000/90⌉


def test_trench_materials_are_quantity_only(catalog):
    prices = catalog["المواد"]
    for name in ("شتايكر 50×50×5 سم", "رمل نهري", "شريط تحذير"):
        assert prices[name]["كمية_فقط"] is True


def test_no_route_length_means_no_trench_materials():
    lines = materials_underground11(Underground11kV(route_length_m=0, feeder_count=2))
    assert not any(l.name in ("شتايكر 50×50×5 سم", "رمل نهري", "شريط تحذير") for l in lines)


# ═══════════════════ الأعمال المدنية ═══════════════════


def test_civil_works_rate_depends_on_sidewalk_and_feeder_count(catalog):
    net = Underground11kV(sidewalk_type=SidewalkType.TERRAZZO, feeder_count=3)
    assert civil_works_rate(net, catalog) == 37000


def test_civil_works_rate_all_fifteen_combinations_match_the_original_file(catalog):
    expected = {
        ("ترابي", 1): 20000, ("ترابي", 2): 26000, ("ترابي", 3): 31000,
        ("ترابي", 4): 36000, ("ترابي", 5): 39000,
        ("مبلط", 1): 18000, ("مبلط", 2): 22000, ("مبلط", 3): 26000,
        ("مبلط", 4): 30000, ("مبلط", 5): 34000,
        ("مقرنص", 1): 34000, ("مقرنص", 2): 36000, ("مقرنص", 3): 37000,
        ("مقرنص", 4): 41000, ("مقرنص", 5): 45000,
    }
    for sidewalk in SidewalkType:
        for count in range(1, 6):
            net = Underground11kV(sidewalk_type=sidewalk, feeder_count=count)
            assert civil_works_rate(net, catalog) == expected[(sidewalk.value, count)]


def test_civil_works_rate_beyond_the_table_is_reported_not_guessed(catalog):
    """6 مغذيات خارج الجدول (1-5 فقط) — يُبلَّغ عنه لا يُخمَّن."""
    net = Underground11kV(route_length_m=100, feeder_count=6)
    assert civil_works_rate(net, catalog) is None

    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    assert "الأعمال المدنية — رصيف ترابي × 6 مغذٍّ" in result["أجور_مفقودة"]


def test_civil_works_cost_is_route_length_times_rate_not_cable_quantity(catalog):
    """المدنية تُحسب من طول المسار — لا من كمية القابلو المضروبة بالمغذيات."""
    net = Underground11kV(route_length_m=400, feeder_count=3, sidewalk_type=SidewalkType.EARTH)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    civil = next(l for l in result["أجور_العمل"] if l.name.startswith("الأعمال المدنية"))
    assert civil.qty == 400                # لا 1320 (طول القابلو)
    assert civil.rate == 31000
    assert civil.cost == 400 * 31000


# ═══════════════════ الأجور الأخرى ═══════════════════


def test_cable_laying_labour_uses_the_multiplied_cable_quantity(catalog):
    net = Underground11kV(route_length_m=400, feeder_count=3)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    laying = next(l for l in result["أجور_العمل"] if l.name == "كلفة مد القابلو 11 ك.ف")
    assert laying.qty == 1320               # 400×3×1.1 — لا 400
    assert laying.rate == 3500


def test_end_boxes_share_one_labour_line_like_the_original_file(catalog):
    """صندوق نهاية داخلي وخارجي يجتمعان في بند أجر واحد — كما فعل الملف الأصلي."""
    net = Underground11kV(route_length_m=1, end_boxes_internal=2, end_boxes_external=3)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    boxes = [l for l in result["أجور_العمل"] if l.name == "كلفة نصب صندوق نهاية 11 ك.ف"]
    assert len(boxes) == 1 and boxes[0].qty == 5


def test_straight_and_end_boxes_are_separate_labour_items(catalog):
    net = Underground11kV(route_length_m=1, straight_boxes=2, end_boxes_internal=1)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    names = {l.name for l in result["أجور_العمل"]}
    assert "كلفة نصب صندوق مستقيم 11 ك.ف" in names
    assert "كلفة نصب صندوق نهاية 11 ك.ف" in names


# ═══════════════════ عبور الشوارع — للمشروع كله لا للمقطع ═══════════════════


def test_street_crossings_are_project_level_not_per_segment(catalog):
    project = Project(
        segments=[Segment("م", Underground11kV(route_length_m=100))],
        street_crossing_secondary_m=50,
        street_crossing_main_m=20,
    )
    result = compute_project(project, catalog)
    secondary = next(l for l in result["أجور_العمل"] if l.name == "عبور الشوارع الفرعية")
    main = next(
        l for l in result["أجور_العمل"] if l.name == "عبور الشوارع الرئيسية – حفر مخفي"
    )
    assert secondary.qty == 50 and secondary.cost == 5_000_000
    assert main.qty == 20 and main.cost == 4_000_000


def test_street_crossings_do_not_appear_when_zero(catalog):
    result = compute_project(Project(), catalog)
    names = {l.name for l in result["أجور_العمل"]}
    assert "عبور الشوارع الفرعية" not in names
    assert "عبور الشوارع الرئيسية – حفر مخفي" not in names


def test_street_crossings_are_not_duplicated_across_multiple_segments(catalog):
    """رقم إجمالي واحد للمشروع، مهما تعدّدت مقاطعه الأرضية."""
    project = Project(
        segments=[
            Segment("أ", Underground11kV(route_length_m=100)),
            Segment("ب", Underground11kV(route_length_m=200)),
        ],
        street_crossing_secondary_m=30,
    )
    result = compute_project(project, catalog)
    rows = [l for l in result["أجور_العمل"] if l.name == "عبور الشوارع الفرعية"]
    assert len(rows) == 1 and rows[0].qty == 30


# ═══════════════════ التكامل والتتبّع ═══════════════════


def test_every_underground_material_has_a_traceable_source():
    net = Underground11kV(
        route_length_m=300, feeder_count=2, straight_boxes=1,
        end_boxes_internal=1, end_boxes_external=1,
    )
    for line in materials_underground11(net):
        assert line.source


def test_empty_segment_produces_nothing(catalog):
    result = compute_project(Project(segments=[Segment("م", Underground11kV())]), catalog)
    assert result["المواد"] == []
    assert result["أجور_العمل"] == []


def test_mixing_overhead_and_underground_segments(catalog):
    """مشروع فيه شبكة هوائية وأرضية معاً — لا تعارض بين المسارين."""
    from engine.types import Network11kV

    project = Project(segments=[
        Segment("الجزء الهوائي", Network11kV(route_length_m=500, poles_lattice=5, poles_round=16)),
        Segment("الجزء الأرضي", Underground11kV(route_length_m=300, feeder_count=1)),
    ])
    result = compute_project(project, catalog)
    names = {m["المادة"] for m in result["المواد"]}
    assert "عمود 11م مشبك" in names
    assert "قابلو 3×150 ملم2 جهد 11 ك.ف" in names


def test_every_underground_material_is_priced_or_flagged(catalog):
    prices = catalog["المواد"]
    net = Underground11kV(
        route_length_m=100, feeder_count=1, straight_boxes=1,
        end_boxes_internal=1, end_boxes_external=1,
    )
    for line in materials_underground11(net):
        assert line.name in prices, f"مادة بلا صف في نسخة الأسعار: {line.name}"
        assert prices[line.name]["الوحدة"] == line.unit


# ═══════════════════════════ 33 ك.ف — قابلو 1×400 ملم² (ق-٣١) ═══════════════════════════

from engine.types import CircuitType, Underground33kV  # noqa: E402
from engine.underground import (  # noqa: E402
    cable_count_33,
    cable_quantity_33,
    civil_works_rate_33,
    labour_underground33,
    materials_underground33,
    resolve_drum_length_33,
)


# ─────────────────── عدد الكابلات وكمية القابلو ───────────────────


def test_single_circuit_is_three_cables():
    net = Underground33kV(circuit=CircuitType.SINGLE)
    assert cable_count_33(net) == 3


def test_double_circuit_is_six_cables():
    net = Underground33kV(circuit=CircuitType.DOUBLE)
    assert cable_count_33(net) == 6


def test_the_users_own_worked_example():
    """500م مزدوجة الدائرة ← 500×6×1.1 = 3300م — الرقم الذي ذكره المستخدم حرفياً."""
    net = Underground33kV(route_length_m=500, circuit=CircuitType.DOUBLE)
    assert cable_quantity_33(net) == 3300


def test_single_circuit_worked_example():
    net = Underground33kV(route_length_m=500, circuit=CircuitType.SINGLE)
    assert cable_quantity_33(net) == 1650          # 500×3×1.1


def test_waste_included_flag_skips_the_10_percent_33():
    net = Underground33kV(route_length_m=500, circuit=CircuitType.DOUBLE,
                           length_includes_waste=True)
    assert cable_quantity_33(net) == 3000


def test_zero_route_length_produces_nothing_33():
    assert cable_quantity_33(Underground33kV(route_length_m=0, circuit=CircuitType.DOUBLE)) == 0


# ─────────────────── طول البكرة الافتراضي ───────────────────


def test_drum_length_33_defaults_to_500(catalog):
    assert resolve_drum_length_33(Underground33kV(), catalog) == 500


def test_drum_length_33_differs_from_11kv_default(catalog):
    assert resolve_drum_length_33(Underground33kV(), catalog) != \
        resolve_drum_length(Underground11kV(), catalog)


# ─────────────────── الصندوق المستقيم — لكل كابل (طور) على حدة ───────────────────


def test_straight_boxes_use_the_cable_count_not_the_circuit_count():
    """مزدوجة الدائرة (500م، بكرة 500م) لا تحتاج صندوقاً — الطول لا يتجاوز البكرة."""
    net = Underground33kV(route_length_m=500, circuit=CircuitType.DOUBLE, drum_length_m=500)
    assert suggest_straight_boxes(net.route_length_m, cable_count_33(net), net.drum_length_m) == 0


def test_straight_boxes_scale_with_the_six_cables_of_a_double_circuit():
    """1000م مزدوجة ببكرة 500م: لكل كابل صندوق واحد × 6 كابلات = 6."""
    net = Underground33kV(route_length_m=1000, circuit=CircuitType.DOUBLE, drum_length_m=500)
    assert suggest_straight_boxes(net.route_length_m, cable_count_33(net), net.drum_length_m) == 6


# ─────────────────── الأعمال المدنية — المغذي الواحد كمغذٍّ واحد (ق-٣١) ───────────────────


def test_civil_rate_uses_circuit_count_not_cable_count(catalog):
    """مفردة (3 كابلات) تُعامَل كـ«1» لا «3» — بتأكيد المستخدم صراحةً."""
    single = Underground33kV(sidewalk_type=SidewalkType.EARTH, circuit=CircuitType.SINGLE)
    assert civil_works_rate_33(single, catalog) == 20000       # نفس تعرفة "1" في جدول 11 ك.ف


def test_civil_rate_double_circuit_uses_count_two(catalog):
    double = Underground33kV(sidewalk_type=SidewalkType.PAVED, circuit=CircuitType.DOUBLE)
    assert civil_works_rate_33(double, catalog) == 22000        # نفس تعرفة "2"


def test_civil_rate_33_and_11_share_the_exact_same_table(catalog):
    """جدول واحد للجهدين — لا نسخة منفصلة لـ33 ك.ف."""
    for sidewalk in SidewalkType:
        for circuit, count in ((CircuitType.SINGLE, 1), (CircuitType.DOUBLE, 2)):
            ug33 = Underground33kV(sidewalk_type=sidewalk, circuit=circuit)
            ug11 = Underground11kV(sidewalk_type=sidewalk, feeder_count=count)
            assert civil_works_rate_33(ug33, catalog) == civil_works_rate(ug11, catalog)


def test_civil_works_cost_is_route_length_not_cable_quantity_33(catalog):
    net = Underground33kV(route_length_m=500, circuit=CircuitType.DOUBLE,
                           sidewalk_type=SidewalkType.EARTH)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    civil = next(l for l in result["أجور_العمل"] if l.name.startswith("الأعمال المدنية"))
    assert civil.qty == 500                # لا 3300 (كمية القابلو)
    assert civil.rate == 26000


# ─────────────────── المواد ───────────────────


def test_materials_match_the_prices_from_the_original_file(catalog):
    prices = catalog["المواد"]
    assert prices["قابلو 1×400 ملم2 جهد 33 ك.ف"]["السعر"] == 85000
    assert prices["صندوق مستقيم 1×400 ملم2 جهد 33 ك.ف"]["السعر"] == 285000
    assert prices["صندوق نهاية داخلي 1×400 ملم2 جهد 33 ك.ف"]["السعر"] == 408000
    assert prices["صندوق نهاية خارجي 1×400 ملم2 جهد 33 ك.ف"]["السعر"] == 471000


def test_end_boxes_are_counted_per_piece_not_per_set(catalog):
    """الوحدة «عدد» لا «سيت» — والسعر سعر الصندوق الواحد (ق-٣٥).

    خلافاً للملف الأصلي الذي كان يسمّيها «سيت» بينما سعره سعر المفرد — فكان
    يحسب ثلث الكلفة الحقيقية.
    """
    prices = catalog["المواد"]
    assert prices["صندوق نهاية داخلي 1×400 ملم2 جهد 33 ك.ف"]["الوحدة"] == "عدد"
    assert prices["صندوق نهاية خارجي 1×400 ملم2 جهد 33 ك.ف"]["الوحدة"] == "عدد"


def test_one_end_set_generates_three_boxes():
    """السيت الواحد 3 صناديق — صندوق لكل طور (ق-٣٥)."""
    from engine.underground import BOXES_PER_END_SET_33

    assert BOXES_PER_END_SET_33 == 3
    lines = materials_underground33(Underground33kV(route_length_m=1, end_boxes_internal=1))
    assert qty(lines, "صندوق نهاية داخلي 1×400 ملم2 جهد 33 ك.ف") == 3


def test_end_box_cost_triples_versus_the_old_per_set_reading(catalog):
    """أثر مالي مقصود: كلفة نقطة النهاية الواحدة تصير ثلاثة أضعاف ما كانت."""
    net = Underground33kV(route_length_m=1, end_boxes_internal=1)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    row = next(m for m in result["المواد"]
               if m["المادة"] == "صندوق نهاية داخلي 1×400 ملم2 جهد 33 ك.ف")
    assert row["الكمية"] == 3
    assert row["سعر الوحدة"] == 408_000          # سعر الصندوق الواحد بلا تغيير
    assert row["الكلفة"] == 3 * 408_000


def test_eleven_kv_end_boxes_are_not_multiplied():
    """11 ك.ف كابله ثلاثي القلب فنهايته صندوق واحد — لا ×3 (ق-٣٥)."""
    lines = materials_underground11(
        Underground11kV(route_length_m=1, end_boxes_internal=2, end_boxes_external=3)
    )
    assert qty(lines, "صندوق نهاية داخلي 3×150 ملم2 جهد 11 ك.ف") == 2
    assert qty(lines, "صندوق نهاية خارجي 3×150 ملم2 جهد 11 ك.ف") == 3


def test_trench_materials_are_shared_with_11kv_and_route_length_based():
    net33 = Underground33kV(route_length_m=1000, circuit=CircuitType.DOUBLE)
    net11 = Underground11kV(route_length_m=1000, feeder_count=1)
    lines33, lines11 = materials_underground33(net33), materials_underground11(net11)
    for name in ("شتايكر 50×50×5 سم", "رمل نهري", "شريط تحذير"):
        assert qty(lines33, name) == qty(lines11, name)


def test_end_boxes_manual_no_advisory_33(catalog):
    """صناديق النهاية 33 ك.ف يدوية بحتة — والمُدخَل سيتات تُضرب ×3 (ق-٣٥)."""
    net = Underground33kV(route_length_m=500, end_boxes_internal=3, end_boxes_external=2)
    lines = materials_underground33(net)
    assert qty(lines, "صندوق نهاية داخلي 1×400 ملم2 جهد 33 ك.ف") == 9
    assert qty(lines, "صندوق نهاية خارجي 1×400 ملم2 جهد 33 ك.ف") == 6


# ─────────────────── الأجور ───────────────────


def test_cable_laying_labour_uses_the_cable_quantity_33(catalog):
    net = Underground33kV(route_length_m=500, circuit=CircuitType.DOUBLE)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    laying = next(l for l in result["أجور_العمل"] if l.name == "كلفة مد القابلو 33 ك.ف")
    assert laying.qty == 3300
    assert laying.rate == 2000


def test_end_boxes_share_one_labour_line_33(catalog):
    net = Underground33kV(route_length_m=1, end_boxes_internal=2, end_boxes_external=3)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    boxes = [l for l in result["أجور_العمل"] if l.name == "كلفة نصب صندوق نهاية 33 ك.ف"]
    assert len(boxes) == 1 and boxes[0].qty == 5
    assert boxes[0].rate == 225000


def test_33kv_and_11kv_labour_rates_are_independent(catalog):
    """أسعار 33 ك.ف مختلفة عن 11 ك.ف — لا مشاركة سعر بالخطأ."""
    rates = catalog["أجور_العمل"]
    assert rates["كلفة مد القابلو 11 ك.ف"]["السعر"] != rates["كلفة مد القابلو 33 ك.ف"]["السعر"]
    assert rates["كلفة نصب صندوق نهاية 11 ك.ف"]["السعر"] != \
        rates["كلفة نصب صندوق نهاية 33 ك.ف"]["السعر"]


# ─────────────────── التكامل ───────────────────


def test_11kv_and_33kv_underground_segments_coexist(catalog):
    project = Project(segments=[
        Segment("مقطع 11", Underground11kV(route_length_m=300, feeder_count=1)),
        Segment("مقطع 33", Underground33kV(route_length_m=500, circuit=CircuitType.SINGLE)),
    ])
    result = compute_project(project, catalog)
    names = {m["المادة"] for m in result["المواد"]}
    assert "قابلو 3×150 ملم2 جهد 11 ك.ف" in names
    assert "قابلو 1×400 ملم2 جهد 33 ك.ف" in names


def test_empty_33kv_segment_produces_nothing(catalog):
    result = compute_project(Project(segments=[Segment("م", Underground33kV())]), catalog)
    assert result["المواد"] == []
    assert result["أجور_العمل"] == []


def test_every_33kv_material_is_priced_or_flagged(catalog):
    prices = catalog["المواد"]
    net = Underground33kV(
        route_length_m=100, circuit=CircuitType.DOUBLE, straight_boxes=1,
        end_boxes_internal=1, end_boxes_external=1,
    )
    for line in materials_underground33(net):
        assert line.name in prices, f"مادة بلا صف في نسخة الأسعار: {line.name}"
        assert prices[line.name]["الوحدة"] == line.unit
