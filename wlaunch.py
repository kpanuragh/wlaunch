#!/usr/bin/env python3
import sys
import os
from PyQt6.QtWidgets import QApplication
from ui.window import MainWindow

def load_stylesheet(app):
    """Loads the QSS stylesheet."""
    try:
        with open("styles.qss", "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Warning: styles.qss not found.")

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("wlaunch")
    
    # Load Styles
    load_stylesheet(app)

    window = MainWindow()
    window.show()

    # Ensure window is focused and on top (Linux/i3 specific hints sometimes needed)
    window.activateWindow()
    window.raise_()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
