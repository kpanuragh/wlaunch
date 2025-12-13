import os
from xdg.BaseDirectory import xdg_data_dirs
from xdg.DesktopEntry import DesktopEntry
import logging

class AppIndexer:
    def __init__(self):
        self.apps = []
        self.logger = logging.getLogger("wlaunch.indexer")

    def index_apps(self):
        """Scans system for .desktop files and returns a list of apps."""
        self.apps = []
        seen_names = set()

        # Standard XDG paths + /usr/share/applications explicitly to be safe
        paths = list(xdg_data_dirs)
        if '/usr/share' not in paths:
            paths.append('/usr/share')

        for data_dir in paths:
            app_dir = os.path.join(data_dir, 'applications')
            if not os.path.exists(app_dir):
                continue

            for root, dirs, files in os.walk(app_dir):
                for file in files:
                    if file.endswith('.desktop'):
                        full_path = os.path.join(root, file)
                        try:
                            entry = DesktopEntry(full_path)
                            
                            # Skip if Hidden or NoDisplay
                            if entry.getHidden() or entry.getNoDisplay():
                                continue
                                
                            # Basic validation
                            name = entry.getName()
                            exec_cmd = entry.getExec()
                            
                            if not name or not exec_cmd:
                                continue

                            # Remove duplicates (simple name check for now)
                            if name in seen_names:
                                continue
                            seen_names.add(name)

                            # Clean up Exec command (remove %u, %F, etc.)
                            clean_exec = self._clean_exec(exec_cmd)
                            
                            self.apps.append({
                                'name': name,
                                'exec': clean_exec,
                                'icon': entry.getIcon() or 'application-x-executable',
                                'description': entry.getComment() or '',
                                'type': 'Application'
                            })
                            
                        except Exception as e:
                            self.logger.warning(f"Failed to parse {full_path}: {e}")

        # Add Custom System Commands
        system_cmds = [
            {'name': 'Shutdown', 'exec': 'systemctl poweroff', 'icon': 'system-shutdown', 'description': 'Power off the machine', 'type': 'System'},
            {'name': 'Reboot', 'exec': 'systemctl reboot', 'icon': 'system-reboot', 'description': 'Restart the machine', 'type': 'System'},
            {'name': 'Log Out', 'exec': 'i3-msg exit', 'icon': 'system-log-out', 'description': 'Exit i3 session', 'type': 'System'},
            {'name': 'Reload i3', 'exec': 'i3-msg reload', 'icon': 'view-refresh', 'description': 'Reload i3 configuration', 'type': 'System'},
             {'name': 'Restart i3', 'exec': 'i3-msg restart', 'icon': 'view-refresh', 'description': 'Restart i3 in place', 'type': 'System'},
        ]
        self.apps.extend(system_cmds)

        # Add User Scripts
        self.apps.extend(self._index_scripts())

        # Sort alphabetically
        self.apps.sort(key=lambda x: x['name'].lower())
        return self.apps

    def _index_scripts(self):
        """Scans user scripts directory, creating it if needed."""
        scripts_dir = os.path.expanduser("~/.config/wlaunch/scripts")
        scripts = []

        # Create directory if missing
        if not os.path.exists(scripts_dir):
            try:
                os.makedirs(scripts_dir, exist_ok=True)
                # Create a sample script
                sample_path = os.path.join(scripts_dir, "hello.sh")
                with open(sample_path, "w") as f:
                    f.write("#!/bin/bash\nnotify-send 'wlaunch' 'Hello from your custom script!'")
                os.chmod(sample_path, 0o755)
            except Exception as e:
                self.logger.error(f"Could not create scripts dir: {e}")
                return []

        # Scan for scripts
        for filename in os.listdir(scripts_dir):
            if filename.startswith('.'):
                continue
                
            full_path = os.path.join(scripts_dir, filename)
            if os.path.isfile(full_path):
                # Formulate a nice display name
                display_name = filename
                if '.' in display_name:
                    display_name = display_name.rsplit('.', 1)[0] # Remove extension
                display_name = display_name.replace('_', ' ').replace('-', ' ').title()

                scripts.append({
                    'name': display_name,
                    'exec': full_path,
                    'icon': 'text-x-script', # Generic script icon
                    'description': f'User Script ({filename})',
                    'type': 'Script'
                })
        
        return scripts
    
    def get_clipboard_history(self):
        """Reads clipboard history from JSON file."""
        import json
        history_file = os.path.expanduser("~/.config/wlaunch/clipboard_history.json")
        items = []
        
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    raw_history = json.load(f)
                
                for text in raw_history:
                    # Create display name (truncated, no newlines)
                    display = text.replace('\n', ' ')
                    if len(display) > 60:
                        display = display[:57] + "..."
                        
                    items.append({
                        'name': display,
                        'exec': text, # Full text for clipboard
                        'icon': 'edit-paste',
                        'description': 'Clipboard History',
                        'type': 'Clipboard'
                    })
            except Exception as e:
                self.logger.error(f"Failed to read clipboard history: {e}")
        
        return items

    def _clean_exec(self, exec_cmd):
        """Removes field codes like %u, %F from Exec command."""
        # Simple removal of common field codes
        parts = exec_cmd.split()
        clean_parts = [p for p in parts if not p.startswith('%')]
        return " ".join(clean_parts)

    def add_recent_file(self, file_path):
        """Track file in recent history (max 100 items)."""
        from core.recent_files import RecentFileBrowser
        browser = RecentFileBrowser()
        browser.add_recent_file(file_path)
