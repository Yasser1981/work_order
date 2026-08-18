# -*- coding: utf-8 -*-
"""نقطة تشغيل تطبيق أوامر العمل الكهربائية."""

import sys

from PyQt6.QtWidgets import QApplication

from engine import load_catalog
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("نظام أوامر العمل الكهربائية")
    window = MainWindow(load_catalog())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
