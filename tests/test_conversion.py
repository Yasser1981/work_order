# -*- coding: utf-8 -*-
"""مقطع تحويل شبكة 11 ك.ف من مفردة إلى مزدوجة (ق-٨٣).

**الحارس الجوهري:** أن الفرق **مشتقٌّ من جداول المحرك** لا مكتوبٌ هنا. فلو
غُيّرت قاعدة براكيت يوماً في `overhead` تبعها التحويل تلقائياً — ولو كُتب الرقم
في مكانين لافترقا بلا أن ينبّه شيء.
"""

import pytest

from engine import load_catalog
from engine.conversion import (
    bracket_increment,
    labour_conversion_11,
    materials_conversion_11,
)
from engine.overhead import (
    CONVERSION_LATTICE_RATE,
    CONVERSION_ROUND_RATE,
    bracket_need_11,
)
from engine.project import compute_project
from engine.types import (
    BracketPattern,
    CircuitType,
    Conversion11kV,
    PoleType11,
    Project,
    Segment,
    SupplyForm,
)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def quantities(net: Conversion11kV) -> dict:
    from engine.project import aggregate

    return {name: qty for (name, _), qty in aggregate(materials_conversion_11(net)).items()}


def rates_of(net: Conversion11kV, catalog) -> dict:
    return {line.name: line for line in labour_conversion_11(net, catalog["أجور_العمل"])}


# ═════════ ١. الفرق مشتقٌّ من الجداول، لا مكتوبٌ هنا ═════════


@pytest.mark.parametrize("pattern", list(BracketPattern))
@pytest.mark.parametrize("pole", list(PoleType11))
def test_the_increment_is_exactly_double_minus_single(pattern, pole):
    """**الحارس الأهمّ:** الفرق = المزدوجة ناقص المفردة، بحساب مستقلّ عن الشيفرة."""
    single = bracket_need_11(CircuitType.SINGLE, pattern, pole)
    double = bracket_need_11(CircuitType.DOUBLE, pattern, pole)
    expected = {size: double.get(size, 0) - single.get(size, 0)
                for size in set(single) | set(double)}
    expected = {size: n for size, n in expected.items() if n > 0}
    assert bracket_increment(pattern, pole) == expected


@pytest.mark.parametrize("pattern,pole,total", [
    (BracketPattern.STANDARD, PoleType11.ROUND, 2),
    (BracketPattern.ALTERNATIVE, PoleType11.ROUND, 2),
    (BracketPattern.STANDARD, PoleType11.LATTICE, 4),
    (BracketPattern.ALTERNATIVE, PoleType11.LATTICE, 4),
])
def test_the_numbers_the_user_confirmed(pattern, pole, total):
    """صدّقها المستخدم نصّاً: المدوّر 2 في النمطين، **والمشبك 4 لا 2**."""
    assert sum(bracket_increment(pattern, pole).values()) == total


def test_the_round_pole_needs_two_different_sizes_in_the_standard_pattern():
    """«2 لكل عمود» في القياسي ليسا من مقاسٍ واحد — 1.2 و1.4."""
    assert bracket_increment(BracketPattern.STANDARD, PoleType11.ROUND) == \
        {"1.2": 1, "1.4": 1}
    assert bracket_increment(BracketPattern.ALTERNATIVE, PoleType11.ROUND) == {"1.2": 2}


# ═════════ ٢. الأعمدة القائمة: فرقٌ فقط، لا عمود ولا كونكريت ولا تأريض ═════════


def test_existing_poles_bring_no_pole_no_concrete_and_no_earthing():
    """**جوهر المقطع:** الشبكة قائمة على الأرض — أعمدتها منصوبة ومؤرَّضة.

    ولو أُضيفت لها أعمدةٌ أو كونكريت لتضاعفت كلفة المشروع بلا أن يُنصب عمود.
    """
    got = quantities(Conversion11kV(route_length_m=1000, existing_lattice=9,
                                    existing_round=32))
    for name in ("عمود 11م مشبك", "عمود 11م مدوّر", "كونكريت أساسات الأعمدة",
                 "سلك نحاس 50 ملم²", "ترمنل 50 ملم²"):
        assert name not in got, name


def test_the_existing_poles_bring_exactly_the_bracket_difference():
    net = Conversion11kV(existing_lattice=9, existing_round=32)
    got = quantities(net)
    assert got["براكيت جنل 1.4 م مع الملحقات"] == 9 * 4 + 32 * 1
    assert got["براكيت جنل 1.2 م مع الملحقات"] == 32 * 1


def test_the_insulator_increment_is_one_more_circuit(catalog):
    """+3 دبوسي لكل عمود، و+6 قرصي و+6 معدات ربط لكل مشبك — دائرة واحدة إضافية."""
    got = quantities(Conversion11kV(existing_lattice=9, existing_round=32))
    assert got["عازل دبوسي مع السبندل"] == (9 + 32) * 3
    assert got["عازل قرصي مع الملحقات"] == 9 * 6
    assert got["معدات ربط ألمنيوم – ألمنيوم"] == 9 * 6


def test_a_round_only_route_brings_no_disc_insulators():
    """القرصي للشدّ وهو على المشبك وحده — فلا يظهر بلا أعمدة مشبكة."""
    got = quantities(Conversion11kV(existing_round=20))
    assert "عازل قرصي مع الملحقات" not in got


# ═════════ ٣. السلك: دائرة واحدة لا اثنتان ═════════


@pytest.mark.parametrize("route,waste,expected", [
    (1000, 0.10, 3300),
    (1000, 0.0, 3000),
    (500, 0.10, 1650),
])
def test_the_new_circuit_is_one_circuit_of_three_phases(route, waste, expected):
    got = quantities(Conversion11kV(route_length_m=route, waste_pct=waste))
    assert got["سلك ألمنيوم 120/20 ملم²"] == expected


def test_a_length_that_already_includes_the_waste_is_not_inflated_twice():
    got = quantities(Conversion11kV(route_length_m=1000, length_includes_waste=True))
    assert got["سلك ألمنيوم 120/20 ملم²"] == 3000


# ═════════ ٤. أعمدة الإسناد: حاجة عمود مزدوج كاملة ═════════


def test_an_added_pole_carries_a_full_double_circuit_set():
    """العمود الجديد يحمل الدائرتين — فليس تحويلاً بل عمود شبكة مزدوجة."""
    got = quantities(Conversion11kV(added_round=3))
    assert got["عمود 11م مدوّر"] == 3
    assert got["براكيت جنل 1.2 م مع الملحقات"] == 3 * 2      # الحاجة الكاملة
    assert got["براكيت جنل 1.4 م مع الملحقات"] == 3 * 1
    assert got["عازل دبوسي مع السبندل"] == 3 * 3 * 2          # دائرتان
    assert got["سلك نحاس 50 ملم²"] == 3 * 1.5
    assert got["ترمنل 50 ملم²"] == 3
    assert got["كونكريت أساسات الأعمدة"] == 3                 # 3 × 0.756 ← لأعلى


def test_an_added_lattice_pole_brings_its_disc_insulators_too():
    got = quantities(Conversion11kV(added_lattice=2))
    assert got["عازل قرصي مع الملحقات"] == 2 * 6 * 2
    assert got["براكيت جنل 1.4 م مع الملحقات"] == 2 * 6


def test_an_added_pole_supplied_with_accessories_drops_one_bracket():
    """قاعدة ق-٦٠ تسري على المضاف كما تسري على أي عمود جديد."""
    bare = quantities(Conversion11kV(added_lattice=4))
    kitted = quantities(Conversion11kV(
        added_lattice=4, added_lattice_supply=SupplyForm.WITH_ACCESSORIES))
    assert kitted["براكيت جنل 1.4 م مع الملحقات"] == bare["براكيت جنل 1.4 م مع الملحقات"] - 4
    assert "عمود 11م مشبك مع الملحقات" in kitted


def test_the_added_poles_and_the_existing_ones_add_up_together():
    """المصدران يجتمعان في سطر واحد — ولا يُسقط أحدهما الآخر."""
    both = quantities(Conversion11kV(existing_round=10, added_round=2))
    assert both["براكيت جنل 1.2 م مع الملحقات"] == 10 * 1 + 2 * 2


# ═════════ ٥. الأجور: التسليك مُسعَّر، والتحويل بلا سعر بعد ═════════


def test_the_stringing_is_priced_and_follows_the_new_wire(catalog):
    net = Conversion11kV(route_length_m=1000)
    line = rates_of(net, catalog)["تسليك سلك ألمنيوم 120/20 ملم²"]
    assert line.qty == 3300 and not line.rate_missing
    assert line.driver == ("سلك ألمنيوم 120/20 ملم²", "متر")     # ق-٨١


def test_the_conversion_labour_is_reported_without_a_rate(catalog):
    """بنصّ المستخدم «اتركه فارغاً بدون أجور» — فيظهر البند ولا يُحتسب صفراً (ق-٩)."""
    net = Conversion11kV(existing_lattice=9, existing_round=32)
    lines = rates_of(net, catalog)

    for name, count in ((CONVERSION_LATTICE_RATE, 9), (CONVERSION_ROUND_RATE, 32)):
        line = lines[name]
        assert line.qty == count
        assert line.rate_missing is True
        assert line.cost == 0


def test_the_two_conversion_items_are_separate_because_the_work_differs(catalog):
    """المشبك 4 براكيت و6 عوازل قرصية، والمدوّر براكيتان — فسعرٌ واحد يخفي فرقاً."""
    assert CONVERSION_LATTICE_RATE != CONVERSION_ROUND_RATE
    lines = rates_of(Conversion11kV(existing_lattice=1, existing_round=1), catalog)
    assert CONVERSION_LATTICE_RATE in lines and CONVERSION_ROUND_RATE in lines


def test_an_old_price_catalog_that_never_heard_of_these_items_still_works(catalog):
    """**حارس انهيار:** نسخة أسعار قديمة لا تعرف البندين — ولا ينهار الحساب.

    وهي الحالة الواقعية: نسخة آب على حاسبة المستخدم لا تحوي البندين، فلو
    قُرئ سعرهما بالفهرسة لسقط الحساب بـ KeyError عند أول مقطع تحويل.
    """
    rates = {k: v for k, v in catalog["أجور_العمل"].items()
             if k not in (CONVERSION_LATTICE_RATE, CONVERSION_ROUND_RATE)}
    lines = labour_conversion_11(Conversion11kV(existing_round=5), rates)
    assert any(line.name == CONVERSION_ROUND_RATE and line.rate_missing
               for line in lines)


def test_the_added_poles_installation_is_priced(catalog):
    lines = rates_of(Conversion11kV(added_round=3, added_lattice=1), catalog)
    assert lines["نصب عمود مدور 11م"].qty == 3
    assert lines["نصب عمود مشبك 11م"].qty == 1


# ═════════ ٦. المقطع داخل مشروع كامل ═════════


def test_an_empty_conversion_segment_produces_nothing(catalog):
    result = compute_project(
        Project("م", [Segment("أ", Conversion11kV())]), catalog)
    assert result["المواد"] == [] and result["أجور_العمل"] == []


def test_the_unpriced_items_are_named_in_the_warning(catalog):
    result = compute_project(
        Project("م", [Segment("أ", Conversion11kV(existing_round=10))]), catalog)
    assert CONVERSION_ROUND_RATE in result["أجور_مفقودة"]
    assert result["كلفة_العمل"] == 0        # لا يُحتسب صفراً بصمت بل يُبلَّغ


def test_a_conversion_merges_with_a_normal_segment_in_one_table(catalog):
    """مقطعا تحويلٍ وشبكةٍ في مشروع واحد: البراكيت سطرٌ واحد مجموع."""
    from engine.types import Network11kV

    result = compute_project(Project("م", [
        Segment("تحويل", Conversion11kV(existing_round=10)),
        Segment("جديدة", Network11kV(route_length_m=500, poles_round=4)),
    ]), catalog)
    rows = [row for row in result["المواد"] if row["المادة"].startswith("براكيت جنل 1.2")]
    assert len(rows) == 1
    assert rows[0]["الكمية"] == 10 * 1 + 4 * 1
    assert rows[0]["مجمَّع"] is True
