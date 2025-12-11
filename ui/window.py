import sys
import subprocess
import re
import os
import time
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLineEdit, 
                             QListWidget, QListWidgetItem, QApplication, QLabel, QHBoxLayout, QTextBrowser)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QIcon, QAction, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from core.indexer import AppIndexer
from core.ai import AIHandler
from core.emojis import search_emojis
from core.files import FileSearcher

class IndexerThread(QThread):
    finished = pyqtSignal(list)

    def run(self):
        indexer = AppIndexer()
        apps = indexer.index_apps()
        self.finished.emit(apps)

class AIThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self, prompt, handler):
        super().__init__()
        self.prompt = prompt
        self.handler = handler

    def run(self):
        response = self.handler.ask(self.prompt)
        self.finished.emit(response)

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
        self.search_bar.setPlaceholderText("Search apps, 'cb' for clipboard, 'g' for google, 'ask' for AI, 'e ' for emoji, 'f ' for files...")
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
        self.chat_history_items = []
        self.indexer = AppIndexer() # Helper for direct calls
        self.file_searcher = FileSearcher()
        self.ai_handler = AIHandler()
        self.ai_thread = None
        
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

        # Image Preview Label
        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setMinimumHeight(200)
        self.image_preview.hide()
        layout.addWidget(self.image_preview)

        # Video Preview Widget
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(200)
        self.video_widget.hide()
        layout.addWidget(self.video_widget)

        # Media Player
        self.audio_output = QAudioOutput()
        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        # Description
        self.details_desc = QTextBrowser()
        self.details_desc.setObjectName("DetailsDesc")
        self.details_desc.setReadOnly(True)
        self.details_desc.setOpenExternalLinks(True)
        layout.addWidget(self.details_desc)
        
        # Spacer - removed to allow QLabel to expand fully

        # Meta/Command
        self.details_meta = QLabel("")
        self.details_meta.setObjectName("DetailsMeta")
        self.details_meta.setWordWrap(True)
        layout.addWidget(self.details_meta)
        
        # Fill rest - removed to allow QLabel to expand fully


    def update_details(self, current, previous):
        # Reset Previews
        self.image_preview.hide()
        self.video_widget.hide()
        self.media_player.stop()
        self.details_desc.show()

        if not current:
            self.details_title.setText("")
            self.details_desc.setText("")
            self.details_meta.setText("")
            return

        data = current.data(Qt.ItemDataRole.UserRole)
        
        self.details_title.setText(data['name'])
        
        item_type = data.get('type')
        
        if item_type == 'Image':
            pixmap = QPixmap(data['exec'])
            if not pixmap.isNull():
                # Scale nicely
                scaled = pixmap.scaled(self.image_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.image_preview.setPixmap(scaled)
                self.image_preview.show()
                self.details_desc.hide()
            else:
                self.details_desc.setText("Could not load image preview.")
                self.details_desc.show()
        
        elif item_type == 'Video':
            self.media_player.setSource(QUrl.fromLocalFile(data['exec']))
            self.video_widget.show()
            self.media_player.play()
            self.details_desc.hide()
            
        else:
            self.details_desc.setText(data.get('description', 'No description'))
            self.details_desc.show()
        
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
            elif app['type'] == 'AI':
                icon = QIcon.fromTheme("preferences-system", QIcon.fromTheme("system-help"))
            elif app['type'] == 'Emoji':
                icon = QIcon.fromTheme("face-smile")
            elif app['type'] in ('File', 'Image', 'Video'):
                icon = QIcon.fromTheme(icon_name)
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

        # Emoji Mode
        if lower_text.startswith("e "):
            query = lower_text[2:].strip()
            if query:
                results = search_emojis(query)
                for res in results:
                    items_to_show.append({
                        'name': f"{res['char']} {res['name']}",
                        'exec': res['char'],
                        'icon': 'face-smile', # Fallback icon
                        'description': res['description'],
                        'type': 'Emoji'
                    })
            else:
                items_to_show.append({
                    'name': "Search Emojis...",
                    'exec': "",
                    'icon': 'face-smile',
                    'description': 'Type e.g., "e smile"',
                    'type': 'Info'
                })
            self.update_list(items_to_show)
            return

        # File Search Mode
        if lower_text.startswith("f "):
            query = lower_text[2:].strip()
            if len(query) >= 2:
                results = self.file_searcher.search(query)
                for res in results:
                    icon_name = 'text-x-generic'
                    if res['type'] == 'Image':
                        icon_name = 'image-x-generic'
                    elif res['type'] == 'Video':
                        icon_name = 'video-x-generic'
                    
                    items_to_show.append({
                        'name': res['name'],
                        'exec': res['path'],
                        'icon': icon_name,
                        'description': res['path'],
                        'type': res['type']
                    })
            else:
                 items_to_show.append({
                    'name': "Search Files...",
                    'exec': "",
                    'icon': 'system-search',
                    'description': 'Type at least 2 chars to search...',
                    'type': 'Info'
                })
            self.update_list(items_to_show)
            return

        # Chat History Mode
        if lower_text == "chat" or lower_text.startswith("chat "):
            if not self.chat_history_items:
                items_to_show.append({
                    'name': "Chat History is empty",
                    'exec': "",
                    'icon': 'preferences-system',
                    'description': 'Ask something first!',
                    'type': 'Info'
                })
            else:
                # Reverse to show newest first
                items_to_show.extend(reversed(self.chat_history_items))
            
            self.update_list(items_to_show)
            return

        # AI Mode
        if lower_text.startswith("ask "):
            query = text[4:].strip()
            if query:
                 items_to_show.append({
                    'name': f"Ask AI: {query}",
                    'exec': query,
                    'icon': 'preferences-system',
                    'description': 'Send to Gemini AI',
                    'type': 'AI'
                })
            else:
                 items_to_show.append({
                    'name': "Ask AI...",
                    'exec': "",
                    'icon': 'preferences-system',
                    'description': 'Type your question',
                    'type': 'Info'
                })
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

        if app_data['type'] == 'AI':
            self.details_title.setText("Thinking...")
            self.details_desc.setText("Waiting for Gemini API response...")
            self.details_meta.setText("")
            
            # Disable interaction while waiting? For now just visual feedback.
            self.ai_thread = AIThread(app_data['exec'], self.ai_handler)
            self.ai_thread.finished.connect(self.on_ai_response)
            self.ai_thread.start()
            return

        if app_data['type'] in ('Calculator', 'Clipboard', 'Emoji'):
            clipboard = QApplication.clipboard()
            clipboard.setText(app_data['exec'])
            # Ensure the clipboard event is processed before the app closes
            QApplication.processEvents()
            time.sleep(0.1) # Give time for clipboard manager to grab it
            print(f"Copied to clipboard: {app_data['exec'][:20]}...")
            self.close()
        elif app_data['type'] == 'WebSearch' or app_data['type'] in ('File', 'Image', 'Video'):
            print(f"Opening: {app_data['exec']}")
            # xdg-open works on most Linux systems to open default browser/files
            subprocess.Popen(['xdg-open', app_data['exec']], start_new_session=True)
            self.close()
        else:
            print(f"Launching: {app_data['name']}")
            try:
                subprocess.Popen(app_data['exec'], shell=True, start_new_session=True)
                self.close()
            except Exception as e:
                print(f"Error launching {app_data['name']}: {e}")

    def on_ai_response(self, response):
        self.details_title.setText("AI Response")
        self.details_desc.setText(response)
        
        # We can add an option to copy the response to clipboard
        # Re-using the list item to allow "Enter" to copy result
        # If there's an error in the response, don't show the copy option.
        if response.startswith("Error:"):
            # If an error occurred, just display it and don't offer to copy.
            self.search_bar.setText("Error occurred during AI request.")
            self.update_list([])
            return

        # Save to history
        prompt = self.ai_thread.prompt if self.ai_thread else "Unknown Question"
        history_item = {
            'name': f"Q: {prompt}",
            'exec': response,
            'icon': 'preferences-system',
            'description': response,
            'type': 'Clipboard' # Allow copying from history
        }
        self.chat_history_items.append(history_item)

        result_item = {
            'name': "Copy AI Answer",
            'exec': response,
            'icon': 'edit-paste',
            'description': response,
            'type': 'Clipboard'
        }
        self.update_list([result_item])
