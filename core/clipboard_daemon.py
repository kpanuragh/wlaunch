#!/usr/bin/env python3
import sys
import time
import json
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QClipboard

HISTORY_FILE = os.path.expanduser("~/.config/wlaunch/clipboard_history.json")
MAX_HISTORY = 50

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

class ClipboardDaemon:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.clipboard = self.app.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.history = load_history()
        self.last_text = ""
        
        # Initialize last_text from history if available
        if self.history:
            self.last_text = self.history[0]

        print("wlaunch-daemon started. Monitoring clipboard...")

    def on_clipboard_change(self):
        text = self.clipboard.text()
        
        # Ignore empty or duplicate of immediate last item
        if not text or text == self.last_text:
            return

        print(f"Captured: {text[:20]}...")
        
        # Update History
        # Remove if exists elsewhere to bump to top
        if text in self.history:
            self.history.remove(text)
        
        self.history.insert(0, text)
        self.history = self.history[:MAX_HISTORY]
        self.last_text = text
        
        save_history(self.history)

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    daemon = ClipboardDaemon()
    daemon.run()
