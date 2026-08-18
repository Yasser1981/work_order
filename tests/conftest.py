# -*- coding: utf-8 -*-
"""إعداد بيئة الاختبارات."""

import os

# اختبارات الواجهة تعمل بلا شاشة
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
