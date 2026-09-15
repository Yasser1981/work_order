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
from engine.conversion import pole_increment
from engine.overhead import bracket_need_11
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


@pytest.mark.parametrize("pattern", list(BracketPattern))
@pytest.mark.parametrize("pole", list(PoleType11))
def test_the_panel_hint_and_the_calculation_read_the_same_tables(pattern, pole):
    """`bracket_increment` تشرح و`pole_increment` تحسب — فلا يفترقان.

    فلو اشتُقّ البراكيت من جدولين مختلفين لعرضت اللوحة رقماً وحسب المحرك آخر.
    """
    from engine.overhead import M_BRACKET_12, M_BRACKET_14

    keys = {"1.2": M_BRACKET_12, "1.4": M_BRACKET_14}
    computed = pole_increment(pattern, pole)
    assert {size: computed[key] for size, key in keys.items() if key in computed} == \
        {size: float(n) for size, n in bracket_increment(pattern, pole).items()}


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


@pytest.mark.parametrize("pole", list(PoleType11))
def test_what_does_not_change_with_the_circuit_falls_out_of_the_difference(pole):
    """**وامتناعُها نتيجةُ طرحٍ لا سطرٌ يستثنيها:** العمود والكونكريت والتأريض
    واحدٌ في المفردة والمزدوجة، ففرقُه صفرٌ فيسقط وحده."""
    got = pole_increment(BracketPattern.STANDARD, pole)
    names = {name for name, _ in got}
    assert not (names & {"عمود 11م مشبك", "عمود 11م مدوّر",
                         "كونكريت أساسات الأعمدة", "سلك نحاس 50 ملم²",
                         "ترمنل 50 ملم²"})


def test_the_existing_poles_bring_exactly_the_bracket_difference():
    net = Conversion11kV(existing_lattice=9, existing_round=32)
    got = quantities(net)
    assert got["براكيت جنل 1.4 م مع الملحقات"] == 9 * 4 + 32 * 1
    assert got["براكيت جنل 1.2 م مع الملحقات"] == 32 * 1


def test_the_insulator_increment_is_one_circuit_plus_the_crown_spare(catalog):
    """بنصّ المستخدم (ق-٨٤): **4** دبوسي للمدوّر القائم و**8** قرصي للمشبك القائم.

    الدائرة الإضافية تعطي 3 و6، **ويُزاد عليها بدل التاج** — فالعازل على رأس
    العمود يُنقل مكانه «وقد يُهمل أو يتلف». ومعدات الربط 6 بلا زيادة.
    """
    got = quantities(Conversion11kV(existing_lattice=9, existing_round=32))
    assert got["عازل دبوسي مع السبندل"] == 32 * 4 + 9 * 3
    assert got["عازل قرصي مع الملحقات"] == 9 * 8
    assert got["معدات ربط ألمنيوم – ألمنيوم"] == 9 * 6


def test_the_crown_spare_is_a_replacement_not_a_circuit_need(catalog):
    """**حارس المعنى:** بدل التاج فوق الفرق المشتقّ، لا بدلاً منه.

    فلو كُتب الرقم كاملاً (4 و8) لانقطعت صلته بجدول المحرك، ولو تغيّرت قاعدة
    عوازل الدائرة يوماً لبقي التحويل على رقمه القديم.
    """
    from engine.conversion import CROWN_SPARE
    from engine.overhead import M_DISC_INSULATOR_11, M_PIN_INSULATOR_11

    derived = pole_increment(BracketPattern.STANDARD, PoleType11.ROUND)
    assert derived[M_PIN_INSULATOR_11] == 3          # من المولّد وحده
    assert CROWN_SPARE[PoleType11.ROUND][M_PIN_INSULATOR_11] == 1
    assert CROWN_SPARE[PoleType11.LATTICE][M_DISC_INSULATOR_11] == 2


def test_an_added_pole_gets_no_crown_spare(catalog):
    """العمود المضاف عوازله كلها جديدة — فلا تاج يُنقل ولا بدل له."""
    got = quantities(Conversion11kV(added_round=10))
    assert got["عازل دبوسي مع السبندل"] == 10 * 3 * 2      # دائرتان بلا زيادة


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


def test_the_existing_poles_carry_no_labour_item_at_all(catalog):
    """بنصّ المستخدم (ق-٨٤): «يؤخذ أجر التسليك فقط، وبالتأكيد أجر الأعمدة الإضافية».

    فتركيب البراكيت والعوازل على العمود القائم **لا أجر له أصلاً** — لا بندٌ
    ينتظر تسعيراً. وهذا يُبطل ما كان في ق-٨٣.
    """
    net = Conversion11kV(route_length_m=1000, existing_lattice=9, existing_round=32)
    names = set(rates_of(net, catalog))
    assert names == {"تسليك سلك ألمنيوم 120/20 ملم²"}


def test_converting_existing_poles_alone_raises_no_missing_rate_warning(catalog):
    """**حارس التحذير الذي لا ينطفئ:** بندٌ بلا سعر كان يُبقي تنبيهاً أصفر أبداً،
    ويوهم المدقّق أن في الكشف نقصاً — والنقص غير موجود."""
    result = compute_project(Project("م", [
        Segment("أ", Conversion11kV(existing_lattice=9, existing_round=32))]), catalog)
    assert result["أجور_مفقودة"] == []
    assert result["أجور_العمل"] == []
    assert result["المواد"]                      # والمواد على حالها


def test_the_existing_poles_still_name_themselves_in_the_material_source(catalog):
    """أثرُ العمل القائم لا يضيع بزوال بنده: المصدر يسمّي الأعمدة بعددها ونوعها.

    **في كل سطر**، لا في سطر بدل التاج وحده — فالمدقّق يقرأ خانة المصدر سطراً
    سطراً، والبراكيت الذي لا بدل تاج له يحتاج شرحه كما يحتاجه العازل.
    """
    for pole_kind, label in (("existing_round", "أعمدة مدوّرة قائمة: 32"),
                             ("existing_lattice", "أعمدة مشبكة قائمة: 32")):
        lines = materials_conversion_11(Conversion11kV(**{pole_kind: 32}))
        assert lines, pole_kind
        for line in lines:
            assert label in line.source, f"سطر بلا مصدر: {line.name} — {line.source}"


def test_the_added_poles_installation_is_priced(catalog):
    lines = rates_of(Conversion11kV(added_round=3, added_lattice=1), catalog)
    assert lines["نصب عمود مدور 11م"].qty == 3
    assert lines["نصب عمود مشبك 11م"].qty == 1


# ═════════ ٦. المقطع داخل مشروع كامل ═════════


def test_an_empty_conversion_segment_produces_nothing(catalog):
    result = compute_project(
        Project("م", [Segment("أ", Conversion11kV())]), catalog)
    assert result["المواد"] == [] and result["أجور_العمل"] == []


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
