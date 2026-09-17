# -*- coding: utf-8 -*-
"""عبور الشوارع داخل المقاطع الأرضية (ق-٨٧).

**الحارس الجوهري:** أن تقريب الأنبوب يقع على **الشارع الواحد** لا على مجموع
الشوارع. فخمسة شوارع بعشرة أمتار ليست شارعاً بخمسين: الأنبوب يُقطع لكل شارع
على حدة، والباقي هدرٌ لا يُنقل إلى الشارع التالي.
"""

import math

import pytest

from engine import load_catalog
from engine.project import compute_project
from engine.types import (
    CrossingKind,
    Project,
    Segment,
    StreetCrossing,
    Underground11kV,
    Underground33kV,
)
from engine.underground import (
    PIPE_LENGTH_M,
    SPARE_PIPES_PER_STREET,
    crossing_pipes,
    crossings_labour,
)

MAIN, SEC = CrossingKind.MAIN, CrossingKind.SECONDARY


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def crossing_lines(project, catalog, word="عبور"):
    return [l for l in compute_project(project, catalog)["أجور_العمل"] if word in l.name]


def pipes_of(project, catalog):
    rows = [r for r in compute_project(project, catalog)["المواد"] if "أنبوب" in r["المادة"]]
    return rows[0]["الكمية"] if rows else 0


def ug(*crossings, length=500, feeders=1):
    return Underground11kV(route_length_m=length, feeder_count=feeders,
                           crossings=list(crossings))


# ═════════ ١. التقريب على الشارع الواحد — جوهر ق-٨٧ ═════════


@pytest.mark.parametrize("count,length,expected", [
    (5, 10, 5 * (2 + 1)),        # ⌈10÷6⌉ = 2، والمجموع لو جُمع: ⌈50÷6⌉ = 9
    (2, 7, 2 * (2 + 1)),
    (3, 6, 3 * (1 + 1)),         # 6 م بالضبط = روطة واحدة، بلا هدر
    (1, 50, 1 * (9 + 1)),
])
def test_the_pipe_ceiling_falls_on_one_street_not_on_their_sum(count, length, expected):
    assert crossing_pipes(StreetCrossing(SEC, count, length, 1))[0].qty == expected


def test_splitting_a_street_never_costs_fewer_pipes_than_lumping_it():
    """**حارس الاتجاه:** التقسيم لا ينقص الأنابيب أبداً — إمّا يساوي أو يزيد.

    فلو انعكس الاتجاه يوماً لكان التقريب قد وقع في الموضع الخطأ ثانيةً.
    """
    for count in range(1, 12):
        for length in (5, 6, 7, 10, 13, 24, 31):
            split = crossing_pipes(StreetCrossing(SEC, count, length, 1))[0].qty
            lumped = math.ceil(count * length / PIPE_LENGTH_M) + SPARE_PIPES_PER_STREET
            assert split >= lumped, (count, length, split, lumped)


def test_the_five_street_case_the_user_gave():
    """مثال المستخدم: 5 شوارع × 10 م × مغذٍّ واحد."""
    assert crossing_pipes(StreetCrossing(SEC, 5, 10, 1))[0].qty == 15


# ═════════ ٢. الاحتياط: لكل شارع، لا للعبور كلّه ولا لكل مغذٍّ ═════════


def test_one_spare_pipe_per_street():
    """بنصّ المستخدم (ق-٨٧): «أنبوب احتياط لكل شارع … مستقبلاً قد يُستغلّ».

    **وهذا يعدّل ق-٤٨** الذي كان «واحداً للعبور كلّه».
    """
    bare = crossing_pipes(StreetCrossing(SEC, 1, 12, 1))[0].qty
    for count in (2, 5, 10):
        got = crossing_pipes(StreetCrossing(SEC, count, 12, 1))[0].qty
        assert got == count * bare, count


def test_the_spare_does_not_multiply_by_feeders():
    """الاحتياط للشارع لا للمغذّي — فثمانية مغذيات لا تعطي ثمانية احتياطات."""
    for feeders in (1, 3, 8):
        got = crossing_pipes(StreetCrossing(SEC, 1, 12, feeders))[0].qty
        assert got == 2 * feeders + 1, feeders


# ═════════ ٣. الرئيسي بلا أنبوب، والفرعي به ═════════


def test_a_main_crossing_brings_no_pipe_at_all():
    """حفرٌ مخفيّ — بلا أنبوب (ق-٤٦)، مهما كثرت شوارعه."""
    assert crossing_pipes(StreetCrossing(MAIN, 10, 50, 5)) == []


def test_a_main_crossing_is_still_priced(catalog):
    lines = crossings_labour([StreetCrossing(MAIN, 2, 30, 2)], catalog["أجور_العمل"])
    assert lines[0].qty == 2 * 30 * 2
    assert lines[0].name == "عبور الشوارع الرئيسية – حفر مخفي"


# ═════════ ٤. الأجر: التعرفة لمترٍ ولمغذٍّ، مضروبةً بعدد الشوارع ═════════


def test_the_labour_multiplies_all_three(catalog):
    line = crossings_labour([StreetCrossing(SEC, 5, 10, 3)], catalog["أجور_العمل"])[0]
    assert line.qty == 5 * 10 * 3


def test_an_empty_crossing_produces_nothing(catalog):
    for empty in (StreetCrossing(SEC, 5, 0, 3), StreetCrossing(SEC, 0, 10, 3),
                  StreetCrossing(SEC, 5, 10, 0)):
        assert crossings_labour([empty], catalog["أجور_العمل"]) == []
        assert crossing_pipes(empty) == []


# ═════════ ٥. مثال المستخدم كاملاً داخل مشروع ═════════


def test_the_users_three_segment_example(catalog):
    """**الحالة التي عجز عنها النموذج القديم:** أعداد مغذيات مختلفة بين المقاطع.

    (2×30×2) + (1×50×3) = 270 م×مغذٍّ — ولا يمكن بلوغها بطولٍ واحد وعددٍ واحد،
    إذ تلزم 270/110 = 2.45 مغذٍّ.
    """
    project = Project("مثال", [
        Segment("الأول", ug(StreetCrossing(MAIN, 2, 30, 2))),
        Segment("الثاني", ug(StreetCrossing(MAIN, 1, 50, 3))),
        Segment("الثالث", ug(StreetCrossing(SEC, 5, 10, 1))),
    ])
    main = [l for l in crossing_lines(project, catalog) if "رئيسية" in l.name][0]
    sec = [l for l in crossing_lines(project, catalog) if "الفرعية" in l.name][0]
    assert main.qty == 270 and main.cost == 54_000_000
    assert sec.qty == 50 and sec.cost == 5_000_000
    assert pipes_of(project, catalog) == 15


def test_crossings_from_several_segments_merge_into_one_line(catalog):
    """«ويقوم البرنامج بحساب الإجمالي» — سطرٌ واحد لا سطرٌ لكل مقطع."""
    project = Project("م", [
        Segment("أ", ug(StreetCrossing(SEC, 2, 10, 1))),
        Segment("ب", ug(StreetCrossing(SEC, 3, 10, 1))),
    ])
    lines = crossing_lines(project, catalog)
    assert len(lines) == 1 and lines[0].qty == 50
    assert pipes_of(project, catalog) == 2 * 3 + 3 * 3
    assert "أ ←" in lines[0].source and "ب ←" in lines[0].source


def test_the_crossing_labour_is_tagged_as_civil_work(catalog):
    """ضمن الأعمال المدنية (ق-٣٨) — فلا يخرج من وسمه بتغيّر موضعه."""
    from engine.underground import CIVIL_GROUP

    project = Project("م", [Segment("أ", ug(StreetCrossing(SEC, 1, 10, 1)))])
    assert crossing_lines(project, catalog)[0].group == CIVIL_GROUP


def test_the_33kv_segment_carries_crossings_too(catalog):
    project = Project("م", [Segment("أ", Underground33kV(
        route_length_m=300, crossings=[StreetCrossing(SEC, 4, 10, 1)]))])
    assert crossing_lines(project, catalog)[0].qty == 40
    assert pipes_of(project, catalog) == 4 * 3


# ═════════ ٦. أوامر العمل القديمة لا تتغيّر — بشرط المستخدم ═════════


def test_a_project_level_crossing_computes_exactly_as_before(catalog):
    """**الشرط الذي وضعه المستخدم:** «أوامر العمل القديمة لا تتغيّر».

    والحقول القديمة تمرّ بالصيغة الجديدة نفسها بـ`count=1`، فتعطي ما كانت
    تعطيه: ⌈الطول÷6⌉ × المغذيات + احتياط واحد.
    """
    project = Project("قديم", [Segment("أ", ug(length=500))],
                      street_crossing_secondary_m=30,
                      street_crossing_secondary_feeders=2)
    assert crossing_lines(project, catalog)[0].qty == 60
    assert pipes_of(project, catalog) == math.ceil(30 / PIPE_LENGTH_M) * 2 + 1


def test_the_old_and_the_new_paths_agree_on_a_single_street(catalog):
    """**حارس عدم الافتراق:** الطريقان صيغةٌ واحدة، فلا يفترقان أبداً.

    ولو نُسخت الصيغة يوماً بدل أن تُستدعى، لسقط هذا الحارس.
    """
    for length in (7, 12, 30, 50):
        for feeders in (1, 2, 5):
            old = Project("قديم", [Segment("أ", ug())],
                          street_crossing_secondary_m=length,
                          street_crossing_secondary_feeders=feeders)
            new = Project("جديد", [Segment("أ", ug(StreetCrossing(SEC, 1, length, feeders)))])
            assert pipes_of(old, catalog) == pipes_of(new, catalog), (length, feeders)
            assert crossing_lines(old, catalog)[0].qty == \
                crossing_lines(new, catalog)[0].qty


def test_the_two_paths_add_up_when_both_are_present(catalog):
    """ولو اجتمعا في مشروعٍ واحد جُمعا ولم يُسقط أحدهما الآخر."""
    project = Project("مختلط", [Segment("أ", ug(StreetCrossing(SEC, 2, 10, 1)))],
                      street_crossing_secondary_m=10,
                      street_crossing_secondary_feeders=1)
    assert crossing_lines(project, catalog)[0].qty == 2 * 10 + 10


# ═════════ ٧. الحقل على المقاطع الأرضية وحدها ═════════


def test_only_underground_segments_can_carry_crossings():
    """بنصّ المستخدم: «المقاطع الأرضية فقط مشمولة بهذا الأمر».

    **والحالة الممتنعة لا تُمثَّل**: الحقل غير موجودٍ أصلاً في المقاطع الأخرى،
    فلا يحتاج حارساً يرفضه في وقت التشغيل.
    """
    from engine.types import Conversion11kV, Network11kV, Network33kV, NetworkLV
    from engine.equipment import Equipment

    for kind in (Network11kV, Network33kV, NetworkLV, Equipment, Conversion11kV):
        assert not hasattr(kind(), "crossings"), kind.__name__
    for kind in (Underground11kV, Underground33kV):
        assert kind().crossings == []
