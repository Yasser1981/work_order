# -*- coding: utf-8 -*-
"""نقطة تشغيل تطبيق أوامر العمل الكهربائية."""

import sys

from PyQt6.QtWidgets import QApplication

from engine import ensure_user_data, latest_catalog_version, load_catalog
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("نظام أوامر العمل الكهربائية")
    # ينسخ نسخة أسعار المصنع إلى مجلد المستخدم عند أول تشغيل (ق-٢٨)
    ensure_user_data()
    # النسخة تُمرَّر صريحةً لا تُستنتَج مرّتين: النافذة تحفظها مع أمر العمل (ق-٤٠)
    version = latest_catalog_version()
    window = MainWindow(load_catalog(version), version)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
