# -*- coding: utf-8 -*-
"""اختبارات التجهيزات على الأعمدة — المحولة والفواصل والقفيص (ق-٢٣).

الأرقام المرجعية مأخوذة من `RAW_تفصيلي` في الملف الأصلي:
المحولة الصفوف 5–19، الفاصل ON-LOAD 43–47، وعلى رأس القابلو 48–57،
والفاصل الهوائي 33 ك.ف 85–92.
"""

import pytest

from engine import load_catalog
from engine.equipment import (
    AIR_ISOLATOR_33_KIT,
    ONLOAD_CABLE_HEAD_KIT,
    ONLOAD_KIT,
    TRANSFORMER_KIT,
    labour_equipment,
    materials_equipment,
)
from engine.overhead import aggregate, compute
from engine.types import Equipment, OverheadProject


@pytest.fixture
def catalog():
    return load_catalog()


def qty(lines, name):
    return sum(l.qty for l in lines if l.name == name)


# ═══════════════════ المحولة ═══════════════════


def test_transformer_kit_matches_the_original_file():
    """15 مادة بالكميات نفسها التي يولّدها الملف الأصلي لمحولة واحدة."""
    lines = materials_equipment(Equipment(transformers=1))
    expected = {
        "محولة 400 KVA": 1,
        "قاطع دورة 400 أمبير مع المتسعة": 2,
        "قاعدة محولة 2.4 متر": 1,
        "لنك فيوز 15 KV مع سلك فيوز 40 أمبير": 1,
        "قاعدة لنك فيوز 2.4 متر": 1,
        "قضيب تأريض 1.5 متر مع القفيص": 3,
        "سلك نحاس 50 ملم2": 15,
        "قابلو نحاس 1×50 ملم²": 25,
        "قابلو نحاس 1×150 ملم²": 80,
        "مانعة صواعق 11 KV": 1,
        "قاعدة مانعة صواعق مع الملحقات": 1,
        "معدات ربط ألمنيوم – نحاس": 15,
        "ترمنل 50 ملم²": 15,
        "ترمنل 150 ملم²": 30,
        "جهاز إنارة": 2,
    }
    assert len(lines) == len(expected) == len(TRANSFORMER_KIT)
    assert {l.name: l.qty for l in lines} == expected


def test_transformer_quantities_scale_linearly():
    lines = materials_equipment(Equipment(transformers=3))
    assert qty(lines, "محولة 400 KVA") == 3
    assert qty(lines, "قابلو نحاس 1×150 ملم²") == 240
    assert qty(lines, "ترمنل 150 ملم²") == 90


def test_transformer_accessories_have_no_separate_labour(catalog):
    """أجر واحد للمحولة يشمل ملحقاتها كلها — لا بند مستقل لأي ملحق."""
    labour = labour_equipment(Equipment(transformers=2), catalog["أجور_العمل"])
    assert [l.name for l in labour] == ["نصب المحولة"]
    assert labour[0].qty == 2
    assert labour[0].cost == 700_000


# ═══════════════════ الفاصل ON-LOAD ═══════════════════


def test_onload_kit_matches_the_original_file():
    lines = materials_equipment(Equipment(onload=1))
    assert {l.name: l.qty for l in lines} == {
        "فاصل ON-LOAD": 1,
        "قابلو نحاس 1×150 ملم²": 20,
        "معدات ربط ألمنيوم – نحاس": 6,
        "ترمنل 150 ملم²": 6,
    }


def test_onload_on_cable_head_adds_protection_and_earthing():
    """على رأس القابلو: الفاصل نفسه زائد مانعة صواعق وتأريضاً كاملين."""
    lines = materials_equipment(Equipment(onload_cable_head=1))
    assert {l.name: l.qty for l in lines} == {
        "فاصل ON-LOAD": 1,
        "قابلو نحاس 1×150 ملم²": 20,
        "معدات ربط ألمنيوم – نحاس": 6,
        "ترمنل 150 ملم²": 6,
        "مانعة صواعق 11 KV": 1,
        "قاعدة مانعة صواعق مع الملحقات": 1,
        "قضيب تأريض 1.5 متر مع القفيص": 1,
        "قابلو نحاس 1×50 ملم²": 15,
        "ترمنل 50 ملم²": 1,
    }


def test_bracket_21_is_gone_from_both_isolator_kits():
    """ق-١٩: براكيت 2.1 متر ملغى تماماً — لا في المواد ولا في الأجور."""
    kits = ONLOAD_KIT + ONLOAD_CABLE_HEAD_KIT + AIR_ISOLATOR_33_KIT + TRANSFORMER_KIT
    assert not any("2.1" in name for (name, _unit), _per in kits)

    lines = materials_equipment(Equipment(onload=5, onload_cable_head=5))
    assert not any("2.1" in l.name for l in lines)


def test_both_isolator_kinds_share_one_priced_material_and_one_labour_item(catalog):
    """النوعان مادة واحدة مسعّرة وبند أجر واحد — لكن بمصدرين متمايزين للتتبّع."""
    eq = Equipment(onload=2, onload_cable_head=3)
    lines = materials_equipment(eq)
    assert qty(lines, "فاصل ON-LOAD") == 5

    sources = [l.source for l in lines if l.name == "فاصل ON-LOAD"]
    assert sources == ["فاصل ON-LOAD: 2 × 1", "فاصل ON-LOAD على رأس القابلو: 3 × 1"]

    labour = labour_equipment(eq, catalog["أجور_العمل"])
    assert [(l.name, l.qty) for l in labour] == [("نصب الفاصل ON-LOAD", 5)]


# ═══════════════════ الفاصل الهوائي 33 ك.ف ═══════════════════


def test_air_isolator_33_kit_matches_the_original_file():
    lines = materials_equipment(Equipment(air_isolator_33=1))
    assert {l.name: l.qty for l in lines} == {
        "فاصل هوائي 33 ك.ف": 1,
        "مانعة صواعق 33 ك.ف": 1,
        "قاعدة مانعة صواعق مع الملحقات": 1,
        "قضيب تأريض 1.5 متر مع القفيص": 1,
        "قابلو 1×185 ملم2": 20,
        "ترمنل 185 ملم2": 6,
        "قابلو نحاس 1×50 ملم²": 15,
        "ترمنل 50 ملم²": 1,
    }


def test_air_isolator_33_has_its_own_labour_item(catalog):
    labour = labour_equipment(Equipment(air_isolator_33=2), catalog["أجور_العمل"])
    assert [(l.name, l.qty, l.cost) for l in labour] == [
        ("نصب فاصل هوائي 33 ك.ف", 2, 180_000)
    ]


# ═══════════════════ قفيص العمود المشبك ═══════════════════


def test_lattice_cage_is_quantity_only_with_no_kit_and_no_labour(catalog):
    eq = Equipment(lattice_cages=7)
    lines = materials_equipment(eq)
    assert {l.name: l.qty for l in lines} == {"قفيص عمود مشبك": 7}
    assert labour_equipment(eq, catalog["أجور_العمل"]) == []


# ═══════════════════ التكامل مع المشروع ═══════════════════


def test_empty_equipment_generates_nothing(catalog):
    assert materials_equipment(Equipment()) == []
    assert labour_equipment(Equipment(), catalog["أجور_العمل"]) == []
    assert not Equipment()
    assert Equipment(lattice_cages=1)


def test_project_defaults_to_no_equipment(catalog):
    """المشروع بلا تجهيزات ما لم تُدخَل صراحةً — لا محولة تسلّلت إلى التخمين."""
    result = compute(OverheadProject(), catalog)
    assert result["المواد"] == []
    assert result["الكلفة_الكلية"] == 0


def test_equipment_merges_into_project_totals(catalog):
    """المادة المشتركة تُجمَّع من كل مصادرها ويبقى تفصيلها ظاهراً."""
    from engine.types import Network11kV

    project = OverheadProject(
        net11=Network11kV(route_length_m=500, poles_lattice=5, poles_round=20),
        equipment=Equipment(transformers=1),
    )
    result = compute(project, catalog)
    earth = next(m for m in result["المواد"] if m["المادة"] == "سلك نحاس 50 ملم2")

    # 25 عموداً × 1.5 م = 37.5 من الأعمدة، و15 م من المحولة
    assert earth["الكمية"] == 52.5
    assert earth["مجمَّع"] is True
    assert len(earth["تفصيل"]) == 2


def test_every_equipment_material_has_an_entry_in_the_catalog(catalog):
    """حارس: كل مادة يولّدها المحرك لها صف في نسخة الأسعار — بسعر أو بتنبيه."""
    eq = Equipment(
        transformers=1, onload=1, onload_cable_head=1, air_isolator_33=1, lattice_cages=1
    )
    prices = catalog["المواد"]
    for (name, unit), _qty in aggregate(materials_equipment(eq)).items():
        assert name in prices, f"مادة بلا صف في نسخة الأسعار: {name}"
        assert prices[name]["الوحدة"] == unit, f"وحدة مختلفة: {name}"


def test_pending_prices_are_reported_not_silently_zeroed(catalog):
    """جهاز الإنارة وترمنل 185 بلا سعر — يُبلَّغ عنهما ولا يمرّان بصفر صامت."""
    result = compute(
        OverheadProject(equipment=Equipment(transformers=1, air_isolator_33=1)), catalog
    )
    assert "جهاز إنارة" in result["أسعار_مفقودة"]
    assert "ترمنل 185 ملم2" in result["أسعار_مفقودة"]


def test_transformer_cost_is_the_heaviest_single_line(catalog):
    """المحولة وحدها 17 مليوناً — رقم يستحق أن يُثبَّت باختبار."""
    result = compute(OverheadProject(equipment=Equipment(transformers=1)), catalog)
    transformer = next(m for m in result["المواد"] if m["المادة"] == "محولة 400 KVA")
    assert transformer["الكلفة"] == 17_000_000
    assert result["كلفة_المواد"] == 23_639_000
    assert result["كلفة_العمل"] == 350_000
