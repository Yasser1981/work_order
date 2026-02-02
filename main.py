import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel

def main():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Electrical Work Order System")
    window.resize(1024, 768)
    
    # Placeholder for the UI
    label = QLabel("Welcome! The application skeleton is ready.", window)
    label.move(50, 50)
    label.adjustSize()
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
