# -*- coding: utf-8 -*-
"""اختبارات آلية القوالب — مشروع واحد يُخرَج بأكثر من قالب."""

from datetime import date

import pytest

import printing
from engine import load_catalog
from engine.overhead import compute
from engine.types import CircuitType, Network11kV, Network33kV, OverheadProject
from engine.workorder import WorkOrder


@pytest.fixture(scope="module")
def result():
    project = OverheadProject(
        net11=Network11kV(route_length_m=500, poles_lattice=5, poles_round=16,
                          stay_rod_sets=2),
        net33=Network33kV(route_length_m=2000, poles_suspension=27, anchors_mid=3,
                          anchors_end=2, circuit=CircuitType.DOUBLE),
    )
    return compute(project, load_catalog())


@pytest.fixture
def order():
    return WorkOrder(number="45", project_name="مشروع اختباري",
                     order_date=date(2026, 8, 19))


# ═══════════════════════ السجل ═══════════════════════


def test_builtin_templates_are_registered():
    keys = [t.key for t in printing.available()]
    assert "iso" in keys and "audit" in keys


def test_every_template_has_a_name_and_description():
    for template in printing.available():
        assert template.name.strip()
        assert template.description.strip()


def test_unknown_template_key_is_rejected():
    with pytest.raises(KeyError):
        printing.get("لا-يوجد")


def test_duplicate_registration_is_rejected():
    """تسجيل مفتاح مكرّر يُرفض بدل أن يستبدل قالباً قائماً بصمت."""
    existing = printing.get("iso")
    with pytest.raises(ValueError):
        printing.register(existing)


# ═══════════════════════ كل القوالب تقرأ نفس البيانات ═══════════════════════


@pytest.mark.parametrize("key", [t.key for t in printing.available()])
def test_template_renders_the_same_project(key, order, result):
    html = printing.get(key).build_html(order, result)
    assert "مشروع اختباري" in html
    assert "45" in html


@pytest.mark.parametrize("key", [t.key for t in printing.available()])
def test_template_writes_pdf(key, order, result, tmp_path, qapp):
    path = str(tmp_path / f"{key}.pdf")
    printing.get(key).write_pdf(order, result, path)
    assert (tmp_path / f"{key}.pdf").read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize("key", [t.key for t in printing.available()])
def test_every_template_lists_all_materials(key, order, result):
    """أي قالب يعرض كل المواد ذات الكمية — لا يُسقط شيئاً."""
    html = printing.get(key).build_html(order, result)
    for row in result["المواد"]:
        if row["الكمية"] > 0:
            assert row["المادة"] in html, f"{row['المادة']} مفقودة من قالب {key}"


# ═══════════════ ما يميّز كل قالب عن الآخر ═══════════════


def test_iso_shows_no_prices_but_audit_does(order, result):
    """الإيزو نموذج كميات رسمي، وورقة التدقيق للمراجعة الداخلية."""
    iso = printing.get("iso").build_html(order, result)
    audit = printing.get("audit").build_html(order, result)

    assert "سعر الوحدة" not in iso
    assert "سعر الوحدة" in audit


def test_only_audit_shows_the_work_items(order, result):
    """فقرات العمل تظهر في ورقة التدقيق ولا تظهر في النموذج الرسمي."""
    iso = printing.get("iso").build_html(order, result)
    audit = printing.get("audit").build_html(order, result)

    labour_name = result["أجور_العمل"][0].name
    assert labour_name not in iso
    assert labour_name in audit
    assert f"{result['كلفة_العمل']:,.0f}" in audit


def test_only_audit_shows_quantity_sources(order, result):
    """تفصيل مصدر الكمية للمدقّق — لا يدخل النموذج الرسمي."""
    iso = printing.get("iso").build_html(order, result)
    audit = printing.get("audit").build_html(order, result)

    assert "المصدر" not in iso
    assert "المصدر" in audit
    assert "مقرَّب لأعلى" in audit          # تفصيل الكونكريت
    assert "مرفق" in audit or "×" in audit  # معادلات المصادر


def test_audit_totals_match_the_engine(order, result):
    audit = printing.get("audit").build_html(order, result)
    assert f"{result['كلفة_المواد']:,.0f}" in audit
    assert f"{result['كلفة_العمل']:,.0f}" in audit
    assert f"{result['الكلفة_الكلية']:,.0f}" in audit


def test_audit_warns_about_unpriced_materials(order):
    """المادة بلا سعر تُنبّه عنها ورقة التدقيق صراحةً.

    بسعر **مُحقون**: بعد ق-٣٦ صارت كل المواد مسعّرة، فربط الاختبار بمادة بعينها
    يجعله يفشل مع كل تحديث أسعار.
    """
    import copy

    from engine.overhead import compute
    from engine.types import Network11kV, OverheadProject

    catalog = copy.deepcopy(load_catalog())
    catalog["المواد"]["عمود 11م مشبك"]["السعر"] = None
    unpriced = compute(OverheadProject(net11=Network11kV(poles_lattice=3)), catalog)

    audit = printing.get("audit").build_html(order, unpriced)
    assert unpriced["أسعار_مفقودة"] == ["عمود 11م مشبك"]
    assert "تنبيه" in audit
    assert "عمود 11م مشبك" in audit


def test_adding_a_template_needs_no_engine_change():
    """حارس معماري: القوالب تقرأ نتيجة المحرك ولا يعرف المحرك بها.

    هذا ما يجعل إضافة قالب جديد تعديلاً في مجلد الطباعة وحده.
    """
    import inspect

    from engine import overhead

    source = inspect.getsource(overhead)
    assert "printing" not in source
    assert "iso_form" not in source


# ═══════════════════ القوالب ومشروع المقاطع ═══════════════════


@pytest.fixture(scope="module")
def segmented_result():
    """مشروع بمقاطع مسمّاة، وفيه بند بلا أجر (ربط المستهلكين)."""
    from engine.project import compute_project
    from engine.types import LVNetworkType, NetworkLV, Project, Segment

    project = Project(
        "مشروع بمقاطع",
        [
            Segment("المقطع الأول",
                    Network11kV(route_length_m=500, poles_lattice=5, poles_round=16)),
            Segment("المقطع الثاني",
                    NetworkLV(route_length_m=300, kind=LVNetworkType.BARE_WIRES,
                              poles_lattice=4, poles_round=12, consumers=5)),
        ],
    )
    return compute_project(project, load_catalog())


# ═══════════════════ اتجاه الأعمدة (ق-٦٤ — يصحّح ق-٥٤) ═══════════════════


def _tables(doc):
    """كل جداول المستند **بما فيها المتداخلة**، بترتيب ظهورها.

    منذ ق-٦٨ صار جدول المواد داخل جدول تخطيط، فلا يكفي المستوى الأول من
    `rootFrame().childFrames()` — وكان الاكتفاء به يجعل الحرّاس تفحص جدولاً
    واحداً وتظنّ أنها فحصت الكل.
    """
    from PyQt6.QtGui import QTextTable

    found, pending = [], list(doc.rootFrame().childFrames())
    while pending:
        frame = pending.pop(0)
        pending.extend(frame.childFrames())
        if isinstance(frame, QTextTable):
            found.append(frame)
    return found


def _header_columns(doc, table):
    """نصوص خلايا الصفّ الأول مقرونةً بموضعها الأفقي في المستند المرسوم."""
    layout = doc.documentLayout()
    found = []
    for col in range(table.columns()):
        cell = table.cellAt(0, col)
        block = cell.firstCursorPosition().block()
        found.append((block.text().strip(), layout.blockBoundingRect(block).left()))
    return found


def _laid_out(html: str):
    """مستند مرسوم فعلاً — القياس على النتيجة لا على النصّ."""
    from PyQt6.QtGui import QTextDocument
    from printing.iso_form import styles, _rtl_option

    doc = QTextDocument()
    doc.setDefaultStyleSheet(styles())
    doc.setDefaultTextOption(_rtl_option())
    doc.setHtml(html)
    doc.setTextWidth(1000)
    return doc


def test_the_serial_column_is_the_rightmost_one(order, result, qapp):
    """**حارس هندسي:** عمود «ت» في أقصى اليمين في كل جدول يحمله (ق-٦٤).

    ويقيس هذا الاختبار **المستند المرسوم** لا نصّ HTML ولا قواعد CSS — وهذا هو
    الفرق الجوهري عن حارس ق-٥٤ الذي كان يتحقّق من وجود `direction: rtl` في
    الأنماط. تلك القاعدة موجودة فعلاً **ولا تقلب ترتيب الأعمدة** في محرّك
    QTextDocument، فكان الحارس يمرّ والنموذج مقلوب — حتى طبع المستخدم أول أمر
    عمل فرأى «ت» في أقصى اليسار.

    فالقياس هنا على ما يراه القارئ في الورقة، ولا يمكن أن يمرّ على خلل مماثل.
    """
    for key in ("iso", "audit"):
        doc = _laid_out(printing.get(key).build_html(order, result))
        checked = 0
        for table in _tables(doc):
            columns = _header_columns(doc, table)
            positions = {text: left for text, left in columns}
            if "ت" not in positions:
                continue
            checked += 1
            assert positions["ت"] == max(left for _, left in columns), (
                f"{key}: «ت» ليس أقصى اليمين — {columns}"
            )
        assert checked >= 2, f"{key}: لم يُفحص جدولان على الأقل"


def test_the_material_columns_run_right_to_left_in_order(order, result, qapp):
    """ترتيب أعمدة جدول المواد كاملاً: ت ← اسم المادة ← الوحدة ← الكمية."""
    doc = _laid_out(printing.get("iso").build_html(order, result))
    # يُنتقى بعنوانه لا بترتيبه: ثلاثة جداول تحمل «ت» منذ ق-٦٨
    table = _table_headed(doc, "اسم المادة")
    ordered = [text for text, _ in
               sorted(_header_columns(doc, table), key=lambda c: -c[1])]
    assert ordered == ["ت", "اسم المادة", "الوحدة القياسية", "الكمية"], ordered


def test_the_header_table_puts_the_label_before_its_value(order, result, qapp):
    """ترويسة أمر العمل: «التبويب» يمين قيمته، و«التاريخ» يمين تاريخه."""
    doc = _laid_out(printing.get("iso").build_html(order, result))
    header = _tables(doc)[0]
    ordered = [text for text, _ in
               sorted(_header_columns(doc, header), key=lambda c: -c[1])]
    assert ordered[0] == "التبويب", ordered
    assert ordered.index("التاريخ") < ordered.index("2026/08/19"), ordered


def test_the_styles_keep_the_document_direction(qapp):
    """`direction: rtl` تبقى: تضبط اتجاه النصّ داخل الخلية والفقرة.

    **ولا تقلب الأعمدة** — يفعل ذلك `_row` وحدها. مُثبَّت أعلاه هندسياً.
    """
    import re

    from printing.iso_form import styles

    css = styles()
    assert re.search(r"body\s*\{[^}]*direction:\s*rtl", css), css


# ═══════════ التخطيط: الجداول متجاورة (ق-٦٨) ═══════════


def _table_headed(doc, header: str):
    for table in _tables(doc):
        texts = [table.cellAt(0, c).firstCursorPosition().block().text().strip()
                 for c in range(table.columns())]
        if header in texts:
            return table
    raise AssertionError(f"لا جدول فيه العنوان «{header}»")


def _left_edge(doc, table):
    block = table.cellAt(0, 0).firstCursorPosition().block()
    return doc.documentLayout().blockBoundingRect(block).left()


def test_the_side_tables_sit_beside_the_materials_not_below_them(order, result, qapp):
    """**حارس هندسي:** الإشراف والآليات والملاحظات **يسار** جدول المواد (ق-٦٨).

    يقيس المستند المرسوم: لو انهار التخطيط إلى عمود واحد لصار أحدها تحت الآخر
    بالإحداثي نفسه تقريباً، فيسقط الاختبار.
    """
    order.staff[0].count, order.staff[0].days = 1, 30
    order.equipment[2].count, order.equipment[2].days = 1, 30
    doc = _laid_out(printing.get("iso").build_html(order, result))

    materials = _left_edge(doc, _table_headed(doc, "اسم المادة"))
    for header in ("نوع العاملين", "نوع الآلية"):
        assert _left_edge(doc, _table_headed(doc, header)) < materials, header


def test_the_side_tables_share_one_top_line_with_the_materials(order, result, qapp):
    """يبدأ العمودان من ارتفاع واحد — لا يهبط أحدهما تحت الآخر."""
    order.staff[0].count, order.staff[0].days = 1, 30
    doc = _laid_out(printing.get("iso").build_html(order, result))
    layout = doc.documentLayout()

    def top(header):
        table = _table_headed(doc, header)
        return layout.blockBoundingRect(
            table.cellAt(0, 0).firstCursorPosition().block()).top()

    assert abs(top("اسم المادة") - top("نوع العاملين")) < 40


def test_the_materials_header_repeats_on_every_page(order, result, qapp):
    """صفحة ثانية بأعمدة بلا عناوين = أربعة أرقام لا يُعرف أيّها أيّ (ق-٦٨).

    و`<th>` وحده لا يفعلها: مستورد HTML في Qt لا يضبط `headerRowCount` منه.

    **والفحص على `document()` التي تستعملها الطباعة نفسها** لا على
    `repeat_header_rows` وحدها: أول صياغة لهذا الاختبار استدعت الدالة بيدها،
    فكان حذفُ استدعائها من مسار الطباعة يمرّ بلا أن يسقط شيء — جرّبتُ الطفرة
    فمرّت. فصار الاختبار يفحص **الوصل** لا الدالة.
    """
    from printing.iso_form import document

    doc = document(order, result)
    assert _table_headed(doc, "اسم المادة").format().headerRowCount() == 1
    for header in ("نوع العاملين", "نوع الآلية"):
        assert _table_headed(doc, header).format().headerRowCount() == 0, header


def test_only_the_materials_table_repeats_its_header(order, result, qapp):
    """الجداول الجانبية قصيرة لا تعبر الصفحات، فتكرار عناوينها ضجيج."""
    from printing.iso_form import build_html, repeat_header_rows

    doc = _laid_out(build_html(order, result))
    assert repeat_header_rows(doc, "اسم المادة") == 1


def test_a_long_material_list_flows_without_losing_rows(tmp_path, order, qapp):
    """التخطيط المتجاور لا يبتلع الصفوف الزائدة: 90 مادة على صفحتين وكلها هناك."""
    from printing.iso_form import write_pdf

    big = {
        "المواد": [{"المادة": f"مادة رقم {i}", "الوحدة": "عدد", "الكمية": i,
                    "سعر الوحدة": 1000, "الكلفة": i * 1000,
                    "كمية_فقط": False, "سعر_مفقود": False} for i in range(1, 91)],
        "كلفة_المواد": 800_000, "كلفة_العمل": 200_000, "الكلفة_الكلية": 1_000_000,
    }
    doc = _laid_out(build_html_of(order, big))
    table = _table_headed(doc, "اسم المادة")
    assert table.rows() == 91                       # رأس + 90 مادة

    path = tmp_path / "big.pdf"
    write_pdf(order, big, str(path))
    assert path.exists() and path.stat().st_size > 10_000


def build_html_of(order, result):
    return printing.get("iso").build_html(order, result)


# ═══════════ فراغات الفصل بين الجداول (ق-٦٩) ═══════════


def _frame(doc, table):
    """مستطيل **إطار الجدول** لا نصّه.

    وهذا هو الفرق الذي أسقط أول صياغة لهذين الحارسين: كنتُ أقيس مواضع **كتل
    النصّ** داخل الخلايا، وبينها حشوة الخلية (`cellpadding`) في كل الأحوال —
    فحذفُ الفاصل بين العمودين كان يُبقي الفرق موجباً والاختبار راضياً. جرّبتُ
    الطفرة فمرّت، فصار القياس على `frameBoundingRect`: صفرٌ حين تتلاصق الحدود.
    """
    return doc.documentLayout().frameBoundingRect(table)


def test_a_gutter_separates_the_two_columns(order, result, qapp):
    """**حارس هندسي:** فراغ بين حدّي العمودين — لا يلتصق جدولٌ بجدول (ق-٦٩).

    بلا الفاصل يصير الفرق **صفراً بالضبط**، ومعه 19 نقطة.
    """
    order.staff[0].count, order.staff[0].days = 1, 30
    doc = _laid_out(printing.get("iso").build_html(order, result))
    gap = (_frame(doc, _table_headed(doc, "اسم المادة")).left()
           - _frame(doc, _table_headed(doc, "نوع العاملين")).right())
    assert gap > 8, gap


def test_a_gap_separates_the_header_from_the_tables_below(order, result, qapp):
    """جدول الترويسة لا يلتصق بما تحته: 47 نقطة بالفاصل و18 بدونه."""
    order.staff[0].count, order.staff[0].days = 1, 30
    doc = _laid_out(printing.get("iso").build_html(order, result))
    gap = (_frame(doc, _table_headed(doc, "اسم المادة")).top()
           - _frame(doc, _table_headed(doc, "التبويب")).bottom())
    assert gap > 30, gap


# ═══════════ تذييل التواقيع (ق-٦٦) ═══════════


def test_the_signature_titles_are_the_five_you_named(order, result, qapp):
    """الخمسة بترتيبهم من اليمين، ولكلٍّ سطر توقيع تحته (ق-٦٦)."""
    from printing.iso_form import SIGNATURES

    assert list(SIGNATURES) == [
        "مسؤول القطاع", "مسؤول التنفيذ", "مسؤول الفنية",
        "مسؤول التخطيط", "مدير الفرع",
    ]
    doc = _laid_out(printing.get("iso").build_html(order, result))
    table = _table_headed(doc, SIGNATURES[0])
    assert table.columns() == len(SIGNATURES)
    titles = [table.cellAt(0, c).firstCursorPosition().block().text().strip()
              for c in range(table.columns() - 1, -1, -1)]
    assert titles == list(SIGNATURES), titles
    lines = [table.cellAt(1, c).firstCursorPosition().block().text().strip()
             for c in range(table.columns())]
    assert all(line.startswith(".") for line in lines), lines


def test_the_signature_row_reads_right_to_left(order, result, qapp):
    """**حارس هندسي:** «مسؤول القطاع» أقصى اليمين و«مدير الفرع» أقصى اليسار."""
    from printing.iso_form import SIGNATURES

    doc = _laid_out(printing.get("iso").build_html(order, result))
    table = _table_headed(doc, SIGNATURES[0])
    layout = doc.documentLayout()
    placed = {
        table.cellAt(0, c).firstCursorPosition().block().text().strip():
            layout.blockBoundingRect(
                table.cellAt(0, c).firstCursorPosition().block()).left()
        for c in range(table.columns())
    }
    assert placed[SIGNATURES[0]] == max(placed.values()), placed
    assert placed[SIGNATURES[-1]] == min(placed.values()), placed


# ═══════════ سطر الكلفة التخمينية المفصَّل (ق-٦٥) ═══════════


def _cost_block(doc):
    """فقرة سطر الكلفة **بعد رسمها فعلاً**.

    ⚠️ **يجب أن يبقى `doc` حيّاً عند المُنادي.** `QTextBlock` مؤشّر إلى داخل
    المستند لا نسخة منه، فلو جُمع المستند بعد الاستدعاء (`_cost_block(_laid_out(…))`
    بلا متغيّر يمسكه) صار المؤشّر معلّقاً و**سقطت العملية بـ Segfault** عند أول
    قراءة — لا باستثناء يُلتقط.

    `blockBoundingRect` ليست للقياس هنا بل **تُجبر Qt على رسم الفقرة**: قبلها
    `layout().lineCount()` صفر، و`lineAt(0)` عندئذٍ **تُسقط العملية** لا ترفع
    استثناءً — كنظير `QFontDatabase` بلا `QApplication` في ق-٥٣.
    """
    block = doc.begin()
    while block.isValid():
        if "الكلفة التخمينية الكلية" in block.text():
            doc.documentLayout().blockBoundingRect(block)
            assert block.layout().lineCount() == 1, "السطر لم يُرسم"
            return block
        block = block.next()
    raise AssertionError("لا سطر كلفة في المستند")


def test_the_cost_line_shows_both_parts_and_their_sum(order, result, qapp):
    """بنصّك: المواد + العمل = الكلي د.ع — في سطر واحد."""
    doc = _laid_out(printing.get("iso").build_html(order, result))
    text = _cost_block(doc).text()
    for part in ("كلفة المواد التخمينية", "كلفة العمل التخمينية",
                 "الكلفة التخمينية الكلية", "د.ع", "+", "="):
        assert part in text, (part, text)
    for value in ("كلفة_المواد", "كلفة_العمل", "الكلفة_الكلية"):
        assert f"{result[value]:,.0f}" in text, (value, text)


def test_the_printed_sum_actually_adds_up(order, result, qapp):
    """حارس حسابي: المعروض في الورقة يجمع فعلاً — لا ثلاثة أرقام لا رابط بينها."""
    import re

    doc = _laid_out(printing.get("iso").build_html(order, result))
    text = _cost_block(doc).text()
    numbers = [int(n.replace(",", "")) for n in re.findall(r"[\d,]{4,}", text)]
    assert len(numbers) == 3, numbers
    assert numbers[0] + numbers[1] == numbers[2], numbers


def test_the_cost_line_reads_right_to_left(order, result, qapp):
    """**حارس هندسي:** المواد يمين العمل يمين المجموع — بترتيب القراءة (ق-٦٥).

    و`+` و`=` محارف محايدة في خوارزمية BiDi تأخذ اتجاهها من جوارها، فقد تنتقل
    إلى الطرف الخطأ. جرّبتُ تغليفها بعلامات اتجاه فلم يتغيّر الرسم شيئاً، فحُذفت
    وبقي هذا القياس حارساً: يقيس موضع كل مبلغ في **السطر المرسوم** لا في النصّ.
    """
    doc = _laid_out(printing.get("iso").build_html(order, result))
    block = _cost_block(doc)
    text = block.text()
    line = block.layout().lineAt(0)
    positions = [line.cursorToX(text.index(f"{result[key]:,.0f}"))[0]
                 for key in ("كلفة_المواد", "كلفة_العمل", "الكلفة_الكلية")]
    assert positions[0] > positions[1] > positions[2], positions


# ═══════════ الإشراف الفني والآليات: بلا أسطر صفرية (ق-٦٤) ═══════════


def _table_titled(doc, header: str):
    """الجدول الذي يحمل هذا العنوان في صفّه الأول — لا بترتيبه فيتغيّر بأي إضافة."""
    for table in _tables(doc):
        if any(text == header for text, _ in _header_columns(doc, table)):
            return table
    raise AssertionError(f"لا جدول عنوانه «{header}»")


def _body(doc, table) -> list[list[str]]:
    """صفوف الجدول بلا رأسه، كلُّ صفّ نصوصُ خلاياه من اليمين إلى اليسار."""
    return [
        [table.cellAt(r, c).firstCursorPosition().block().text().strip()
         for c in range(table.columns() - 1, -1, -1)]
        for r in range(1, table.rows())
    ]


def test_a_row_with_no_count_is_left_out(order, result, qapp):
    """السطر بلا عدد لا يُطبع — النموذج يُظهر ما استُخدم فعلاً (ق-٦٤).

    والفحص على **خلايا الجدول المرسوم** لا على نصّ HTML: «عامل» جزء من «نوع
    العاملين» في رأس الجدول، فالبحث النصّي يمرّ على الخطأ ويسقط على الصواب.
    """
    order.staff[0].count, order.staff[0].days = 1, 90     # مهندس
    order.staff[2].count = 0                              # عامل — صفر
    order.equipment[2].count, order.equipment[2].days = 1, 90   # رافعة

    doc = _laid_out(printing.get("iso").build_html(order, result))
    staff = [row[1] for row in _body(doc, _table_titled(doc, "نوع العاملين"))]
    equipment = [row[1] for row in _body(doc, _table_titled(doc, "نوع الآلية"))]
    assert staff == ["مهندس"], staff
    assert equipment == ["رافعة"], equipment


def test_the_serial_renumbers_after_the_empty_rows_are_dropped(order, result, qapp):
    """الترقيم يعيد الحساب: الرافعة الثالثة في القائمة تصير الأولى في الجدول."""
    order.equipment[2].count, order.equipment[2].days = 1, 90
    order.equipment[5].count, order.equipment[5].days = 2, 30

    doc = _laid_out(printing.get("iso").build_html(order, result))
    rows = _body(doc, _table_titled(doc, "نوع الآلية"))
    assert [row[0] for row in rows] == ["1", "2"], rows
    assert [row[1] for row in rows] == ["رافعة", "شفل"], rows
    assert [row[2] for row in rows] == ["1", "2"], rows


def test_an_empty_table_keeps_one_blank_row(order, result, qapp):
    """لا مُدخَل إطلاقاً ← صفٌّ فارغ واحد، فلا يظهر رأسُ جدولٍ بلا جسم."""
    doc = _laid_out(printing.get("iso").build_html(order, result))
    rows = _body(doc, _table_titled(doc, "نوع العاملين"))
    assert rows == [["", "", "", ""]], rows


def test_days_without_a_count_do_not_resurrect_the_row(order, result, qapp):
    """العدد وحده يحكم — أيامٌ بلا عدد لا تُبقي السطر (بنصّك: «إذا كان العدد صفر»)."""
    order.staff[3].days = 45          # سائق: أيام بلا عدد
    doc = _laid_out(printing.get("iso").build_html(order, result))
    names = [row[1] for row in _body(doc, _table_titled(doc, "نوع العاملين"))]
    assert "سائق" not in names, names


# ═══════════════════ الخطّ العربي — ملاءمة ويندوز (ق-٥١) ═══════════════════


def test_the_font_falls_back_across_platforms():
    """أول خطّ عربي متاح فعلاً — لا اسم مثبَّت قد لا يوجد على جهاز المستخدم."""
    from printing.iso_form import available_arabic_font

    # ويندوز عادي بلا أوفيس: Tahoma مشحون مع كل نسخة وعربيّته ممتازة
    assert available_arabic_font(["Arial", "Tahoma", "Times New Roman"]) == "Tahoma"
    # ويندوز مع أوفيس: الخطّ الرسمي يتقدّم
    assert available_arabic_font(["Arial", "Tahoma", "Simplified Arabic"]) == "Simplified Arabic"
    # لينكس (بيئة التطوير)
    assert available_arabic_font(["DejaVu Sans", "FreeSerif"]) == "FreeSerif"
    # جهاز بلا أي خطّ من القائمة — لا انهيار، بل الافتراضي العامّ
    assert available_arabic_font(["Comic Sans MS"]) == "serif"


def test_building_html_without_a_qt_app_does_not_abort():
    """حارس انهيار: `QFontDatabase` بلا `QApplication` **تُسقط العملية بـ Abort**
    لا برفع استثناء. فبناء HTML خارج التطبيق يجب أن يعيد `serif` بلا مساس.

    الخلل كان من صنعي في ق-٥١ وكشفته الاختبارات قبل الإيداع.
    """
    import subprocess
    import sys

    code = (
        "from printing.iso_form import available_arabic_font;"
        "print(available_arabic_font())"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd="."
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "serif"


def test_no_linux_only_font_is_hard_coded_in_the_styles(qapp):
    """حارس ق-٥١: لا اسم خطّ مثبَّت في الأنماط — يُختار وقت التشغيل.

    كان `FreeSerif` مثبَّتاً وهو خطّ لينكس لا يُشحن مع ويندوز، فكان المستند
    على حاسبة المستخدم يسقط إلى Times New Roman.
    """
    from printing.iso_form import _CSS, styles

    assert "%FONT%" in _CSS                 # القالب يحمل موضع الاستبدال
    assert "%FONT%" not in styles()         # والناتج لا يحمله
    assert "font-family" in styles()


def test_both_templates_use_the_resolved_font(order, result, qapp):
    from printing.iso_form import available_arabic_font

    font = available_arabic_font()
    for key in ("iso", "audit"):
        html = printing.get(key).build_html(order, result)
        assert f"'{font}'" in html, key


def test_the_resolved_font_actually_supports_arabic(qapp):
    """**الحارس الحقيقي للخطّ (ق-٧٠):** الخطّ المختار يرسم العربية فعلاً.

    والاختبار الذي فوقه **تحصيلُ حاصل**: يقارن المُخرَج بالدالة نفسها، فلو
    أعادت خطّاً لاتينياً لطابقه المُخرَج ومرّ الاختبار — وهو بالضبط خلل ق-٥٣
    (عائلة فارغة حُلّت إلى `Bitstream Charter` فتقطّعت العربية على ويندوز).
    أثبتُّ ذلك بطفرة: صدّرتُ خطّاً لاتينياً في القائمة **فمرّ كلّ شيء**.

    وهذا يسأل `QFontDatabase` سؤالاً مباشراً: أيدعم هذا الخطّ العربية؟
    """
    from PyQt6.QtGui import QFontDatabase

    from printing.iso_form import ARABIC_FONTS, available_arabic_font

    installed = set(QFontDatabase.families())
    arabic = QFontDatabase.WritingSystem.Arabic

    chosen = available_arabic_font()
    if chosen != "serif":
        assert arabic in QFontDatabase.writingSystems(chosen), chosen

    # وكل اسم في القائمة — لا المختار على هذا الجهاز وحده: القائمة تُقرأ على
    # ويندوز أيضاً، وخطأٌ فيها لا يظهر هنا
    for name in ARABIC_FONTS:
        if name in installed:
            assert arabic in QFontDatabase.writingSystems(name), name


def test_audit_survives_a_labour_item_with_no_rate(order, underground_result_missing_rate):
    """كان القالب ينهار على أي أجر بلا سعر — الأجر None لا يُنسَّق كرقم (خ-١)."""
    html = printing.get("audit").build_html(order, underground_result_missing_rate)
    assert underground_result_missing_rate["أجور_مفقودة"]
    # **في خلية الجدول** لا في سطر التحذير: «بلا أجر» جزء من «بنود بلا أجر»،
    # فالبحث في الصفحة كلها كان يمرّ ولو طُبع الأجر المفقود صفراً (ق-٧٠)
    doc = _laid_out(html)
    labour = _table_headed(doc, "الفقرة")
    cells = [labour.cellAt(r, c).firstCursorPosition().block().text().strip()
             for r in range(1, labour.rows()) for c in range(labour.columns())]
    assert "بلا أجر" in cells, cells
    assert "0" not in cells, cells


def test_audit_warns_about_missing_rates_too(order, underground_result_missing_rate):
    html = printing.get("audit").build_html(order, underground_result_missing_rate)
    assert "بنود بلا أجر" in html


def test_audit_lists_the_project_segments(order, segmented_result):
    """جدول المقاطع مفتاح قراءة عمود «المصدر» الذي يذكر اسم المقطع."""
    html = printing.get("audit").build_html(order, segmented_result)
    assert "مقاطع المشروع" in html
    assert "المقطع الأول" in html
    assert "المقطع الثاني" in html


def test_the_simple_project_shows_no_segments_table(order, result):
    """المشروع بلا مقاطع مسمّاة لا يُضاف له جدول فارغ."""
    html = printing.get("audit").build_html(order, result)
    assert "مقاطع المشروع" not in html


@pytest.mark.parametrize("key", ["iso", "audit"])
def test_every_template_handles_a_segmented_project(key, order, segmented_result, tmp_path, qapp):
    path = printing.get(key).write_pdf(order, segmented_result, str(tmp_path / f"{key}.pdf"))
    assert (tmp_path / f"{key}.pdf").read_bytes().startswith(b"%PDF")


# ═══════════════════ الشبكة الأرضية 11 ك.ف ═══════════════════


def _underground_project():
    from engine.types import Project, Segment, SidewalkType, Underground11kV

    return Project(
        "مشروع أرضي",
        [
            Segment(
                "المقطع الأول",
                Underground11kV(
                    route_length_m=400, feeder_count=6, sidewalk_type=SidewalkType.EARTH,
                    straight_boxes=2, end_boxes_internal=1,
                ),
            ),
        ],
        street_crossing_secondary_m=30,
        street_crossing_main_m=10,
    )


@pytest.fixture(scope="module")
def underground_result():
    """مشروع أرضي كامل التسعير — 6 مغذيات صارت مسعّرة بعد ق-٤٤."""
    from engine.project import compute_project

    return compute_project(_underground_project(), load_catalog())


@pytest.fixture(scope="module")
def underground_result_missing_rate():
    """المشروع نفسه وقد حُذفت تعرفة الأعمال المدنية من نسخة الأسعار.

    لم يعد للأجر المفقود مصدر طبيعي بعد ق-٤٤ — كل عدد مغذيات صار مسعّراً.
    فيُحقَن الغياب في **نسخة** من الأسعار بدل بناء الاختبار على ثغرة مسدودة
    (نفس نهج ق-٣٦ مع المواد بلا سعر).
    """
    import copy

    from engine.project import compute_project

    catalog = copy.deepcopy(load_catalog())
    catalog["تعرفة_الأعمال_المدنية"] = {}
    return compute_project(_underground_project(), catalog)


@pytest.mark.parametrize("key", ["iso", "audit"])
def test_every_template_survives_an_underground_segment_with_a_missing_rate(
    key, order, underground_result_missing_rate, tmp_path, qapp
):
    """أهمّ اختبار: أجر بلا سعر لا يُسقط الطباعة (ق-٣٠، خ-١)."""
    path = printing.get(key).write_pdf(
        order, underground_result_missing_rate, str(tmp_path / f"{key}.pdf")
    )
    assert (tmp_path / f"{key}.pdf").read_bytes().startswith(b"%PDF")


def test_audit_prints_the_extended_civil_rate_not_a_blank(order, underground_result):
    """6 مغذيات: تعرفة ممتدّة مسعّرة ومفصَّلة إلى مكوّنين (ق-٤٤، ق-٤٧)."""
    html = printing.get("audit").build_html(order, underground_result)
    assert "الأعمال المدنية" in html
    assert not underground_result["أجور_مفقودة"]
    assert "حفر الخندق" in html and "إعادة المسار" in html
    assert "17,000" in html and "26,000" in html   # ترابي 6: 11,000+6,000 و20,000+6,000


def test_the_audit_sheet_states_which_price_version_produced_it(order, underground_result):
    """المدقّق يرى بأي أسعار حُسبت الورقة — ورقتان بنسختين مختلفتين ورقتان (ق-٤٠)."""
    html = printing.get("audit").build_html(order, underground_result)
    assert f"محسوبة بنسخة الأسعار: {underground_result['نسخة_الأسعار']}" in html
    assert underground_result["نسخة_الأسعار"]          # ليست فارغة


def test_a_result_without_a_price_version_is_flagged_not_hidden(order, underground_result):
    """نتيجة بلا نسخة أسعار تُطبع بتحذير ظاهر — لا بسطر فارغ صامت."""
    stripped = dict(underground_result)
    stripped["نسخة_الأسعار"] = ""
    html = printing.get("audit").build_html(order, stripped)
    assert "نسخة الأسعار غير مسجَّلة" in html


def test_audit_groups_the_labour_table_into_electrical_and_civil(underground_result, order):
    """جدول الأجور مبوّب: الكهربائية ثم المدنية، ولكل باب مجموعه (ق-٣٨)."""
    html = printing.get("audit").build_html(order, underground_result)
    electrical = html.index("الأعمال الكهربائية")
    civil = html.index("<b>الأعمال المدنية</b>")
    assert electrical < civil                      # الكهربائية هي الأصل فتتصدّر
    assert "مجموع الأعمال المدنية" in html
    assert "مجموع الأعمال الكهربائية" in html


def test_the_civil_subtotal_equals_the_sum_of_its_lines(underground_result, order):
    """حارس مالي: مجموع الباب المطبوع = مجموع أسطره فعلاً لا رقماً مستقلاً."""
    from engine.underground import CIVIL_GROUP

    html = printing.get("audit").build_html(order, underground_result)
    expected = sum(
        l.cost for l in underground_result["أجور_العمل"] if l.group == CIVIL_GROUP
    )
    assert f"مجموع الأعمال المدنية</td>\n      <td" not in html   # التنسيق قد يتغيّر
    assert f"{expected:,.0f}" in html


def test_a_single_group_prints_no_group_headers(order):
    """مشروع بلا أعمال مدنية: لا معنى لتبويب جدول من باب واحد."""
    from engine import load_catalog
    from engine.project import compute_project
    from engine.types import Equipment, Project, Segment
    from engine.equipment import TransformerSize, TransformerVoltage

    result = compute_project(
        Project(segments=[Segment("تجهيزات", Equipment(
            transformers={(TransformerVoltage.KV11, TransformerSize.KVA400): 1}))]),
        load_catalog(),
    )
    html = printing.get("audit").build_html(order, result)
    assert "الأعمال الكهربائية" not in html
    assert "مجموع أجور التنفيذ" in html
