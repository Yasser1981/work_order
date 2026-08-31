# -*- coding: utf-8 -*-
"""اختبارات حفظ أمر العمل وفتحه — ملف `.wo` (ق-٦١).

الخطر الذي تحرسه هذه الاختبارات: **حقل يُضاف ولا يُحفظ**. فمُدخَل يختفي عند
الفتح لا يُحدث خطأً ولا رسالة، بل يعطي رقماً أقلّ بصمت — وهو أسوأ أنواع الخلل.
فالحارس هنا يقارن الكائن قبل الحفظ وبعد الفتح **بالمساواة الكاملة**، ويُبنى
الكائن المُختبَر بملء **كل حقل** من `dataclasses.fields` لا بقائمة مكتوبة.
"""

from dataclasses import fields, is_dataclass
from datetime import date
from enum import Enum

import pytest

from engine.equipment import TransformerSize, TransformerVoltage
from engine.store import (
    FILE_KIND,
    FORMAT_VERSION,
    LoadError,
    decode,
    document,
    encode,
    load,
    save,
)
from engine.types import (
    CircuitType,
    Equipment,
    LVNetworkType,
    Network11kV,
    Network33kV,
    NetworkLV,
    Project,
    Segment,
    SidewalkType,
    SupplyForm,
    Underground11kV,
    Underground33kV,
)
from engine.workorder import WorkOrder

CONTENT_TYPES = [
    Network11kV, Network33kV, NetworkLV, Equipment, Underground11kV, Underground33kV,
]


def populate(cls, seed: int = 7):
    """يبني كائناً **كل حقوله غير افتراضية** — فحقل منسيّ يفشل المقارنة.

    القيمة تُشتقّ من نوع الحقل الحالي لا من قائمة مكتوبة، فحقل جديد يُملأ
    تلقائياً ويدخل الحراسة بلا تعديل هنا.
    """
    kwargs = {}
    for i, f in enumerate(fields(cls)):
        current = getattr(cls(), f.name)
        value = seed + i
        if isinstance(current, bool):
            value = not current
        elif isinstance(current, Enum):
            options = list(type(current))
            value = options[(options.index(current) + 1) % len(options)]
        elif isinstance(current, str):
            value = f"نصّ {i}"
        elif isinstance(current, float):
            value = float(seed + i) + 0.5
        elif isinstance(current, dict):
            value = {(TransformerVoltage.KV33, TransformerSize.KVA630): 2}
        elif isinstance(current, list):
            value = current                     # الجداول الثابتة الأسماء
        elif current is None:
            value = float(seed + i)
        kwargs[f.name] = value
    return cls(**kwargs)


# ════════════════════════ ١. الذهاب والإياب الكامل ════════════════════════


@pytest.mark.parametrize("cls", CONTENT_TYPES, ids=lambda c: c.__name__)
def test_every_field_of_every_content_type_survives(cls):
    """حارس الحقول: كل حقل مملوء بقيمة غير افتراضية يعود كما ذهب."""
    original = populate(cls)
    assert decode(encode(original)) == original


def test_a_forgotten_field_would_fail_this_guard():
    """يثبت أن الحارس أعلاه يعمل فعلاً — لو أُسقط حقل لظهر الفرق.

    بلا هذا الاختبار قد يمرّ الحارس السابق لأن `populate` تركت الحقول على
    قيمها الافتراضية، فتتساوى الكائنات لسبب خاطئ.
    """
    original = populate(Network11kV)
    for f in fields(Network11kV):
        assert getattr(original, f.name) != getattr(Network11kV(), f.name), f.name

    crippled = encode(original)
    del crippled["poles_lattice"]
    assert decode(crippled) != original


def test_a_whole_work_order_round_trips(tmp_path):
    """مشروع كامل: مقاطع من كل نوع، وترويسة، وجداول العاملين والآليات."""
    project = Project(
        "مشروع كامل",
        [Segment(f"مقطع {i}", populate(cls)) for i, cls in enumerate(CONTENT_TYPES)],
        street_crossing_secondary_m=12.0,
        street_crossing_secondary_feeders=3,
        street_crossing_main_m=8.0,
        street_crossing_main_feeders=2,
    )
    order = WorkOrder(
        number="45", order_date=date(2026, 8, 31), classification="توسعات",
        project_name="مشروع كامل", duration="90 يوم", work_scope="حجم العمل",
        start_date=None, notes="ملاحظة",
    )
    order.staff[0].count, order.staff[0].days = 2, 90
    order.equipment[1].count, order.equipment[1].days = 1, 45

    path = save(tmp_path / "أمر", order, project, "2026-08")
    assert path.suffix == ".wo"

    restored_order, restored_project, version = load(path)
    assert version == "2026-08"
    assert restored_order == order
    assert restored_project == project


def test_the_start_date_stays_empty_when_it_was_empty(tmp_path):
    """التاريخ الفارغ خيار مقصود (ق-٥٥) — لا يُملأ بتاريخ اليوم عند الفتح."""
    path = save(tmp_path / "a", WorkOrder(start_date=None), Project(), "2026-08")
    assert load(path)[0].start_date is None


# ════════════════════════ ٢. رفض ما لا يُفهم ════════════════════════


def test_a_foreign_file_is_refused_not_guessed(tmp_path):
    path = tmp_path / "غريب.wo"
    path.write_text('{"شيء": 1}', encoding="utf-8")
    with pytest.raises(LoadError, match="ليس ملفَّ أمر عمل"):
        load(path)


def test_broken_json_is_reported_clearly(tmp_path):
    path = tmp_path / "مكسور.wo"
    path.write_text("{ليس", encoding="utf-8")
    with pytest.raises(LoadError, match="تعذّرت قراءته"):
        load(path)


def test_a_newer_format_is_refused(tmp_path):
    """ملف من إصدار أحدث يُرفض صراحةً — ولا يُقرأ نصفه ويُهمل نصفه."""
    import json

    doc = document(WorkOrder(), Project(), "2026-08")
    doc["إصدار_الصيغة"] = FORMAT_VERSION + 1
    path = tmp_path / "أحدث.wo"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(LoadError, match="حدّث البرنامج"):
        load(path)


def test_an_unknown_type_name_is_refused():
    with pytest.raises(LoadError, match="لا يعرفه"):
        decode({"نوع": "صنف_غير_موجود"})


def test_an_unknown_enum_value_is_refused():
    with pytest.raises(LoadError, match="قيمة غير معروفة"):
        decode({"نوع": "CircuitType", "قيمة": "ثلاثية"})


# ════════════════════════ ٣. تفاصيل الصيغة ════════════════════════


def test_the_file_is_readable_arabic_json(tmp_path):
    """الملف يُفتح بمحرّر نصوص فيُفهم — لا ترميز `\\uXXXX`."""
    path = save(tmp_path / "a", WorkOrder(number="45"), Project("مشروعي"), "2026-08")
    text = path.read_text(encoding="utf-8")
    assert "مشروعي" in text and "\\u" not in text
    assert FILE_KIND in text


def test_enums_are_saved_by_name_not_by_arabic_label():
    """الاسم البرمجي ثابت، والقيمة العربية نصّ معروض قد يُحرَّر يوماً."""
    assert encode(CircuitType.DOUBLE) == {"نوع": "CircuitType", "قيمة": "DOUBLE"}
    assert encode(SidewalkType.TERRAZZO)["قيمة"] == "TERRAZZO"
    assert encode(LVNetworkType.BARE_WIRES)["قيمة"] == "BARE_WIRES"
    assert encode(SupplyForm.WITH_ACCESSORIES)["قيمة"] == "WITH_ACCESSORIES"


def test_the_transformer_key_is_a_pair_of_enums(tmp_path):
    """مفتاح المحولة ثنائي (جهد وسعة) — لا يصلح مفتاحاً نصّياً في JSON."""
    eq = Equipment(transformers={(TransformerVoltage.KV33, TransformerSize.KVA630): 4})
    restored = decode(encode(eq))
    assert restored.transformers == eq.transformers
    assert (TransformerVoltage.KV33, TransformerSize.KVA630) in restored.transformers


def test_results_are_not_saved_only_inputs(tmp_path):
    """الكميات والكلف **لا تُحفَظ** — تُحسب عند الفتح (ق-٦١).

    فتصحيحٌ لقاعدة حسابية (كتصحيح البراكيت في ق-٦٠) يظهر في أوامر العمل
    القديمة عند فتحها، ولا تبقى أرقام خاطئة محفوظة إلى الأبد.
    """
    project = Project("م", [Segment("أ", Network11kV(poles_lattice=9))])
    path = save(tmp_path / "a", WorkOrder(), project, "2026-08")
    text = path.read_text(encoding="utf-8")
    for word in ("الكلفة_الكلية", "كلفة_المواد", "براكيت", "السعر"):
        assert word not in text, word


def test_an_unknown_value_type_is_refused_not_silently_dropped():
    with pytest.raises(TypeError, match="لا أعرف كيف أحفظ"):
        encode({1, 2, 3})


def test_all_content_types_are_dataclasses():
    """شرط ضمني لآلية الحفظ العامة — يُختبر صراحةً لئلا يُكسر بلا انتباه."""
    for cls in CONTENT_TYPES:
        assert is_dataclass(cls), cls.__name__
