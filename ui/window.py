import sys
import subprocess
import re
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLineEdit, 
                             QListWidget, QListWidgetItem, QApplication, QLabel, QHBoxLayout)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QAction

from core.indexer import AppIndexer

class IndexerThread(QThread):
    finished = pyqtSignal(list)

    def run(self):
        indexer = AppIndexer()
        apps = indexer.index_apps()
        self.finished.emit(apps)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Dialog hint helps tiling WMs (like i3) treat it as a floating window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Dimensions (Increased width for details panel)
        self.resize(850, 450)
        self.center()

        # Central Widget
        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)
        
        # Main Layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Search Bar (Top)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search apps, 'cb' for clipboard, 'g' for google...")
        self.search_bar.textChanged.connect(self.filter_items)
        self.search_bar.returnPressed.connect(self.execute_selected)
        self.main_layout.addWidget(self.search_bar)

        # Content Layout (Split View)
        self.content_layout = QHBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.main_layout.addLayout(self.content_layout)

        # Results List (Left)
        self.results_list = QListWidget()
        self.results_list.setIconSize(QSize(32, 32))
        self.results_list.itemActivated.connect(self.execute_selected)
        self.results_list.currentItemChanged.connect(self.update_details)
        self.content_layout.addWidget(self.results_list, stretch=6)

        # Details Panel (Right)
        self.details_panel = QWidget()
        self.details_panel.setObjectName("DetailsPanel")
        self.setup_details_panel()
        self.content_layout.addWidget(self.details_panel, stretch=4)

        # Data
        self.all_apps = []
        self.indexer = AppIndexer() # Helper for direct calls
        
        # Start Indexing
        self.indexer_thread = IndexerThread()
        self.indexer_thread.finished.connect(self.on_indexing_finished)
        self.indexer_thread.start()

        # Shortcuts
        self.escape_action = QAction(self)
        self.escape_action.setShortcut("Esc")
        self.escape_action.triggered.connect(self.close)
        self.addAction(self.escape_action)

        # Event Filter for Search Bar Navigation
        self.search_bar.installEventFilter(self)

    def setup_details_panel(self):
        layout = QVBoxLayout(self.details_panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Title
        self.details_title = QLabel("")
        self.details_title.setObjectName("DetailsTitle")
        self.details_title.setWordWrap(True)
        layout.addWidget(self.details_title)

        # Description
        self.details_desc = QLabel("")
        self.details_desc.setObjectName("DetailsDesc")
        self.details_desc.setWordWrap(True)
        layout.addWidget(self.details_desc)
        
        # Spacer
        layout.addSpacing(10)

        # Meta/Command
        self.details_meta = QLabel("")
        self.details_meta.setObjectName("DetailsMeta")
        self.details_meta.setWordWrap(True)
        layout.addWidget(self.details_meta)
        
        # Fill rest
        layout.addStretch()

    def update_details(self, current, previous):
        if not current:
            self.details_title.setText("")
            self.details_desc.setText("")
            self.details_meta.setText("")
            return

        data = current.data(Qt.ItemDataRole.UserRole)
        
        self.details_title.setText(data['name'])
        self.details_desc.setText(data.get('description', 'No description'))
        
        # Show Exec command or URL, truncated if too long
        exec_cmd = data.get('exec', '')
        if len(exec_cmd) > 100:
            exec_cmd = exec_cmd[:97] + "..."
        self.details_meta.setText(f"> {exec_cmd}")

    def center(self):
        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def eventFilter(self, obj, event):
        if obj == self.search_bar and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self.navigate_list(1)
                return True
            elif key == Qt.Key.Key_Up:
                self.navigate_list(-1)
                return True
        return super().eventFilter(obj, event)

    def navigate_list(self, direction):
        current = self.results_list.currentRow()
        count = self.results_list.count()
        if count == 0:
            return
        
        next_row = current + direction
        if 0 <= next_row < count:
            self.results_list.setCurrentRow(next_row)

    def on_indexing_finished(self, apps):
        self.all_apps = apps
        self.update_list(apps)

    def update_list(self, apps):
        self.results_list.clear()
        for app in apps:
            # Determine icon (if it's a theme icon string or fallback)
            icon_name = app.get('icon', 'application-x-executable')
            if app['type'] == 'Calculator':
                icon = QIcon.fromTheme("accessories-calculator")
            elif app['type'] == 'WebSearch':
                icon = QIcon.fromTheme("web-browser", QIcon.fromTheme("internet-web-browser"))
            elif app['type'] == 'Clipboard':
                icon = QIcon.fromTheme("edit-paste")
            else:
                icon = QIcon.fromTheme(icon_name)
            
            item = QListWidgetItem(icon, app['name'])
            item.setData(Qt.ItemDataRole.UserRole, app)
            # Add description as tooltip or secondary text
            item.setToolTip(app.get('description', '')) 
            self.results_list.addItem(item)
        
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

    def filter_items(self, text):
        items_to_show = []
        lower_text = text.lower()
        
        # 0. Check for Clipboard Mode
        if lower_text == "cb" or lower_text.startswith("cb "):
            history = self.indexer.get_clipboard_history()
            # Optional: Filter history if they type "cb something"
            query = lower_text[2:].strip()
            if query:
                history = [h for h in history if query in h['exec'].lower()]
            
            if not history:
                items_to_show.append({
                    'name': "Clipboard History is empty",
                    'exec': "",
                    'icon': 'edit-paste',
                    'description': 'Copy something first!',
                    'type': 'Info'
                })
            else:
                items_to_show.extend(history)
            
            self.update_list(items_to_show)
            return

        # 1. Check for Math Expression
        # Allow: digits, whitespace, ., +, -, *, /, %, (, )
        if re.match(r'^[\d\s\.\+\-\*\/\%\(\)]+$', text) and any(op in text for op in "+-*/%"):
            try:
                # Safe eval
                result = eval(text, {"__builtins__": None}, {})
                items_to_show.append({
                    'name': f"= {result}",
                    'exec': str(result),
                    'icon': 'accessories-calculator',
                    'description': 'Copy to clipboard',
                    'type': 'Calculator'
                })
            except:
                pass # Invalid math, ignore

        # 2. Check for Web Search Prefixes
        if text.startswith("g "):
            query = text[2:].strip()
            if query:
                items_to_show.append({
                    'name': f"Search Google: {query}",
                    'exec': f"https://www.google.com/search?q={query}",
                    'icon': 'web-browser',
                    'description': 'Open in default browser',
                    'type': 'WebSearch'
                })
        elif text.startswith("gh "):
            query = text[3:].strip()
            if query:
                items_to_show.append({
                    'name': f"Search GitHub: {query}",
                    'exec': f"https://github.com/search?q={query}",
                    'icon': 'web-browser',
                    'description': 'Open in default browser',
                    'type': 'WebSearch'
                })
        elif text.startswith("yt "):
            query = text[3:].strip()
            if query:
                items_to_show.append({
                    'name': f"Search YouTube: {query}",
                    'exec': f"https://www.youtube.com/results?search_query={query}",
                    'icon': 'web-browser',
                    'description': 'Open in default browser',
                    'type': 'WebSearch'
                })

        # 3. Filter Apps & Scripts
        items_to_show.extend([
            app for app in self.all_apps 
            if lower_text in app['name'].lower() or lower_text in app.get('description', '').lower()
        ])
        
        self.update_list(items_to_show)

    def execute_selected(self):
        current_item = self.results_list.currentItem()
        if current_item:
            app_data = current_item.data(Qt.ItemDataRole.UserRole)
            self.launch_app(app_data)

    def launch_app(self, app_data):
        if app_data.get('type') == 'Info':
            return

        if app_data['type'] in ('Calculator', 'Clipboard'):
            clipboard = QApplication.clipboard()
            clipboard.setText(app_data['exec'])
            print(f"Copied to clipboard: {app_data['exec'][:20]}...")
            self.close()
        elif app_data['type'] == 'WebSearch':
            print(f"Opening URL: {app_data['exec']}")
            # xdg-open works on most Linux systems to open default browser
            subprocess.Popen(['xdg-open', app_data['exec']], start_new_session=True)
            self.close()
        else:
            print(f"Launching: {app_data['name']}")
            try:
                subprocess.Popen(app_data['exec'], shell=True, start_new_session=True)
                self.close()
            except Exception as e:
                print(f"Error launching {app_data['name']}: {e}")
