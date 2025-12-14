import sys
import subprocess
import re
import os
import time
import signal
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLineEdit,
                             QListWidget, QListWidgetItem, QApplication, QLabel, QHBoxLayout, QTextBrowser, QInputDialog, QMessageBox, QDialog, QPushButton, QCheckBox)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QIcon, QAction, QPixmap, QClipboard
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from core.indexer import AppIndexer
from core.ai import AIHandler
from core.emojis import search_emojis
from core.files import FileSearcher
from core.bitwarden import BitwardenAPI
from core.bitwarden_api import BitwardenAPIClient
from core.bitwarden_full import BitwardenFullClient
from core.windows import WindowSwitcher
from core.recent_files import RecentFileBrowser
from core.converter import UnitConverter
from core.processes import ProcessManager
from core.network import NetworkManager

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

class WifiScanThread(QThread):
    finished = pyqtSignal(list)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def run(self):
        networks = self.manager.scan()
        self.finished.emit(networks)

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
        self.search_bar.setPlaceholderText("Search apps, 'w' for windows, 'wifi' for network, 'r' for recent, 'ps' for processes, 'bw' for passwords, 'ask' for AI...")
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
        self.results_list.itemClicked.connect(self.on_item_clicked)  # Single click handler
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
        self.bw_api = None # Lazy loaded
        self.window_switcher = WindowSwitcher()
        self.recent_files = RecentFileBrowser()
        self.converter = UnitConverter()
        self.process_manager = ProcessManager()
        self.network_manager = NetworkManager()
        self.wifi_thread = None
        self.wifi_cache = []
        self.last_wifi_scan = 0
        
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
            elif app['type'] in ('BitwardenUnlock', 'BitwardenCopy', 'BitwardenCopyUsername', 'BitwardenLogin'):
                if app['type'] == 'BitwardenUnlock':
                    icon = QIcon.fromTheme("auth-sim-locked")
                elif app['type'] == 'BitwardenLogin':
                    icon = QIcon.fromTheme("dialog-password")
                elif app['type'] == 'BitwardenCopyUsername':
                    icon = QIcon.fromTheme("avatar-default")
                else:
                    icon = QIcon.fromTheme("emblem-locked")
            elif app['type'] == 'BitwardenTOTP':
                icon = QIcon.fromTheme("dialog-password")
            elif app['type'] == 'BitwardenNote':
                icon = QIcon.fromTheme("text-x-generic")
            elif app['type'] == 'BitwardenCard':
                icon = QIcon.fromTheme("payment-card")
            elif app['type'] == 'BitwardenGenerate':
                icon = QIcon.fromTheme("password-generate")
            elif app['type'] == 'Window':
                icon = QIcon.fromTheme("preferences-system-windows")
            elif app['type'] == 'Process':
                icon = QIcon.fromTheme("utilities-system-monitor")
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
        
        # 0. Bitwarden Mode
        if lower_text == "bw" or lower_text.startswith("bw "):
            if self.bw_api is None:
                # Use full client with master password support
                self.bw_api = BitwardenFullClient()
                self.bw_mode = "full"

            status = self.bw_api.get_status()
            print(f"DEBUG filter_items: Bitwarden status={status}")

            if status == "logged_out":
                 items_to_show.append({
                    'name': "Bitwarden: Login Required",
                    'exec': "",
                    'icon': 'dialog-password',
                    'description': 'Press Enter to login with email and master password',
                    'type': 'BitwardenLogin'
                })
            elif status == "locked":
                 items_to_show.append({
                    'name': "Unlock Bitwarden Vault",
                    'exec': "",
                    'icon': 'auth-sim-locked',
                    'description': 'Press Enter to provide Master Password',
                    'type': 'BitwardenUnlock'
                })
            elif status == "unlocked":
                # Sub-modes
                if lower_text == "bw gen":
                    items_to_show.append({
                        'name': "Generate Password",
                        'exec': "",
                        'icon': 'password-generate',
                        'description': 'Press Enter to generate a secure password',
                        'type': 'BitwardenGenerate'
                    })
                elif lower_text.startswith("bw totp "):
                    query = lower_text[8:].strip()
                    results = self.bw_api.search_items_advanced(query, item_type=1)  # Only logins
                    for res in results:
                        if res.get('has_totp'):
                            item_data = {
                                'name': f"{res['name']} - TOTP",
                                'exec': "",
                                'item_id': res['id'],
                                'icon': 'dialog-password',
                                'description': f"User: {res.get('username', 'N/A')}",
                                'type': 'BitwardenTOTP'
                            }
                            # In API mode, include the TOTP seed
                            if hasattr(self, 'bw_mode') and self.bw_mode == "api":
                                item_data['totp_seed'] = res.get('totp_seed', '')
                            items_to_show.append(item_data)
                elif lower_text.startswith("bw note "):
                    query = lower_text[8:].strip()
                    results = self.bw_api.search_items_advanced(query, item_type=2)  # Only notes
                    for res in results:
                        items_to_show.append({
                            'name': res['name'],
                            'exec': res.get('notes', ''),
                            'icon': 'text-x-generic',
                            'description': res.get('notes', '')[:60] + '...' if len(res.get('notes', '')) > 60 else res.get('notes', ''),
                            'type': 'BitwardenNote'
                        })
                elif lower_text.startswith("bw card "):
                    query = lower_text[8:].strip()
                    results = self.bw_api.search_items_advanced(query, item_type=3)  # Only cards
                    for res in results:
                        items_to_show.append({
                            'name': f"{res['name']} - {res.get('number_masked', '')}",
                            'exec': res.get('number_full', ''),
                            'icon': 'payment-card',
                            'description': f"{res.get('cardholder', '')} | Exp: {res.get('exp_month', '')}/{res.get('exp_year', '')}",
                            'type': 'BitwardenCard'
                        })
                else:
                    query = lower_text[2:].strip()
                    if query:
                        results = self.bw_api.search_items(query)
                        for res in results:
                            # Only show login items with both username and password options
                            if res.get('type_name') == 'login':
                                # Password copy option
                                items_to_show.append({
                                    'name': f"🔑 {res['name']} - Password",
                                    'exec': res.get('password', ''),
                                    'username': res.get('username', ''),
                                    'url': res.get('url', ''),
                                    'icon': 'emblem-locked',
                                    'description': f"Copy password • User: {res.get('username', 'N/A')}",
                                    'type': 'BitwardenCopy'
                                })
                                # Username copy option
                                if res.get('username'):
                                    items_to_show.append({
                                        'name': f"👤 {res['name']} - Username",
                                        'exec': res.get('username', ''),
                                        'username': res.get('username', ''),
                                        'url': res.get('url', ''),
                                        'icon': 'avatar-default',
                                        'description': f"Copy username: {res.get('username', '')}",
                                        'type': 'BitwardenCopyUsername'
                                    })
                    else:
                        items_to_show.append({
                            'name': "Search Bitwarden...",
                            'exec': "",
                            'icon': 'system-search',
                            'description': 'Type "bw <query>" or "bw gen", "bw totp <query>", "bw note <query>", "bw card <query>"',
                            'type': 'Info'
                        })
            else:
                 items_to_show.append({
                    'name': f"Bitwarden Status: {status}",
                    'exec': "",
                    'icon': 'dialog-warning',
                    'description': 'Check bw serve status',
                    'type': 'Info'
                })

            self.update_list(items_to_show)
            return

        # Window Switcher Mode
        if lower_text == "w" or lower_text.startswith("w "):
            query = lower_text[2:].strip() if len(lower_text) > 2 else ""
            results = self.window_switcher.search(query)
            items_to_show.extend(results)
            self.update_list(items_to_show)
            return

        # System Commands
        system_cmds = {
            'shutdown': {'cmd': 'systemctl poweroff', 'icon': 'system-shutdown', 'desc': 'Power off the system'},
            'reboot': {'cmd': 'systemctl reboot', 'icon': 'system-reboot', 'desc': 'Reboot the system'},
            'suspend': {'cmd': 'systemctl suspend', 'icon': 'system-suspend', 'desc': 'Suspend the system'},
            'lock': {'cmd': 'loginctl lock-session', 'icon': 'system-lock-screen', 'desc': 'Lock the screen'},
            'logout': {'cmd': 'i3-msg exit', 'icon': 'system-log-out', 'desc': 'Exit i3 session'}
        }
        
        matched_sys_cmds = []
        for cmd_name, cmd_data in system_cmds.items():
            if cmd_name.startswith(lower_text):
                 matched_sys_cmds.append({
                    'name': cmd_name.capitalize(),
                    'exec': cmd_data['cmd'],
                    'icon': cmd_data['icon'],
                    'description': cmd_data['desc'],
                    'type': 'System'
                })
        
        if matched_sys_cmds:
            items_to_show.extend(matched_sys_cmds)
            # If we have an exact match, we might want to prioritize it, but appending works too.
            # If the user typed "shut", it matches "shutdown".

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

        # Recent Files Mode
        if lower_text == "r" or lower_text.startswith("r "):
            query = lower_text[2:].strip()
            results = self.recent_files.search(query)

            if not results:
                items_to_show.append({
                    'name': "No recent files found",
                    'exec': "",
                    'icon': 'document-open-recent',
                    'description': 'Open some files first!',
                    'type': 'Info'
                })
            else:
                items_to_show.extend(results)

            self.update_list(items_to_show)
            return

        # Process Manager Mode
        if lower_text == "ps" or lower_text.startswith("ps "):
            query = lower_text[2:].strip() if len(lower_text) > 2 else ""
            results = self.process_manager.search(query)

            if not results:
                items_to_show.append({
                    'name': "No processes found",
                    'exec': "",
                    'icon': 'utilities-system-monitor',
                    'description': 'Try a different search',
                    'type': 'Info'
                })
            else:
                items_to_show.extend(results)

            self.update_list(items_to_show)
            return

        # Network/Wifi Mode
        if lower_text == "wifi" or lower_text.startswith("wifi "):
            if not self.network_manager.is_available():
                items_to_show.append({
                    'name': "Network Manager Unavailable",
                    'exec': "",
                    'icon': 'network-error',
                    'description': 'No compatible network backend (nmcli) found.',
                    'type': 'Info'
                })
                self.update_list(items_to_show)
                return

            # Add toggle option
            items_to_show.append({
                'name': "Toggle Wifi On/Off",
                'exec': "toggle",
                'icon': 'network-wireless',
                'description': 'Turn wifi radio on or off',
                'type': 'WifiToggle'
            })

            # Handle Scanning
            current_time = time.time()
            if not self.wifi_cache or (current_time - self.last_wifi_scan > 10 and lower_text == "wifi"):
                 # Start scan if cache is old or empty, but only if explicitly asked (to avoid spamming)
                 if self.wifi_thread is None or not self.wifi_thread.isRunning():
                    self.wifi_thread = WifiScanThread(self.network_manager)
                    self.wifi_thread.finished.connect(self.on_wifi_scan_finished)
                    self.wifi_thread.start()
                    
                    # Show scanning indicator if cache is empty
                    if not self.wifi_cache:
                        items_to_show.append({
                            'name': "Scanning for networks...",
                            'exec': "",
                            'icon': 'network-wireless-acquiring',
                            'description': 'Please wait...',
                            'type': 'Info'
                        })
            
            # Show Cached Results
            if self.wifi_cache:
                for net in self.wifi_cache:
                    # Filter if query provided
                    query = lower_text[4:].strip()
                    if query and query not in net['ssid'].lower():
                        continue
                        
                    desc = f"Signal: {net['signal']}% | Security: {net['security']}"
                    
                    if net['in_use']:
                        # Fetch IP details for connected network
                        details = self.network_manager.get_connection_details()
                        ip_info = f" | IP: {details.get('ip', 'N/A')} | GW: {details.get('gateway', 'N/A')}"
                        desc = "CONNECTED" + ip_info + " | " + desc
                    
                    items_to_show.append({
                        'name': net['ssid'],
                        'exec': net['ssid'],
                        'icon': 'network-wireless' if not net['in_use'] else 'network-wireless-connected',
                        'description': desc,
                        'type': 'WifiConnect',
                        'security': net['security'],
                        'in_use': net['in_use']
                    })

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

        # 1. Check for Unit/Currency Conversion
        conversion_result = self.converter.detect_and_convert(text)
        if conversion_result:
            items_to_show.append({
                'name': conversion_result['result'],
                'exec': conversion_result['value'],
                'icon': 'accessories-calculator',
                'description': conversion_result['explanation'],
                'type': 'Calculator'
            })

        # 2. Check for Math Expression
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

        # 3. Check for Web Search Prefixes
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

    def on_wifi_scan_finished(self, networks):
        self.wifi_cache = networks
        self.last_wifi_scan = time.time()
        # Refresh list if user is still in wifi mode
        if self.search_bar.text().startswith("wifi"):
            self.filter_items(self.search_bar.text())

    def on_item_clicked(self, item):
        """Handle single click on item"""
        print(f"DEBUG on_item_clicked: item={item.text() if item else None}")
        # For most items, single click just selects (updates details)
        # For special items like Bitwarden unlock, we want immediate action
        if item:
            app_data = item.data(Qt.ItemDataRole.UserRole)
            if app_data:
                item_type = app_data.get('type')
                print(f"DEBUG: Clicked item type={item_type}")
                # Immediate action items (single click executes)
                if item_type in ('BitwardenUnlock', 'BitwardenLogin'):
                    print(f"DEBUG: Executing {item_type} on single click")
                    self.launch_app(app_data)

    def execute_selected(self):
        """Handle activation (double-click or Enter key)"""
        print("DEBUG execute_selected called")
        current_item = self.results_list.currentItem()
        if current_item:
            app_data = current_item.data(Qt.ItemDataRole.UserRole)
            if app_data:
                print(f"DEBUG execute_selected: type={app_data.get('type')}")
                self.launch_app(app_data)

    def launch_app(self, app_data):
        print(f"DEBUG launch_app: type={app_data.get('type') if app_data else 'None'}")

        if not app_data:
            print("DEBUG: app_data is None, returning")
            return

        if app_data.get('type') == 'Info':
            print("DEBUG: type is Info, returning")
            return

        # Handle Bitwarden unlock FIRST before other types
        if app_data['type'] == 'WifiToggle':
            # This is a bit simplistic, assumes we want to toggle. 
            # Ideally we check status first. For now, let's just show info or try to toggle on.
            # Actually, let's just try to restart the network manager or something?
            # Or asking user what to do.
            # Let's just run nmcli radio wifi
            # We can't easily know current state without another command.
            # Let's assume toggle ON for now or offer choice.
            reply = QMessageBox.question(
                self, "Wifi Toggle", "Turn Wifi ON?", 
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            enable = (reply == QMessageBox.StandardButton.Yes)
            success, msg = self.network_manager.toggle_wifi(enable)
            QMessageBox.information(self, "Wifi", msg)
            return

        if app_data['type'] == 'WifiConnect':
            ssid = app_data['name']
            if app_data.get('in_use'):
                QMessageBox.information(self, "Wifi", f"Already connected to {ssid}")
                return

            password = None
            security = app_data.get('security', '').lower()
            if security and security != '--':
                from PyQt6.QtWidgets import QLineEdit as LineEdit
                text, ok = QInputDialog.getText(self, "Connect to Wifi", f"Password for {ssid}:", LineEdit.EchoMode.Password)
                if ok:
                    password = text
                else:
                    return # Cancelled
            
            self.details_title.setText("Connecting...")
            self.details_desc.setText(f"Connecting to {ssid}...")
            QApplication.processEvents()
            
            success, msg = self.network_manager.connect(ssid, password)
            
            if success:
                self.details_title.setText("Connected")
                self.details_desc.setText(f"Successfully connected to {ssid}")
                QMessageBox.information(self, "Success", f"Connected to {ssid}")
                self.close()
            else:
                self.details_title.setText("Connection Failed")
                self.details_desc.setText(msg)
                QMessageBox.warning(self, "Error", f"Failed to connect: {msg}")
            return

        if app_data['type'] == 'BitwardenUnlock':
            print("DEBUG: BitwardenUnlock triggered - showing password dialog")
            from PyQt6.QtWidgets import QLineEdit as LineEdit
            text, ok = QInputDialog.getText(self, "Bitwarden Unlock", "Enter Master Password:", LineEdit.EchoMode.Password)
            print(f"DEBUG: Dialog closed - ok={ok}, has_text={len(text) > 0 if text else False}")
            if ok and text:
                print("DEBUG: Attempting unlock...")
                success, msg = self.bw_api.unlock(text)
                print(f"DEBUG: Unlock result - success={success}, msg={msg}")
                if success:
                    self.search_bar.setText("bw ")
                    self.filter_items("bw ")
                else:
                    QMessageBox.warning(self, "Unlock Failed", msg)
            return

        if app_data['type'] == 'Window':
            print(f"Focusing window: {app_data['name']}")
            subprocess.Popen(['i3-msg', f'[con_id="{app_data["window_id"]}"] focus'], start_new_session=True)
            self.close()
            return

        if app_data['type'] == 'Process':
            pid = app_data['pid']
            name = app_data['name']

            # Show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Kill Process",
                f"Kill process:\n{name}\n\nPID: {pid}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"Sent SIGTERM to process {pid}")
                    # Refresh the list
                    self.search_bar.setText("ps ")
                    self.filter_items("ps ")
                except PermissionError:
                    self.details_title.setText("Permission Denied")
                    self.details_desc.setText(f"Cannot kill process {pid}. You may not have permission.")
                except ProcessLookupError:
                    self.details_title.setText("Process Not Found")
                    self.details_desc.setText(f"Process {pid} no longer exists.")
                except Exception as e:
                    self.details_title.setText("Error")
                    self.details_desc.setText(f"Error killing process: {e}")
            return

        if app_data['type'] == 'System':
            cmd = app_data['exec']
            name = app_data['name']
            
            # Show confirmation dialog for power actions
            if name in ('Shutdown', 'Reboot', 'Logout'):
                reply = QMessageBox.question(
                    self,
                    f"{name}",
                    f"Are you sure you want to {name.lower()}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            print(f"Executing system command: {cmd}")
            try:
                subprocess.Popen(cmd.split(), start_new_session=True)
                self.close()
            except Exception as e:
                print(f"Error executing {name}: {e}")
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
        
        if app_data['type'] == 'BitwardenLogin':
            # Show login dialog
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton

            dialog = QDialog(self)
            dialog.setWindowTitle("Bitwarden Login")
            dialog.setMinimumWidth(400)

            layout = QVBoxLayout()

            layout.addWidget(QLabel("Email:"))
            email_input = QLineEdit()
            # Pre-fill email if available
            if self.bw_api.email:
                email_input.setText(self.bw_api.email)
            layout.addWidget(email_input)

            layout.addWidget(QLabel("Master Password:"))
            password_input = QLineEdit()
            password_input.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addWidget(password_input)

            # Self-hosted server option
            selfhosted_check = QCheckBox("Self-hosted / Vaultwarden Server")
            # Check if using custom server
            is_custom_server = (self.bw_api.identity_url != self.bw_api.DEFAULT_IDENTITY_URL or
                               self.bw_api.api_url != self.bw_api.DEFAULT_API_URL)
            if is_custom_server:
                selfhosted_check.setChecked(True)
            layout.addWidget(selfhosted_check)

            server_label = QLabel("Server URL (leave empty for official Bitwarden):")
            server_label.hide()
            layout.addWidget(server_label)

            server_input = QLineEdit()
            server_input.setPlaceholderText("https://vault.example.com")
            # Pre-fill server URL if using custom server
            if is_custom_server:
                # Remove /identity suffix for display (we'll add it back on login)
                base_url = self.bw_api.identity_url
                if base_url.endswith('/identity'):
                    base_url = base_url[:-9]  # Remove "/identity"
                server_input.setText(base_url)
                server_label.show()
                server_input.show()
            else:
                server_input.hide()
            layout.addWidget(server_input)

            def toggle_server_fields():
                if selfhosted_check.isChecked():
                    server_label.show()
                    server_input.show()
                else:
                    server_label.hide()
                    server_input.hide()

            selfhosted_check.toggled.connect(toggle_server_fields)

            login_btn = QPushButton("Login")
            layout.addWidget(login_btn)

            status_label = QLabel("")
            layout.addWidget(status_label)

            def do_login():
                email = email_input.text()
                password = password_input.text()

                if not email or not password:
                    status_label.setText("Please enter email and password")
                    return

                # Set custom server URLs if provided
                if selfhosted_check.isChecked() and server_input.text().strip():
                    base_url = server_input.text().strip().rstrip('/')
                    # For Vaultwarden/self-hosted, identity endpoints are at /identity
                    self.bw_api.identity_url = base_url + "/identity"
                    self.bw_api.api_url = base_url + "/api"
                else:
                    # Use official Bitwarden servers
                    self.bw_api.identity_url = self.bw_api.DEFAULT_IDENTITY_URL
                    self.bw_api.api_url = self.bw_api.DEFAULT_API_URL

                status_label.setText("Logging in...")
                QApplication.processEvents()

                success, msg = self.bw_api.login(email, password)
                if success:
                    status_label.setText("Login successful!")
                    QApplication.processEvents()
                    time.sleep(0.5)
                    dialog.accept()
                    self.search_bar.setText("bw ")
                    self.filter_items("bw ")
                else:
                    status_label.setText(f"Login failed: {msg}")

            login_btn.clicked.connect(do_login)
            password_input.returnPressed.connect(do_login)

            dialog.setLayout(layout)
            dialog.exec()
            return

        if app_data['type'] in ('BitwardenCopy', 'BitwardenCopyUsername'):
            self.hide()
            clipboard = QApplication.clipboard()
            clipboard.setText(app_data['exec'], mode=QClipboard.Mode.Clipboard)
            if clipboard.supportsSelection():
                clipboard.setText(app_data['exec'], mode=QClipboard.Mode.Selection)

            QApplication.processEvents()
            time.sleep(0.5)
            self.close()
            return

        if app_data['type'] == 'BitwardenGenerate':
            password = self.bw_api.generate_password()
            if password:
                self.hide()
                clipboard = QApplication.clipboard()
                clipboard.setText(password, mode=QClipboard.Mode.Clipboard)
                if clipboard.supportsSelection():
                    clipboard.setText(password, mode=QClipboard.Mode.Selection)
                QApplication.processEvents()
                time.sleep(0.5)
                print(f"Generated password copied to clipboard")
                self.close()
            else:
                self.details_desc.setText("Error generating password")
            return

        if app_data['type'] == 'BitwardenTOTP':
            # Handle TOTP differently based on mode
            if hasattr(self, 'bw_mode') and self.bw_mode == "api":
                # API mode - get TOTP from seed stored in item
                totp_seed = app_data.get('totp_seed')
                totp_code = self.bw_api.get_totp(totp_seed) if totp_seed else None
            else:
                # CLI mode - use bw get totp
                totp_code = self.bw_api.get_totp(app_data['item_id'])

            if totp_code:
                self.hide()
                clipboard = QApplication.clipboard()
                clipboard.setText(totp_code, mode=QClipboard.Mode.Clipboard)
                if clipboard.supportsSelection():
                    clipboard.setText(totp_code, mode=QClipboard.Mode.Selection)
                QApplication.processEvents()
                time.sleep(0.5)
                print(f"TOTP code copied to clipboard")
                self.close()
            else:
                self.details_desc.setText("Error getting TOTP code")
            return

        if app_data['type'] in ('BitwardenNote', 'BitwardenCard'):
            self.hide()
            clipboard = QApplication.clipboard()
            clipboard.setText(app_data['exec'], mode=QClipboard.Mode.Clipboard)
            if clipboard.supportsSelection():
                clipboard.setText(app_data['exec'], mode=QClipboard.Mode.Selection)
            QApplication.processEvents()
            time.sleep(0.5)
            self.close()
            return

        if app_data['type'] in ('Calculator', 'Clipboard', 'Emoji'):
            self.hide() # Hide immediately for responsiveness
            clipboard = QApplication.clipboard()
            clipboard.setText(app_data['exec'], mode=QClipboard.Mode.Clipboard)
            if clipboard.supportsSelection():
                clipboard.setText(app_data['exec'], mode=QClipboard.Mode.Selection)
            
            # Keep app alive briefly to ensure clipboard manager captures data
            QApplication.processEvents()
            time.sleep(0.5)
            
            print(f"Copied to clipboard: {app_data['exec'][:20]}...")
            self.close()
        elif app_data['type'] == 'WebSearch' or app_data['type'] in ('File', 'Image', 'Video'):
            print(f"Opening: {app_data['exec']}")
            # Track files in recent history
            if app_data['type'] in ('File', 'Image', 'Video'):
                self.indexer.add_recent_file(app_data['exec'])
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

    def closeEvent(self, event):
        if self.bw_api:
            self.bw_api.close()
        event.accept()
