import subprocess

class ProcessManager:
    """Search and manage running processes."""

    def __init__(self):
        pass

    def search(self, query=""):
        """Search for processes matching query."""
        # Get all processes
        processes = self._get_all_processes()

        # Filter by query if provided
        if query:
            query_lower = query.lower()
            processes = [
                p for p in processes
                if query_lower in p['name'].lower() or
                   query_lower in p['description'].lower() or
                   query_lower == str(p['pid'])
            ]

        # Limit to top 50
        return processes[:50]

    def _get_all_processes(self):
        """Get all processes using ps aux."""
        try:
            # Run ps aux --sort=-%cpu to get processes sorted by CPU usage
            result = subprocess.run(
                ['ps', 'aux', '--sort=-%cpu'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                print(f"ps error: {result.stderr}")
                return []

            # Parse output
            lines = result.stdout.strip().split('\n')
            if len(lines) < 2:
                return []

            # Skip header line
            processes = []
            for line in lines[1:]:
                process = self._parse_ps_line(line)
                if process:
                    processes.append(process)

            return processes

        except subprocess.TimeoutExpired:
            print("ps timeout")
            return []
        except FileNotFoundError:
            print("ps command not found")
            return []
        except Exception as e:
            print(f"Error getting processes: {e}")
            return []

    def _parse_ps_line(self, line):
        """Parse a line from ps aux output."""
        try:
            # ps aux format:
            # USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
            parts = line.split(None, 10)  # Split on whitespace, max 11 parts

            if len(parts) < 11:
                return None

            user = parts[0]
            pid = parts[1]
            cpu = parts[2]
            mem = parts[3]
            command = parts[10]

            # Extract process name from command
            # Remove arguments and path
            process_name = command.split()[0] if command else 'unknown'
            process_name = process_name.split('/')[-1]  # Get basename

            # Format display name
            display_name = f"{process_name} ({cpu}% CPU, {mem}% MEM)"

            return {
                'name': display_name,
                'exec': f"kill {pid}",  # For display only
                'icon': 'utilities-system-monitor',
                'description': f"PID: {pid} | User: {user} | Command: {command[:60]}",
                'type': 'Process',
                'pid': pid
            }

        except Exception as e:
            print(f"Error parsing ps line: {e}")
            return None
