import os
import json
import mimetypes

class RecentFileBrowser:
    """Browse and search recently opened files."""

    def __init__(self):
        self.history_file = os.path.expanduser("~/.config/wlaunch/recent_files.json")
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Ensure config directory exists."""
        config_dir = os.path.dirname(self.history_file)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

    def search(self, query=""):
        """Search recent files, optionally filtered by query."""
        # Load recent files
        recent_files = self._load_recent_files()

        # Filter out deleted files
        existing_files = [f for f in recent_files if os.path.exists(f)]

        # Save filtered list back if any files were deleted
        if len(existing_files) != len(recent_files):
            self._save_recent_files(existing_files)

        # Filter by query if provided
        if query:
            query_lower = query.lower()
            existing_files = [
                f for f in existing_files
                if query_lower in os.path.basename(f).lower() or
                   query_lower in f.lower()
            ]

        # Convert to item format
        items = []
        for file_path in existing_files:
            item = self._file_to_item(file_path)
            if item:
                items.append(item)

        return items

    def _file_to_item(self, file_path):
        """Convert file path to item dictionary."""
        try:
            filename = os.path.basename(file_path)

            # Determine file type
            mime_type, _ = mimetypes.guess_type(file_path)
            file_type = 'File'
            icon_name = 'text-x-generic'

            if mime_type:
                if mime_type.startswith('image/'):
                    file_type = 'Image'
                    icon_name = 'image-x-generic'
                elif mime_type.startswith('video/'):
                    file_type = 'Video'
                    icon_name = 'video-x-generic'
                elif mime_type.startswith('audio/'):
                    file_type = 'File'
                    icon_name = 'audio-x-generic'
                elif 'pdf' in mime_type:
                    icon_name = 'application-pdf'
                elif 'text' in mime_type or 'json' in mime_type or 'xml' in mime_type:
                    icon_name = 'text-x-generic'
                elif 'zip' in mime_type or 'compressed' in mime_type:
                    icon_name = 'package-x-generic'

            return {
                'name': filename,
                'exec': file_path,
                'icon': icon_name,
                'description': file_path,
                'type': file_type
            }
        except Exception as e:
            print(f"Error converting file to item: {e}")
            return None

    def _load_recent_files(self):
        """Load recent files from JSON."""
        if not os.path.exists(self.history_file):
            return []

        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading recent files JSON")
            return []
        except Exception as e:
            print(f"Error loading recent files: {e}")
            return []

    def _save_recent_files(self, files):
        """Save recent files to JSON."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(files, f, indent=2)
        except Exception as e:
            print(f"Error saving recent files: {e}")

    def add_recent_file(self, file_path):
        """Add a file to recent history."""
        # Normalize path
        file_path = os.path.abspath(file_path)

        # Load existing
        recent_files = self._load_recent_files()

        # Remove if already exists (to move to front)
        if file_path in recent_files:
            recent_files.remove(file_path)

        # Add to front
        recent_files.insert(0, file_path)

        # Limit to 100 items
        recent_files = recent_files[:100]

        # Save
        self._save_recent_files(recent_files)
