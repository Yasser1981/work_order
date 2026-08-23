# -*- coding: utf-8 -*-
"""اختبارات مسارات البيانات — تحاكي الملف التنفيذي المبنيّ (ق-٢٨).

الخلل الذي تحرسه: PyInstaller بنمط الملف الواحد يفكّ البرنامج في مجلد مؤقّت يُمسح
عند الإغلاق. فلو قرأ البرنامج أسعاره من داخل الحزمة لضاع كل تعديل عليها. وهو خلل
لا يظهر إلا بعد البناء، فلا سبيل لاكتشافه إلا بمحاكاة التجميد هنا.
"""

import json
import sys

import pytest

from engine import load_catalog, paths


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    """يحاكي ملفاً تنفيذياً مبنيّاً: حزمة مؤقّتة، وملف تنفيذي في مجلد قابل للكتابة."""
    bundle = tmp_path / "حزمة_مؤقتة"          # يقابل sys._MEIPASS
    (bundle / "data").mkdir(parents=True)
    exe_dir = tmp_path / "مجلد_البرنامج"
    exe_dir.mkdir()

    (bundle / "data" / "catalog_2026-08.json").write_text(
        json.dumps({"نسخة": "المصنع", "المواد": {}, "أجور_العمل": {}}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "أوامر_العمل.exe"))
    return {"bundle": bundle, "exe_dir": exe_dir}


# ═══════════════════ وضع التطوير ═══════════════════


def test_in_development_both_folders_are_the_repository_data():
    """لا نسخ ولا ازدواج أثناء التطوير — المجلدان واحد."""
    assert not paths.is_frozen()
    assert paths.user_data_dir() == paths.bundled_data_dir()
    assert paths.user_data_dir().name == "data"


def test_development_catalog_loads_and_is_the_real_one():
    assert load_catalog()["نسخة"] == "2026-08"


# ═══════════════════ وضع الملف التنفيذي ═══════════════════


def test_frozen_reads_from_beside_the_executable_not_from_the_bundle(frozen):
    """المجلد العامل بجانب الـexe — لا داخل الحزمة المؤقّتة التي تُمسح."""
    assert paths.is_frozen()
    assert paths.user_data_dir() == frozen["exe_dir"] / "data"
    assert paths.bundled_data_dir() == frozen["bundle"] / "data"
    assert paths.user_data_dir() != paths.bundled_data_dir()


def test_first_run_copies_the_factory_catalog_out_of_the_bundle(frozen):
    target = frozen["exe_dir"] / "data" / "catalog_2026-08.json"
    assert not target.exists()
    paths.ensure_user_data()
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8"))["نسخة"] == "المصنع"


def test_a_user_edit_survives_the_next_run(frozen):
    """أهمّ اختبار: تعديل الأسعار لا يُمحى — لا بإعادة التشغيل ولا بتحديث البرنامج."""
    paths.ensure_user_data()
    edited = frozen["exe_dir"] / "data" / "catalog_2026-08.json"
    edited.write_text(
        json.dumps({"نسخة": "المُعدَّلة", "المواد": {}, "أجور_العمل": {}}, ensure_ascii=False),
        encoding="utf-8",
    )

    paths.ensure_user_data()                     # تشغيل تالٍ
    assert load_catalog("2026-08")["نسخة"] == "المُعدَّلة"


def test_a_program_update_does_not_overwrite_user_prices(frozen):
    """نسخة المصنع لا تعلو على تعديل المستخدم (ق-٠)."""
    paths.ensure_user_data()
    user_file = frozen["exe_dir"] / "data" / "catalog_2026-08.json"
    user_file.write_text('{"نسخة": "أسعاري", "المواد": {}, "أجور_العمل": {}}', encoding="utf-8")

    # حزمة جديدة بأسعار مصنع مختلفة — كأن البرنامج حُدِّث
    (frozen["bundle"] / "data" / "catalog_2026-08.json").write_text(
        '{"نسخة": "مصنع أحدث", "المواد": {}, "أجور_العمل": {}}', encoding="utf-8"
    )
    paths.ensure_user_data()
    assert load_catalog("2026-08")["نسخة"] == "أسعاري"


def test_a_new_factory_version_does_arrive_with_an_update(frozen):
    """الجديد يُنسخ، والقديم لا يُمسّ — الشرطان معاً."""
    paths.ensure_user_data()
    (frozen["bundle"] / "data" / "catalog_2027-01.json").write_text(
        '{"نسخة": "2027-01", "المواد": {}, "أجور_العمل": {}}', encoding="utf-8"
    )
    assert paths.catalog_versions() == ["2026-08", "2027-01"]
    assert paths.latest_catalog_version() == "2027-01"
    assert load_catalog()["نسخة"] == "2027-01"


def test_falls_back_to_the_home_folder_when_the_exe_folder_is_read_only(
    frozen, monkeypatch
):
    """البرنامج في Program Files: الكتابة بجانبه ممنوعة، فيتحوّل إلى مجلد المستخدم."""
    monkeypatch.setattr(paths, "_is_writable", lambda folder: False)
    assert paths.user_data_dir() == paths.Path.home() / paths.APP_FOLDER_NAME / "data"


def test_writability_is_tested_by_actually_writing(tmp_path):
    """لا نثق بالصلاحيات المعلنة — ويندوز يعلن ما لا يحترمه."""
    assert paths._is_writable(tmp_path / "مجلد_جديد")

    # مسار يستحيل إنشاؤه: أبوه ملفّ لا مجلد
    blocker = tmp_path / "هذا_ملف"
    blocker.write_text("", encoding="utf-8")
    assert not paths._is_writable(blocker / "تحته")


# ═══════════════════ اختيار النسخة ═══════════════════


def test_an_unknown_version_names_what_is_available():
    """رسالة الخطأ تدلّ على المخرج بدل أن تترك المستخدم يخمّن."""
    with pytest.raises(FileNotFoundError) as error:
        load_catalog("1999-01")
    assert "1999-01" in str(error.value)
    assert "2026-08" in str(error.value)


def test_no_catalog_at_all_is_reported_clearly(frozen, monkeypatch):
    (frozen["bundle"] / "data" / "catalog_2026-08.json").unlink()
    with pytest.raises(FileNotFoundError) as error:
        paths.latest_catalog_version()
    assert "catalog_YYYY-MM.json" in str(error.value)
