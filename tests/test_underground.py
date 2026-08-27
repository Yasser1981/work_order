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
    CIVIL_GROUP,
    civil_tariff_parts,
    civil_works_rate,
    street_crossing_pipes,
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


def test_materials_match_the_users_worked_example(catalog):
    net = Underground11kV(
        route_length_m=600, feeder_count=2, straight_boxes=4,
        end_boxes_internal=1, end_boxes_external=1,
    )
    lines = materials_underground11(net, catalog)
    assert qty(lines, "قابلو 3×150 ملم² جهد 11 ك.ف") == 1320       # 600×2×1.1
    assert qty(lines, "صندوق مستقيم 3×150 ملم² جهد 11 ك.ف") == 4
    assert qty(lines, "صندوق نهاية داخلي 3×150 ملم² جهد 11 ك.ف") == 1
    assert qty(lines, "صندوق نهاية خارجي 3×150 ملم² جهد 11 ك.ف") == 1


def test_the_trench_is_one_trench_but_its_width_follows_the_feeders(catalog):
    """خندق واحد لا خنادق — لكن عرضه يتّسع بعدد المغذيات، فتتبعه كمية الرمل (ق-٤٣).

    قبل ق-٤٣ كان العرض مثبَّتاً عند 0.6 م (وهو عرض المغذيَّين)، فكانت الكميات
    الثلاث متطابقة مهما بلغ عدد المغذيات.
    """
    one = materials_underground11(Underground11kV(route_length_m=500, feeder_count=1), catalog)
    three = materials_underground11(Underground11kV(route_length_m=500, feeder_count=3), catalog)

    # الرمل يتّسع: 500 × 0.5 × 0.4 = 100 ← 500 × 0.8 × 0.4 = 160
    assert qty(one, "رمل نهري") == 100
    assert qty(three, "رمل نهري") == 160

    # والشتايكر والشريط لا يتضاعفان ما دام العرض دون المتر
    for name in ("شتايكر 50×50×5 سم", "شريط تحذير"):
        assert qty(one, name) == qty(three, name)


def test_the_wide_trench_doubles_the_staker_and_the_tape(catalog):
    """العرض متر فأكثر (5 مغذيات فصاعداً) ← قطعتان متجاورتان ولفّتان (ق-٤٣)."""
    narrow = materials_underground11(Underground11kV(route_length_m=900, feeder_count=4), catalog)
    wide = materials_underground11(Underground11kV(route_length_m=900, feeder_count=5), catalog)

    assert qty(narrow, "شتايكر 50×50×5 سم") == 1800        # ⌈900 ÷ 0.5⌉
    assert qty(wide, "شتايكر 50×50×5 سم") == 3600          # × 2
    assert qty(narrow, "شريط تحذير") == 10                 # ⌈900 ÷ 90⌉
    assert qty(wide, "شريط تحذير") == 20                   # × 2


def test_the_doubling_threshold_is_the_width_not_the_feeder_count(catalog):
    """4 مغذيات عرضها 0.8 م فلا تتضاعف، و5 عرضها 1.0 م فتتضاعف — الحدّ هو العرض."""
    from engine.underground import is_wide_trench, trench_width_m

    assert trench_width_m(4, catalog) == 0.8 and not is_wide_trench(trench_width_m(4, catalog))
    assert trench_width_m(5, catalog) == 1.0 and is_wide_trench(trench_width_m(5, catalog))


def test_the_width_table_matches_the_user_numbers(catalog):
    """الجدول بنصّ المستخدم، وما فوق 8 يأخذ قيمة الثمانية."""
    from engine.underground import trench_width_m

    expected = {1: 0.5, 2: 0.6, 3: 0.8, 4: 0.8, 5: 1.0, 6: 1.2, 7: 1.5, 8: 1.8}
    for count, width in expected.items():
        assert trench_width_m(count, catalog) == width
    assert trench_width_m(12, catalog) == 1.8


def test_an_unknown_width_produces_no_guessed_quantities(catalog):
    """بلا جدول عرض لا تُخمَّن كمية رمل تُسلَّم للمنفّذ — يُبلَّغ بسطر صفر (ق-٤٣)."""
    import copy

    stripped = copy.deepcopy(catalog)
    stripped["عرض_الخندق"] = {}
    lines = materials_underground11(
        Underground11kV(route_length_m=500, feeder_count=2), stripped
    )
    trench = [l for l in lines if l.name in ("شتايكر 50×50×5 سم", "رمل نهري", "شريط تحذير")]
    assert len(trench) == 1
    assert trench[0].qty == 0
    assert "لا عرض خندق" in trench[0].source


def test_staker_formula(catalog):
    lines = materials_underground11(Underground11kV(route_length_m=1000, feeder_count=1), catalog)
    assert qty(lines, "شتايكر 50×50×5 سم") == 2000        # 1000 / 0.5


def test_sand_formula(catalog):
    lines = materials_underground11(Underground11kV(route_length_m=1000, feeder_count=1), catalog)
    assert qty(lines, "رمل نهري") == 200                  # 1000 × عرض 0.5 × سُمك 0.4


def test_warning_tape_formula(catalog):
    lines = materials_underground11(Underground11kV(route_length_m=1000, feeder_count=1), catalog)
    assert qty(lines, "شريط تحذير") == 12                 # ⌈1000/90⌉


def test_trench_materials_are_quantity_only(catalog):
    prices = catalog["المواد"]
    for name in ("شتايكر 50×50×5 سم", "رمل نهري", "شريط تحذير"):
        assert prices[name]["كمية_فقط"] is True


def test_no_route_length_means_no_trench_materials(catalog):
    lines = materials_underground11(Underground11kV(route_length_m=0, feeder_count=2), catalog)
    assert not any(l.name in ("شتايكر 50×50×5 سم", "رمل نهري", "شريط تحذير") for l in lines)


# ═══════════════════ الأعمال المدنية ═══════════════════


def test_civil_works_rate_depends_on_sidewalk_and_feeder_count(catalog):
    net = Underground11kV(sidewalk_type=SidewalkType.TERRAZZO, feeder_count=3)
    assert civil_works_rate(net, catalog) == 37000   # 12,000 حفر + 25,000 إعادة


def test_civil_works_rate_all_fifteen_combinations_match_the_original_file(catalog):
    """أربع عشرة خلية من خمس عشرة كما في الملف الأصلي — والخامسة عشرة ت-١١.

    التفصيل (ق-٣٨) والصيغة الممتدّة (ق-٤٧) يعيدان إجماليات الملف الأصلي كلها
    إلا **ترابي 4 مغذيات**: 35,000 بالصيغة مقابل 36,000 في الملف.
    """
    expected = {
        # ترابي 4 = 35,000 بالصيغة لا 36,000 كالملف الأصلي — ت-١١
        ("ترابي", 1): 20000, ("ترابي", 2): 26000, ("ترابي", 3): 31000,
        ("ترابي", 4): 35000, ("ترابي", 5): 39000,
        ("مبلط", 1): 18000, ("مبلط", 2): 22000, ("مبلط", 3): 26000,
        ("مبلط", 4): 30000, ("مبلط", 5): 34000,
        ("مقرنص", 1): 34000, ("مقرنص", 2): 36000, ("مقرنص", 3): 37000,
        ("مقرنص", 4): 41000, ("مقرنص", 5): 45000,
    }
    for sidewalk in SidewalkType:
        for count in range(1, 6):
            net = Underground11kV(sidewalk_type=sidewalk, feeder_count=count)
            assert civil_works_rate(net, catalog) == expected[(sidewalk.value, count)]


CIVIL_DETAIL = {
    # (الرصيف، تعدّد المسار): (حفر الخندق، إعادة المسار) — بنصّ المستخدم (ق-٣٨)
    ("ترابي", 1): (7000, 13000), ("ترابي", 2): (9000, 17000), ("ترابي", 3): (11000, 20000),
    ("مبلط", 1): (10000, 8000), ("مبلط", 2): (12000, 10000), ("مبلط", 3): (14000, 12000),
    ("مقرنص", 1): (9000, 25000), ("مقرنص", 2): (11000, 25000), ("مقرنص", 3): (12000, 25000),
}


def test_the_two_civil_components_match_the_user_numbers(catalog):
    """كل خلية من التسع: مكوّنان بالاسم والسعر كما أملاهما المستخدم."""
    for (sidewalk_value, count), (dig, restore) in CIVIL_DETAIL.items():
        sidewalk = next(s for s in SidewalkType if s.value == sidewalk_value)
        parts = civil_tariff_parts(sidewalk, count, catalog)
        assert parts == [("حفر الخندق", dig), ("إعادة المسار", restore)]


def test_the_detailed_components_sum_to_the_previous_totals_exactly(catalog):
    """حارس ت-٨ بعد حسمه: التفصيل لا يحرّك أي إجمالي إطلاقاً (ق-٣٩).

    لو حرّك خليةً — بخطأ إدخال أو تعديل لاحق — يسقط هذا الاختبار ويسمّيها.
    """
    previous_totals = {
        ("ترابي", 1): 20000, ("ترابي", 2): 26000, ("ترابي", 3): 31000,
        ("مبلط", 1): 18000, ("مبلط", 2): 22000, ("مبلط", 3): 26000,
        ("مقرنص", 1): 34000, ("مقرنص", 2): 36000, ("مقرنص", 3): 37000,
    }
    moved = {
        key: (previous_totals[key], dig + restore)
        for key, (dig, restore) in CIVIL_DETAIL.items()
        if dig + restore != previous_totals[key]
    }
    assert moved == {}, f"خلايا تحرّك إجماليها عن الملف الأصلي: {moved}"


def test_beyond_three_feeders_each_component_grows_by_two_thousand(catalog):
    """ما زاد على 3 مغذيات: **كل مكوّن** +2,000 لكل مغذٍّ، فالمجموع +4,000 (ق-٤٧)."""
    expected = {
        "ترابي": {4: 35000, 5: 39000, 6: 43000, 8: 51000, 10: 59000, 12: 67000},
        "مبلط": {4: 30000, 5: 34000, 6: 38000, 8: 46000, 10: 54000, 12: 62000},
        "مقرنص": {4: 41000, 5: 45000, 6: 49000, 8: 57000, 10: 65000, 12: 73000},
    }
    for sidewalk_value, rows in expected.items():
        sidewalk = next(s for s in SidewalkType if s.value == sidewalk_value)
        for count, total in rows.items():
            parts = civil_tariff_parts(sidewalk, count, catalog)
            assert sum(rate for _name, rate in parts) == total, (sidewalk_value, count)


def test_the_extended_tariff_stays_detailed_into_two_components(catalog):
    """الامتداد يبقى مكوّنين لا إجمالاً — لم يعد في الجدول إجمالٌ غير مفصَّل (ق-٤٧)."""
    for count in (4, 7, 15):
        parts = civil_tariff_parts(SidewalkType.PAVED, count, catalog)
        assert [name for name, _rate in parts] == ["حفر الخندق", "إعادة المسار"]
        # كل مكوّن = قيمته عند 3 + (العدد − 3) × 2,000
        added = (count - 3) * 2000
        assert parts[0][1] == 14000 + added
        assert parts[1][1] == 12000 + added


def test_no_civil_line_is_undetailed_any_more(catalog):
    """حارس: لا يُطبع «إجمالي غير مفصَّل» لأي عدد مغذيات بعد ق-٤٧."""
    for sidewalk in SidewalkType:
        for count in range(1, 21):
            for name, _rate in civil_tariff_parts(sidewalk, count, catalog):
                assert "غير مفصَّل" not in name, (sidewalk, count)


def test_no_feeder_count_is_left_without_a_civil_rate(catalog):
    """حارس الثغرة: كل عدد مغذيات يُنتج تعرفة — لا «بلا أجر» بعد ق-٤٤."""
    for sidewalk in SidewalkType:
        for count in range(1, 21):
            parts = civil_tariff_parts(sidewalk, count, catalog)
            assert all(rate is not None for _name, rate in parts), (sidewalk, count)


def test_the_original_file_totals_are_kept_for_reference(catalog):
    """إجماليات 4 و5 من الملف الأصلي محفوظة للمرجع ولا يستعملها المحرك (ق-٠)."""
    reference = catalog["تعرفة_الأعمال_المدنية"]["مرجع_الملف_الأصلي"]
    assert reference["ترابي"]["4"] == 36000 and reference["ترابي"]["5"] == 39000
    assert reference["مبلط"]["4"] == 30000 and reference["مبلط"]["5"] == 34000
    assert reference["مقرنص"]["4"] == 41000 and reference["مقرنص"]["5"] == 45000


def test_the_formula_reproduces_the_original_file_except_one_cell(catalog):
    """حارس ت-١١: الصيغة تعيد إجماليات الملف الأصلي إلا خليةً واحدة معروفة."""
    reference = catalog["تعرفة_الأعمال_المدنية"]["مرجع_الملف_الأصلي"]
    moved = {}
    for sidewalk in SidewalkType:
        for key, original in reference.get(sidewalk.value, {}).items():
            computed = sum(
                rate for _n, rate in civil_tariff_parts(sidewalk, int(key), catalog)
            )
            if computed != original:
                moved[(sidewalk.value, int(key))] = (original, computed)
    assert moved == {("ترابي", 4): (36000, 35000)}, moved


def test_a_missing_tariff_table_is_reported_not_guessed(catalog):
    """بلا جدول تعرفة أصلاً: يُبلَّغ عنه ولا يُخمَّن رقم (ق-٣٠).

    كانت 6 مغذيات هي الحالة الطبيعية لهذا — وسُدّت في ق-٤٤ بامتداد التعرفة،
    فصار الغياب يُحقَن في **نسخة** من الأسعار كما في ق-٣٦.
    """
    import copy

    stripped = copy.deepcopy(catalog)
    stripped["تعرفة_الأعمال_المدنية"] = {}
    net = Underground11kV(route_length_m=100, feeder_count=6)
    assert civil_works_rate(net, stripped) is None

    result = compute_project(Project(segments=[Segment("م", net)]), stripped)
    assert "الحفر وإعادة المسار — رصيف ترابي، مسار 6 مغذيات" in result["أجور_مفقودة"]


def test_civil_works_cost_is_route_length_times_rate_not_cable_quantity(catalog):
    """المدنية تُحسب من طول المسار — لا من كمية القابلو المضروبة بالمغذيات."""
    net = Underground11kV(route_length_m=400, feeder_count=3, sidewalk_type=SidewalkType.EARTH)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    civil = [l for l in result["أجور_العمل"] if l.group == CIVIL_GROUP]
    assert [l.name for l in civil] == [
        "حفر الخندق — رصيف ترابي، مسار ثلاثي",
        "إعادة المسار — رصيف ترابي، مسار ثلاثي",
    ]
    assert all(l.qty == 400 for l in civil)      # لا 1320 (طول القابلو)
    assert [l.rate for l in civil] == [11000, 20000]
    assert sum(l.cost for l in civil) == 400 * 31000


def test_street_crossings_are_tagged_as_civil_works(catalog):
    """عبور الشوارع ضمن الأعمال المدنية بنصّ المستخدم — لا باب مستقل (ق-٣٨).

    وسعرهما من «أجور_العمل» لا من جدول التعرفة: 100,000 للفرعية و200,000
    للحفر المخفي في الرئيسية.
    """
    project = Project(
        segments=[Segment("م", Underground11kV(route_length_m=100, feeder_count=1))],
        street_crossing_secondary_m=10,
        street_crossing_main_m=5,
    )
    result = compute_project(project, catalog)
    crossings = [
        l for l in result["أجور_العمل"] if l.name.startswith("عبور الشوارع")
    ]
    assert len(crossings) == 2
    assert all(l.group == CIVIL_GROUP for l in crossings)
    assert sum(l.cost for l in crossings) == 10 * 100_000 + 5 * 200_000


# ═══════════════════ عبور الشوارع — تعرفة لمغذٍّ ولمتر (ق-٤٥) ═══════════════════


def test_the_crossing_rate_is_per_feeder_per_metre(catalog):
    """مثال المستخدم حرفياً: رئيسية 10 م × 3 مغذيات × 200,000 = 6,000,000."""
    project = Project(
        segments=[Segment("م", Underground11kV(route_length_m=100, feeder_count=3))],
        street_crossing_main_m=10,
        street_crossing_main_feeders=3,
    )
    result = compute_project(project, catalog)
    line = next(l for l in result["أجور_العمل"] if "الرئيسية" in l.name)
    assert line.qty == 30                       # 10 م × 3 مغذيات
    assert line.cost == 6_000_000
    assert line.source == "شارع 10 م × 3 مغذيات"


def test_one_feeder_keeps_the_old_result(catalog):
    """مغذٍّ واحد: الكلفة كما كانت قبل ق-٤٥ — الإضافة لا تحرّك الحالة القائمة."""
    project = Project(
        segments=[Segment("م", Underground11kV(route_length_m=100, feeder_count=1))],
        street_crossing_secondary_m=30,
    )
    line = next(
        l for l in compute_project(project, catalog)["أجور_العمل"] if "الفرعية" in l.name
    )
    assert line.qty == 30 and line.cost == 3_000_000


def test_the_pipe_count_divides_the_street_length_by_six(catalog):
    """⌈طول الشارع ÷ 6⌉ لكل مغذٍّ — لأن طول الأنبوب 6 م (ق-٤٥، ق-٤٦)."""
    for length, pipes in ((6, 1), (7, 2), (10, 2), (12, 2), (13, 3), (24, 4)):
        assert street_crossing_pipes(length, 1, "عبور")[0].qty == pipes, length


def test_each_feeder_gets_its_own_pipe(catalog):
    """لكل مغذٍّ أنبوبه الخاص — تصحيح المستخدم في ق-٤٦ لِما نُفِّذ في ق-٤٥."""
    def pipes(feeders):
        project = Project(
            segments=[Segment("م", Underground11kV(route_length_m=100, feeder_count=1))],
            street_crossing_secondary_m=12,
            street_crossing_secondary_feeders=feeders,
        )
        result = compute_project(project, catalog)
        return next(m["الكمية"] for m in result["المواد"] if "أنبوب" in m["المادة"])

    assert pipes(1) == 2                        # ⌈12 ÷ 6⌉
    assert pipes(3) == 6                        # × 3 مغذيات
    assert pipes(5) == 10


def test_the_main_street_crossing_has_no_pipes_at_all(catalog):
    """الرئيسية «حفر مخفي» — الأنبوب للفرعية وحدها بنصّ المستخدم (ق-٤٦)."""
    project = Project(
        segments=[Segment("م", Underground11kV(route_length_m=100, feeder_count=1))],
        street_crossing_main_m=30, street_crossing_main_feeders=4,
    )
    result = compute_project(project, catalog)
    assert not any("أنبوب" in m["المادة"] for m in result["المواد"])
    # ومع ذلك أجر العبور محسوب كاملاً
    assert next(l for l in result["أجور_العمل"] if "الرئيسية" in l.name).cost == 24_000_000


def test_only_the_secondary_pipes_are_counted_when_both_exist(catalog):
    """عبوران معاً: الأنبوب من الفرعية وحدها لا من الاثنين."""
    project = Project(
        segments=[Segment("م", Underground11kV(route_length_m=100, feeder_count=1))],
        street_crossing_secondary_m=24, street_crossing_secondary_feeders=2,
        street_crossing_main_m=30, street_crossing_main_feeders=2,
    )
    row = next(
        m for m in compute_project(project, catalog)["المواد"] if "أنبوب" in m["المادة"]
    )
    assert row["الكمية"] == 8                   # ⌈24/6⌉ × 2 — ولا شيء من الرئيسية
    assert len(row["تفصيل"]) == 1
    assert "الفرعية" in row["تفصيل"][0]["المصدر"]


def test_the_pipe_is_quantity_only_like_the_trench_materials(catalog):
    """كلفته ضمن أجر عبور الشوارع الفرعية — كمية بلا كلفة (ق-٤٦)."""
    assert catalog["المواد"]["أنبوب 8 انج 10 بار"]["كمية_فقط"] is True
    project = Project(
        segments=[Segment("م", Underground11kV(route_length_m=100, feeder_count=1))],
        street_crossing_secondary_m=24,
    )
    result = compute_project(project, catalog)
    row = next(m for m in result["المواد"] if "أنبوب" in m["المادة"])
    assert row["الكمية"] == 4 and row["الكلفة"] == 0
    assert not result["أسعار_مفقودة"]           # لا تحذير — لا سعر مفقوداً


def test_no_crossing_means_no_pipes_and_no_labour(catalog):
    project = Project(
        segments=[Segment("م", Underground11kV(route_length_m=100, feeder_count=1))]
    )
    result = compute_project(project, catalog)
    assert not any("أنبوب" in m["المادة"] for m in result["المواد"])
    assert not any("عبور" in l.name for l in result["أجور_العمل"])


def test_a_project_without_underground_has_no_civil_lines(catalog):
    """المشروع الهوائي الخالص لا يُنتج باب أعمال مدنية أصلاً."""
    project = Project(
        segments=[Segment("م", Underground11kV(route_length_m=0, feeder_count=1))]
    )
    result = compute_project(project, catalog)
    assert not [l for l in result["أجور_العمل"] if l.group == CIVIL_GROUP]


# ═══════════════════ الأجور الأخرى ═══════════════════


def test_cable_laying_labour_uses_the_multiplied_cable_quantity(catalog):
    net = Underground11kV(route_length_m=400, feeder_count=3)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    laying = next(l for l in result["أجور_العمل"] if l.name == "كلفة مد قابلو 3×150 ملم²")
    assert laying.qty == 1320               # 400×3×1.1 — لا 400
    assert laying.rate == 3500


def test_end_boxes_share_one_labour_line_like_the_original_file(catalog):
    """صندوق نهاية داخلي وخارجي يجتمعان في بند أجر واحد — كما فعل الملف الأصلي."""
    net = Underground11kV(route_length_m=1, end_boxes_internal=2, end_boxes_external=3)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    boxes = [l for l in result["أجور_العمل"] if l.name == "كلفة نصب صندوق نهاية 3×150 ملم²"]
    assert len(boxes) == 1 and boxes[0].qty == 5


def test_straight_and_end_boxes_are_separate_labour_items(catalog):
    net = Underground11kV(route_length_m=1, straight_boxes=2, end_boxes_internal=1)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    names = {l.name for l in result["أجور_العمل"]}
    assert "كلفة نصب صندوق مستقيم 3×150 ملم²" in names
    assert "كلفة نصب صندوق نهاية 3×150 ملم²" in names


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


def test_every_underground_material_has_a_traceable_source(catalog):
    net = Underground11kV(
        route_length_m=300, feeder_count=2, straight_boxes=1,
        end_boxes_internal=1, end_boxes_external=1,
    )
    for line in materials_underground11(net, catalog):
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
    assert "قابلو 3×150 ملم² جهد 11 ك.ف" in names


def test_every_underground_material_is_priced_or_flagged(catalog):
    prices = catalog["المواد"]
    net = Underground11kV(
        route_length_m=100, feeder_count=1, straight_boxes=1,
        end_boxes_internal=1, end_boxes_external=1,
    )
    for line in materials_underground11(net, catalog):
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
    civil = [l for l in result["أجور_العمل"] if l.group == CIVIL_GROUP]
    assert all(l.qty == 500 for l in civil)      # لا 3300 (كمية القابلو)
    assert [l.rate for l in civil] == [9000, 17000]
    assert sum(l.cost for l in civil) == 500 * 26000


# ─────────────────── المواد ───────────────────


def test_materials_match_the_prices_from_the_original_file(catalog):
    prices = catalog["المواد"]
    assert prices["قابلو 1×400 ملم² جهد 33 ك.ف"]["السعر"] == 85000
    assert prices["صندوق مستقيم 1×400 ملم² جهد 33 ك.ف"]["السعر"] == 285000
    assert prices["صندوق نهاية داخلي 1×400 ملم² جهد 33 ك.ف"]["السعر"] == 136000
    assert prices["صندوق نهاية خارجي 1×400 ملم² جهد 33 ك.ف"]["السعر"] == 157000


def test_end_boxes_are_counted_per_piece_not_per_set(catalog):
    """الوحدة «عدد» لا «سيت» — والسعر سعر الصندوق الواحد (ق-٣٥).

    خلافاً للملف الأصلي الذي كان يسمّيها «سيت» بينما سعره سعر المفرد — فكان
    يحسب ثلث الكلفة الحقيقية.
    """
    prices = catalog["المواد"]
    assert prices["صندوق نهاية داخلي 1×400 ملم² جهد 33 ك.ف"]["الوحدة"] == "عدد"
    assert prices["صندوق نهاية خارجي 1×400 ملم² جهد 33 ك.ف"]["الوحدة"] == "عدد"


def test_one_end_set_generates_three_boxes(catalog):
    """السيت الواحد 3 صناديق — صندوق لكل طور (ق-٣٥)."""
    from engine.underground import BOXES_PER_END_SET_33

    assert BOXES_PER_END_SET_33 == 3
    lines = materials_underground33(Underground33kV(route_length_m=1, end_boxes_internal=1), catalog)
    assert qty(lines, "صندوق نهاية داخلي 1×400 ملم² جهد 33 ك.ف") == 3


def test_end_box_set_cost_is_unchanged_after_the_unit_switch(catalog):
    """التحويل من «سيت» إلى «عدد» **محايد الكلفة** — لا يزيدها ولا ينقصها.

    الكمية ×3 والسعر ÷3 (408,000 ← 136,000 في ورقتك، ق-٣٦)، فكلفة نقطة النهاية
    الواحدة تبقى 408,000 كما كانت. هذا يُصحّح استنتاجاً خاطئاً في ق-٣٥ ادّعى أن
    الكلفة تتضاعف ثلاثة أضعاف.
    """
    net = Underground33kV(route_length_m=1, end_boxes_internal=1)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    row = next(m for m in result["المواد"]
               if m["المادة"] == "صندوق نهاية داخلي 1×400 ملم² جهد 33 ك.ف")
    assert row["الكمية"] == 3
    assert row["سعر الوحدة"] == 136_000          # سعر الصندوق الواحد
    assert row["الكلفة"] == 408_000              # = كلفة السيت الواحد قبل التحويل


def test_eleven_kv_end_boxes_are_not_multiplied(catalog):
    """11 ك.ف كابله ثلاثي القلب فنهايته صندوق واحد — لا ×3 (ق-٣٥)."""
    lines = materials_underground11(
        Underground11kV(route_length_m=1, end_boxes_internal=2, end_boxes_external=3)
    , catalog)
    assert qty(lines, "صندوق نهاية داخلي 3×150 ملم² جهد 11 ك.ف") == 2
    assert qty(lines, "صندوق نهاية خارجي 3×150 ملم² جهد 11 ك.ف") == 3


def test_trench_materials_are_shared_with_11kv_and_use_the_circuit_count(catalog):
    """33 ك.ف: عرض الخندق بعدد الدوائر لا عدد الكابلات — كالأعمال المدنية (ق-٣١).

    فالمقطع المزدوج (دائرتان، ستة كابلات) يوازي مغذيَّين في 11 ك.ف لا ستة.
    """
    net33 = Underground33kV(route_length_m=1000, circuit=CircuitType.DOUBLE)
    lines33 = materials_underground33(net33, catalog)
    for count, same in ((2, True), (6, False)):
        net11 = Underground11kV(route_length_m=1000, feeder_count=count)
        lines11 = materials_underground11(net11, catalog)
        matches = all(
            qty(lines33, name) == qty(lines11, name)
            for name in ("شتايكر 50×50×5 سم", "رمل نهري", "شريط تحذير")
        )
        assert matches is same


def test_end_boxes_manual_no_advisory_33(catalog):
    """صناديق النهاية 33 ك.ف يدوية بحتة — والمُدخَل سيتات تُضرب ×3 (ق-٣٥)."""
    net = Underground33kV(route_length_m=500, end_boxes_internal=3, end_boxes_external=2)
    lines = materials_underground33(net, catalog)
    assert qty(lines, "صندوق نهاية داخلي 1×400 ملم² جهد 33 ك.ف") == 9
    assert qty(lines, "صندوق نهاية خارجي 1×400 ملم² جهد 33 ك.ف") == 6


# ─────────────────── الأجور ───────────────────


def test_cable_laying_labour_uses_the_cable_quantity_33(catalog):
    net = Underground33kV(route_length_m=500, circuit=CircuitType.DOUBLE)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    laying = next(l for l in result["أجور_العمل"] if l.name == "كلفة مد قابلو 1×400 ملم²")
    assert laying.qty == 3300
    assert laying.rate == 2000


def test_end_boxes_share_one_labour_line_33(catalog):
    net = Underground33kV(route_length_m=1, end_boxes_internal=2, end_boxes_external=3)
    result = compute_project(Project(segments=[Segment("م", net)]), catalog)
    boxes = [l for l in result["أجور_العمل"] if l.name == "كلفة نصب صندوق نهاية 1×400 ملم²"]
    assert len(boxes) == 1 and boxes[0].qty == 5
    assert boxes[0].rate == 225000


def test_33kv_and_11kv_labour_rates_are_independent(catalog):
    """أسعار 33 ك.ف مختلفة عن 11 ك.ف — لا مشاركة سعر بالخطأ."""
    rates = catalog["أجور_العمل"]
    assert rates["كلفة مد قابلو 3×150 ملم²"]["السعر"] != rates["كلفة مد قابلو 1×400 ملم²"]["السعر"]
    assert rates["كلفة نصب صندوق نهاية 3×150 ملم²"]["السعر"] != \
        rates["كلفة نصب صندوق نهاية 1×400 ملم²"]["السعر"]


# ─────────────────── التكامل ───────────────────


def test_11kv_and_33kv_underground_segments_coexist(catalog):
    project = Project(segments=[
        Segment("مقطع 11", Underground11kV(route_length_m=300, feeder_count=1)),
        Segment("مقطع 33", Underground33kV(route_length_m=500, circuit=CircuitType.SINGLE)),
    ])
    result = compute_project(project, catalog)
    names = {m["المادة"] for m in result["المواد"]}
    assert "قابلو 3×150 ملم² جهد 11 ك.ف" in names
    assert "قابلو 1×400 ملم² جهد 33 ك.ف" in names


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
    for line in materials_underground33(net, catalog):
        assert line.name in prices, f"مادة بلا صف في نسخة الأسعار: {line.name}"
        assert prices[line.name]["الوحدة"] == line.unit
