# -*- coding: utf-8 -*-
"""إعداد بيئة الاختبارات."""

import os

# اختبارات الواجهة والطباعة تعمل بلا شاشة
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """كائن QApplication واحد للجلسة كلها.

    يجب الاحتفاظ بمرجع له طوال الجلسة — تركه لجامع المهملات يُسقط العملية كلها
    عند أول استخدام لاحق لـ Qt (انهيار وليس استثناء).
    """
    pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
