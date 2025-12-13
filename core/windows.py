import subprocess
import json

class WindowSwitcher:
    """Switch between i3 windows using i3-msg."""

    def __init__(self):
        self.windows = []

    def search(self, query=""):
        """Search for windows matching query."""
        # Get window tree from i3
        windows = self._get_all_windows()

        # Filter by query
        if query:
            query_lower = query.lower()
            windows = [
                w for w in windows
                if query_lower in w['name'].lower() or
                   query_lower in w['description'].lower()
            ]

        return windows

    def _get_all_windows(self):
        """Get all windows from i3 window tree."""
        try:
            # Run i3-msg to get window tree
            result = subprocess.run(
                ['i3-msg', '-t', 'get_tree'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                print(f"i3-msg error: {result.stderr}")
                return []

            # Parse JSON
            tree = json.loads(result.stdout)

            # Extract all windows recursively
            windows = []
            self._traverse_tree(tree, windows, workspace_name="")

            return windows

        except subprocess.TimeoutExpired:
            print("i3-msg timeout")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            return []
        except FileNotFoundError:
            print("i3-msg not found - is i3 running?")
            return []
        except Exception as e:
            print(f"Error getting windows: {e}")
            return []

    def _traverse_tree(self, node, windows, workspace_name="", parent_workspace=None):
        """Recursively traverse i3 tree to find windows."""
        # Check if this is a workspace
        if node.get('type') == 'workspace':
            workspace_name = node.get('name', '')
            parent_workspace = workspace_name

        # Check if this is an actual window (has window property and isn't a workspace/output)
        if node.get('window') and node.get('type') == 'con':
            window_id = node.get('id')
            title = node.get('name', 'Untitled')
            window_class = node.get('window_properties', {}).get('class', 'Unknown')

            # Skip if no meaningful title
            if not title or title == '__i3':
                return

            # Format the window item
            windows.append({
                'name': f"{title}",
                'exec': f'[con_id="{window_id}"] focus',  # i3 command
                'icon': 'preferences-system-windows',
                'description': f"Workspace: {workspace_name or 'Unknown'} | App: {window_class}",
                'type': 'Window',
                'window_id': window_id
            })

        # Recurse into child nodes
        for child in node.get('nodes', []):
            self._traverse_tree(child, windows, workspace_name, parent_workspace)

        # Also check floating nodes
        for child in node.get('floating_nodes', []):
            self._traverse_tree(child, windows, workspace_name, parent_workspace)
