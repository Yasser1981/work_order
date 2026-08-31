# -*- coding: utf-8 -*-
"""اختبارات إدارة الأسعار وإصدار النسخ (ق-٦٢).

**الحارس الأهمّ هنا:** أن نسخة أسعار محفوظة **لا تُعدَّل أبداً**. فلو كُتب فوقها
لتغيّرت كلفة كل أمر عمل قديم يشير إليها **بلا أن ينبّه أحد** — وهو نقض صريح
لما اشترطه المستخدم: «مع احتفاظ أوامر العمل القديمة بنفس سعر المواد والعمل في
تاريخ إنشائها».
"""

import json

from datetime import date

import pytest

from engine import load_catalog
from engine.prices import (
    DERIVED,
    LABOUR,
    MATERIALS,
    PRICE,
    apply_edits,
    differences,
    editable_rows,
    next_version,
    save_as_new_version,
    strip_derived,
)


@pytest.fixture
def catalog():
    return load_catalog()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """مجلد بيانات مؤقّت — فلا يمسّ أي اختبار نسخة الأسعار الحقيقية."""
    import engine.paths as paths
    import engine.prices as prices

    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "bundled_data_dir", lambda: tmp_path)
    monkeypatch.setattr(prices, "catalog_path", lambda v: tmp_path / f"catalog_{v}.json")
    return tmp_path


# ════════════════════ ١. النسخة المحفوظة لا تُمسّ ════════════════════


def test_writing_over_an_existing_version_is_refused(isolated):
    """القاعدة الحاكمة: لا تُكتَب نسخة فوق نسخة."""
    save_as_new_version({MATERIALS: {}, LABOUR: {}}, "2026-08")
    with pytest.raises(FileExistsError, match="ولا تُكتَب نسخة فوق نسخة"):
        save_as_new_version({MATERIALS: {}, LABOUR: {}}, "2026-08")


def test_a_new_version_never_collides_with_an_existing_one():
    """نسخة اليوم مأخوذة ← يُضاف حرف، والترتيب الأبجدي يبقى زمنياً."""
    today = date(2026, 8, 31)
    assert next_version(today, existing=["2026-08"]) == "2026-08-31"
    assert next_version(today, existing=["2026-08-31"]) == "2026-08-31b"
    assert next_version(today, existing=["2026-08-31", "2026-08-31b"]) == "2026-08-31c"


def test_version_names_sort_chronologically():
    """`latest_catalog_version` تعتمد الترتيب الأبجدي — فيجب أن يوافق الزمن."""
    names = ["2026-08", "2026-08-31", "2026-08-31b", "2026-09", "2026-09-01"]
    assert sorted(names) == names


def test_editing_does_not_touch_the_original_catalog(catalog):
    """`apply_edits` تنسخ ولا تعدّل — وإلا تغيّرت أسعار الجلسة المفتوحة."""
    before = catalog[MATERIALS]["براكيت جنل 2 متر"][PRICE]
    edited = apply_edits(catalog, [{
        "الباب": MATERIALS, "الاسم": "براكيت جنل 2 متر",
        "المفتاح": PRICE, "السعر": 999_000,
    }])
    assert edited[MATERIALS]["براكيت جنل 2 متر"][PRICE] == 999_000
    assert catalog[MATERIALS]["براكيت جنل 2 متر"][PRICE] == before


def test_an_unknown_item_is_refused_not_created(catalog):
    """تعديل باسم غير موجود خطأ لا مادة جديدة تُخلَق بصمت."""
    with pytest.raises(KeyError, match="لا يوجد بند"):
        apply_edits(catalog, [{"الباب": MATERIALS, "الاسم": "مادة وهمية",
                               "المفتاح": PRICE, "السعر": 1}])


# ════════════════════ ٢. الأسعار المشتقّة ════════════════════


def test_derived_prices_are_not_written_into_the_saved_file(catalog, isolated):
    """السعر المشتقّ يُحسب عند التحميل، فلا يُخزَّن رقماً ثابتاً (ق-٥٨)."""
    path = save_as_new_version(catalog, "2026-12")
    saved = json.loads(path.read_text(encoding="utf-8"))
    bare = saved[MATERIALS]["عمود 11م مشبك"]
    assert DERIVED in bare
    assert PRICE not in bare


def test_stripping_derived_prices_leaves_the_original_untouched(catalog):
    stripped = strip_derived(catalog)
    assert PRICE not in stripped[MATERIALS]["عمود 11م مشبك"]
    assert catalog[MATERIALS]["عمود 11م مشبك"][PRICE] is not None


def test_a_derived_row_is_shown_but_not_editable(catalog):
    """يُعرض ليراه المستخدم، ويُقفَل لئلا يكسر الاشتقاق."""
    rows = {r["الاسم"]: r for r in editable_rows(catalog) if r["الباب"] == MATERIALS}
    assert rows["عمود 11م مشبك"]["محرَّر"] is False
    assert rows["عمود 11م مشبك مع الملحقات"]["محرَّر"] is True
    assert "مشتقّ" in rows["عمود 11م مشبك"]["ملاحظة"]


def test_editing_the_source_moves_the_derived_price(catalog, isolated):
    """تحرير الأصل وحده يكفي — والمشتقّ يتبعه عند التحميل."""
    edited = apply_edits(catalog, [{
        "الباب": MATERIALS, "الاسم": "عمود 11م مشبك مع الملحقات",
        "المفتاح": PRICE, "السعر": 2_000_000,
    }])
    save_as_new_version(edited, "2026-12")
    import engine

    reloaded = engine.load_catalog("2026-12")
    bracket = reloaded[MATERIALS]["براكيت جنل 1.4 م مع الملحقات"][PRICE]
    assert reloaded[MATERIALS]["عمود 11م مشبك"][PRICE] == 2_000_000 - bracket


# ════════════════════ ٣. صفوف التحرير والمقارنة ════════════════════


def test_dual_priced_labour_gets_one_row_per_circuit(catalog):
    """بند الأجر ذو السعرين يُحرَّر سعراً سعراً لا سعراً واحداً (ق-١٦)."""
    rows = [r for r in editable_rows(catalog)
            if r["الاسم"].startswith("نصب عمود مشبك تعليق 14م")]
    assert {r["المفتاح"] for r in rows} == {"السعر_مفردة", "السعر_مزدوجة"}
    assert all(r["الاسم_الأصلي"] == "نصب عمود مشبك تعليق 14م" for r in rows)


def test_every_price_in_the_catalog_appears_in_the_editor(catalog):
    """حارس تغطية: سعر لا يظهر في الشاشة سعر لا يمكن تصحيحه."""
    rows = editable_rows(catalog)
    assert len([r for r in rows if r["الباب"] == MATERIALS]) == len(catalog[MATERIALS])
    labour_names = {r["الاسم_الأصلي"] for r in rows if r["الباب"] == LABOUR}
    assert labour_names == set(catalog[LABOUR])


def test_differences_lists_only_what_changed(catalog):
    edited = apply_edits(catalog, [{
        "الباب": MATERIALS, "الاسم": "براكيت جنل 2 متر",
        "المفتاح": PRICE, "السعر": 120_000,
    }])
    diff = differences(catalog, edited)
    assert len(diff) == 1
    assert diff[0]["الاسم"] == "براكيت جنل 2 متر"
    assert (diff[0]["قبل"], diff[0]["بعد"]) == (110_000, 120_000)


def test_differences_ignores_derived_materials(catalog):
    """المشتقّ يتغيّر **نتيجةً** لا تعديلاً، فإدراجه يوهم بتعديلين."""
    edited = apply_edits(catalog, [{
        "الباب": MATERIALS, "الاسم": "براكيت جنل 1.4 م مع الملحقات",
        "المفتاح": PRICE, "السعر": 80_000,
    }])
    names = {d["الاسم"] for d in differences(catalog, edited)}
    assert names == {"براكيت جنل 1.4 م مع الملحقات"}
    assert "عمود 11م مشبك" not in names


def test_unpricing_an_item_is_a_real_change(catalog):
    """إفراغ السعر يعني «غير مُسعَّر» — لا صفراً يُحتسب بصمت (ق-٩)."""
    edited = apply_edits(catalog, [{
        "الباب": MATERIALS, "الاسم": "براكيت جنل 2 متر",
        "المفتاح": PRICE, "السعر": None,
    }])
    diff = differences(catalog, edited)
    assert diff[0]["بعد"] is None
